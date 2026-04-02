import os
import time
import queue
import asyncio
import traceback
import inspect
from typing import Optional

import numpy as np

from config.logger import setup_logging
from core.utils.tts import MarkdownCleaner
from core.providers.tts.base import TTSProviderBase
from core.utils import opus_encoder_utils, textUtils
from core.providers.tts.dto.dto import SentenceType, ContentType, InterfaceType
from piper import PiperVoice

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        # Set as single-stream interface type
        self.interface_type = InterfaceType.SINGLE_STREAM
        
        # Model paths
        self.model_path = config.get(
            "model_path",
            "models/piper/vais1000/vi_VN-vais1000-medium.onnx",
        )
        self.config_path = config.get(
            "config_path",
            "models/piper/vais1000/vi_VN-vais1000-medium.onnx.json",
        )

        # Optional synthesis params
        self.speaker_id: Optional[int] = (
            int(config.get("speaker_id"))
            if str(config.get("speaker_id")).isdigit()
            else None
        )
        self.length_scale = float(config.get("length_scale", 1.0))
        self.noise_scale = float(config.get("noise_scale", 0.667))
        self.noise_w = float(config.get("noise_w", 0.8))
        self.sentence_silence = float(config.get("sentence_silence", 0.2))
        self.phoneme_input = (
            str(config.get("phoneme_input", False)).lower() in ("true", "1", "yes")
        )
        self.ssml = str(config.get("ssml", False)).lower() in ("true", "1", "yes")
        # Audio params
        sample_rate = config.get("sample_rate")
        self.sample_rate = int(sample_rate) if sample_rate else None
        self.audio_file_type = config.get("format", "pcm")

        self.before_stop_play_files = []

        # Load Piper model once
        try:
            self.voice = PiperVoice.load(
                self.model_path,
                config_path=self.config_path,
            )
            if not self.sample_rate:
                self.sample_rate = int(
                    getattr(self.voice, "sample_rate", None)
                    or self.voice.config.get("sample_rate", 22050)
                )
            logger.bind(tag=TAG).info(
                f"Piper TTS initialized | model={self.model_path} | sample_rate={self.sample_rate} | speaker_id={self.speaker_id}"
            )
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to load Piper model: {e}")
            raise

        # Opus only supports 8/12/16/24/48 kHz; resample if needed
        opus_supported = [8000, 12000, 16000, 24000, 48000]
        self.opus_sample_rate = (
            self.sample_rate if self.sample_rate in opus_supported else 24000
        )
        if self.sample_rate != self.opus_sample_rate:
            logger.bind(tag=TAG).warning(
                f"Piper sample_rate {self.sample_rate} not Opus-supported, resampling to {self.opus_sample_rate}"
            )

        # Create Opus encoder with supported sample rate
        self.opus_encoder = opus_encoder_utils.OpusEncoderUtils(
            sample_rate=self.opus_sample_rate, channels=1, frame_size_ms=60
        )

        # PCM buffer
        self.pcm_buffer = bytearray()

        # Record supported synth parameters for runtime compatibility
        try:
            self.synth_params = set(inspect.signature(self.voice.synthesize).parameters.keys())
            logger.bind(tag=TAG).debug(f"Piper synth params: {sorted(self.synth_params)}")
        except Exception as e:
            self.synth_params = set()
            logger.bind(tag=TAG).warning(f"Inspect synth signature failed: {e}")

    def tts_text_priority_thread(self):
        """Streaming text processing thread"""
        while not self.conn.stop_event.is_set():
            try:
                message = self.tts_text_queue.get(timeout=1)
                if message.sentence_type == SentenceType.FIRST:
                    # Initialize parameters
                    self.tts_stop_request = False
                    self.processed_chars = 0
                    self.tts_text_buff = []
                    self.before_stop_play_files.clear()
                elif ContentType.TEXT == message.content_type:
                    self.tts_text_buff.append(message.content_detail)
                    segment_text = self._get_segment_text()
                    if segment_text:
                        self.to_tts_single_stream(segment_text)

                elif ContentType.FILE == message.content_type:
                    logger.bind(tag=TAG).info(
                        f"Add audio file to playback list: {message.content_file}"
                    )
                    if message.content_file and os.path.exists(message.content_file):
                        # Process file audio data first
                        self._process_audio_file_stream(
                            message.content_file, 
                            callback=lambda audio_data: self.handle_audio_file(audio_data, message.content_detail)
                        )

                if message.sentence_type == SentenceType.LAST:
                    # Process remaining text
                    self._process_remaining_text_stream(True)

            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"TTS text processing failed: {str(e)}, type: {type(e).__name__}, stack: {traceback.format_exc()}"
                )

    def _process_remaining_text_stream(self, is_last=False):
        """Process remaining text and generate speech
        Returns:
            bool: 是否成功处理了文本
        """
        full_text = "".join(self.tts_text_buff)
        remaining_text = full_text[self.processed_chars :]
        if remaining_text:
            segment_text = textUtils.get_string_no_punctuation_or_emoji(remaining_text)
            if segment_text:
                self.to_tts_single_stream(segment_text, is_last)
                self.processed_chars += len(full_text)
            else:
                self._process_before_stop_play_files()
        else:
            self._process_before_stop_play_files()

    def to_tts_single_stream(self, text, is_last=False):
        try:
            max_repeat_time = 5
            text = MarkdownCleaner.clean_markdown(text)
            logger.bind(tag=TAG).debug(
                f"Piper to_tts_single_stream | is_last={is_last} | text_len={len(text)}"
            )
            try:
                asyncio.run(self.text_to_speak(text, is_last))
            except Exception as e:
                logger.bind(tag=TAG).warning(
                    f"Speech generation failed {5 - max_repeat_time + 1} times: {text}, error: {e}"
                )
                max_repeat_time -= 1

            if max_repeat_time > 0:
                logger.bind(tag=TAG).info(
                    f"Speech generation successful: {text}, retry {5 - max_repeat_time} times"
                )
            else:
                logger.bind(tag=TAG).error(
                    f"Speech generation failed: {text}, please check network or service status"
                )
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to generate TTS file: {e}")
        finally:
            return None

    async def text_to_speak(self, text, is_last):
        """Streaming TTS audio, directly call local piper-tts library"""
        frame_bytes = int(
            self.opus_sample_rate
            * self.opus_encoder.channels
            * self.opus_encoder.frame_size_ms
            / 1000
            * 2  # 16-bit PCM data
        )

        def _encode_and_send(chunk_pcm: bytes, src_rate: int):
            if not chunk_pcm:
                return
            target_pcm = (
                self._resample_pcm(chunk_pcm, src_rate, self.opus_sample_rate)
                if src_rate != self.opus_sample_rate
                else chunk_pcm
            )
            self.pcm_buffer.extend(target_pcm)
            logger.bind(tag=TAG).debug(
                f"Piper recv PCM chunk | in_len={len(chunk_pcm)} | after_resample_len={len(target_pcm)} | buffer={len(self.pcm_buffer)} | src_rate={src_rate} -> {self.opus_sample_rate}"
            )
            while len(self.pcm_buffer) >= frame_bytes:
                frame = bytes(self.pcm_buffer[:frame_bytes])
                del self.pcm_buffer[:frame_bytes]
                logger.bind(tag=TAG).debug(
                    f"Piper encode frame | frame_bytes={len(frame)} | buffer_left={len(self.pcm_buffer)}"
                )
                self.opus_encoder.encode_pcm_to_opus_stream(
                    frame,
                    end_of_stream=False,
                    callback=self.handle_opus,
                )

        def _synthesize():
            try:
                logger.bind(tag=TAG).debug(
                    f"Piper synth start | text_len={len(text)} | is_last={is_last}"
                )
                self.pcm_buffer.clear()
                self.tts_audio_queue.put((SentenceType.FIRST, [], text))
                synth_kwargs = self._build_synth_kwargs()
                logger.bind(tag=TAG).debug(
                    f"Piper synth kwargs (stream): {synth_kwargs}"
                )
                try:
                    chunk_count = 0
                    for chunk in self.voice.synthesize(text, **synth_kwargs):
                        chunk_count += 1
                        # Prefer documented fields
                        pcm_bytes = getattr(chunk, "audio_int16_bytes", None)
                        if pcm_bytes is None and hasattr(chunk, "audio_int16"):
                            pcm_bytes = chunk.audio_int16.tobytes()
                        if pcm_bytes is None:
                            # fallback: assume bytes
                            pcm_bytes = bytes(chunk)
                        chunk_sr = getattr(chunk, "sample_rate", self.sample_rate)
                        if not chunk_sr:
                            chunk_sr = self.sample_rate or self.opus_sample_rate
                        _encode_and_send(pcm_bytes, chunk_sr)
                    logger.bind(tag=TAG).debug(f"Piper synth chunks={chunk_count}")
                except TypeError:
                    pcm_data = self.voice.synthesize(text)
                    _encode_and_send(pcm_data, self.sample_rate or self.opus_sample_rate)

                if self.pcm_buffer:
                    self.opus_encoder.encode_pcm_to_opus_stream(
                        bytes(self.pcm_buffer),
                        end_of_stream=True,
                        callback=self.handle_opus,
                    )
                    self.pcm_buffer.clear()

                if is_last:
                    self._process_before_stop_play_files()
                    # notify end of audio to downstream
                    self.tts_audio_queue.put((SentenceType.LAST, [], text))
                logger.bind(tag=TAG).debug(
                    f"Piper synth finished | text_len={len(text)} | is_last={is_last}"
                )
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Piper TTS synth failed: {e}, stack: {traceback.format_exc()}"
                )
                self.tts_audio_queue.put((SentenceType.LAST, [], None))

        await asyncio.to_thread(_synthesize)

    async def close(self):
        """Resource cleanup"""
        await super().close()
        if hasattr(self, "opus_encoder"):
            self.opus_encoder.close()

    def to_tts(self, text: str) -> list:
        """Non-streaming TTS processing, for testing and saving audio files
        Args:
            text: Text to convert
        Returns:
            list: List of opus encoded audio data
        """
        start_time = time.time()
        text = MarkdownCleaner.clean_markdown(text)

        try:
            synth_kwargs = self._build_synth_kwargs(
            )
            logger.bind(tag=TAG).debug(
                f"Piper synth kwargs (non-stream): {synth_kwargs}"
            )
            try:
                pcm_chunks = []
                src_rate = self.sample_rate
                for chunk in self.voice.synthesize(text, **synth_kwargs):
                    pcm_bytes = getattr(chunk, "audio_int16_bytes", None)
                    if pcm_bytes is None and hasattr(chunk, "audio_int16"):
                        pcm_bytes = chunk.audio_int16.tobytes()
                    if pcm_bytes is None:
                        pcm_bytes = bytes(chunk)
                    chunk_sr = getattr(chunk, "sample_rate", self.sample_rate)
                    if chunk_sr:
                        src_rate = chunk_sr
                    pcm_chunks.append(pcm_bytes)
                pcm_data = b"".join(pcm_chunks)
            except TypeError:
                pcm_data = self.voice.synthesize(text)
                src_rate = self.sample_rate or self.opus_sample_rate

            if src_rate and src_rate != self.opus_sample_rate:
                pcm_data = self._resample_pcm(
                    pcm_data, src_rate, self.opus_sample_rate
                )

            logger.info(
                f"Piper TTS request successful | text_len={len(text)} | time={time.time() - start_time:.2f}s"
            )

            opus_datas = []
            frame_bytes = int(
                self.opus_encoder.sample_rate
                * self.opus_encoder.channels
                * self.opus_encoder.frame_size_ms
                / 1000
                * 2
            )

            for i in range(0, len(pcm_data), frame_bytes):
                frame = pcm_data[i : i + frame_bytes]
                if len(frame) < frame_bytes:
                    frame = frame + b"\x00" * (frame_bytes - len(frame))

                self.opus_encoder.encode_pcm_to_opus_stream(
                    frame,
                    end_of_stream=(i + frame_bytes >= len(pcm_data)),
                    callback=lambda opus: opus_datas.append(opus)
                )

            return opus_datas

        except Exception as e:
            logger.bind(tag=TAG).error(f"Piper TTS request failed: {e}, stack: {traceback.format_exc()}")
            return []

    def _resample_pcm(self, pcm_bytes: bytes, src_rate: int, dst_rate: int) -> bytes:
        """Linear resample int16 PCM from src_rate to dst_rate."""
        if src_rate == dst_rate or not pcm_bytes:
            return pcm_bytes
        pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
        src_len = len(pcm)
        if src_len <= 1:
            return pcm_bytes
        dst_len = int(src_len * dst_rate / src_rate)
        if dst_len <= 1:
            return pcm_bytes
        src_idx = np.arange(src_len)
        dst_idx = np.linspace(0, src_len - 1, dst_len)
        resampled = np.interp(dst_idx, src_idx, pcm).astype(np.int16)
        return resampled.tobytes()

    def _build_synth_kwargs(self):
        """Build kwargs based on piper-tts signature for compatibility."""
        kwargs = {}
        params = getattr(self, "synth_params", set())

        if "speaker_id" in params and self.speaker_id is not None:
            kwargs["speaker_id"] = self.speaker_id
        if "length_scale" in params:
            kwargs["length_scale"] = self.length_scale
        if "noise_scale" in params:
            kwargs["noise_scale"] = self.noise_scale
        if "noise_w" in params:
            kwargs["noise_w"] = self.noise_w
        if "sentence_silence" in params:
            kwargs["sentence_silence"] = self.sentence_silence
        if "phoneme_input" in params:
            kwargs["phoneme_input"] = self.phoneme_input
        if "ssml" in params:
            kwargs["ssml"] = self.ssml

        return kwargs
