import os
import io
import sys
import wave
import uuid
import time
from config.logger import setup_logging
from typing import Optional, Tuple, List
from core.providers.asr.dto.dto import InterfaceType
from core.providers.asr.base import ASRProviderBase

import numpy as np
import sherpa_onnx

from huggingface_hub import hf_hub_download, try_to_load_from_cache

TAG = __name__
logger = setup_logging()

REPO_ID = "g-group-ai-lab/gipformer-65M-rnnt"
SAMPLE_RATE = 16000
FEATURE_DIM = 80

ONNX_FILES = {
    "fp32": {
        "encoder": "encoder-epoch-35-avg-6.onnx",
        "decoder": "decoder-epoch-35-avg-6.onnx",
        "joiner": "joiner-epoch-35-avg-6.onnx",
    },
    "int8": {
        "encoder": "encoder-epoch-35-avg-6.int8.onnx",
        "decoder": "decoder-epoch-35-avg-6.int8.onnx",
        "joiner": "joiner-epoch-35-avg-6.int8.onnx",
    },
}


class CaptureOutput:
    def __enter__(self):
        self._output = io.StringIO()
        self._original_stdout = sys.stdout
        sys.stdout = self._output

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout
        self.output = self._output.getvalue()
        self._output.close()
        if self.output:
            logger.bind(tag=TAG).info(self.output.strip())


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.LOCAL
        self.output_dir = config.get("output_dir", "tmp/")
        self.quantize = config.get("quantize", "int8")
        self.num_threads = config.get("num_threads", 2)
        self.decoding_method = config.get("decoding_method", "greedy_search")
        self.delete_audio_file = delete_audio_file

        if self.quantize not in ONNX_FILES:
            logger.bind(tag=TAG).warning(
                f"quantize='{self.quantize}' không hợp lệ, dùng 'int8'"
            )
            self.quantize = "int8"

        os.makedirs(self.output_dir, exist_ok=True)

        model_paths = self._download_model()

        with CaptureOutput():
            self.model = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=model_paths["encoder"],
                decoder=model_paths["decoder"],
                joiner=model_paths["joiner"],
                tokens=model_paths["tokens"],
                num_threads=self.num_threads,
                sample_rate=SAMPLE_RATE,
                feature_dim=FEATURE_DIM,
                decoding_method=self.decoding_method,
            )

        logger.bind(tag=TAG).info(
            f"GipformerASR khởi tạo thành công | quantize={self.quantize} | "
            f"threads={self.num_threads} | decoding={self.decoding_method}"
        )

    def _download_model(self) -> dict:
        """Download hoặc load model ONNX từ HuggingFace cache."""
        files = ONNX_FILES[self.quantize]
        all_filenames = list(files.values()) + ["tokens.txt"]

        all_cached = all(
            isinstance(try_to_load_from_cache(repo_id=REPO_ID, filename=f), str)
            for f in all_filenames
        )

        if all_cached:
            logger.bind(tag=TAG).info(
                f"Đang load model {self.quantize} từ local cache..."
            )
        else:
            logger.bind(tag=TAG).info(
                f"Đang tải model {self.quantize} từ {REPO_ID}..."
            )

        try:
            paths = {}
            for key, filename in files.items():
                paths[key] = hf_hub_download(repo_id=REPO_ID, filename=filename)
            paths["tokens"] = hf_hub_download(repo_id=REPO_ID, filename="tokens.txt")

            if not all_cached:
                logger.bind(tag=TAG).info("Tải model hoàn tất.")

            return paths
        except Exception as e:
            logger.bind(tag=TAG).error(f"Tải model thất bại: {e}")
            raise

    def read_wave(self, wave_filename: str) -> Tuple[np.ndarray, int]:
        """Đọc file WAV, trả về mảng float32 trong khoảng [-1, 1] và sample rate."""
        with wave.open(wave_filename) as f:
            assert f.getnchannels() == 1, f.getnchannels()
            assert f.getsampwidth() == 2, f.getsampwidth()
            num_samples = f.getnframes()
            samples = f.readframes(num_samples)
            samples_int16 = np.frombuffer(samples, dtype=np.int16)
            samples_float32 = samples_int16.astype(np.float32)
            samples_float32 = samples_float32 / 32768
            return samples_float32, f.getframerate()

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format: str = "opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """Chuyển đổi giọng nói sang văn bản tiếng Việt."""
        file_path = None
        try:
            start_time = time.time()
            if audio_format == "pcm":
                pcm_data = opus_data
            else:
                pcm_data = self.decode_opus(opus_data)
            file_path = self.save_audio_to_file(pcm_data, session_id)
            logger.bind(tag=TAG).debug(
                f"Lưu audio: {time.time() - start_time:.3f}s | {file_path}"
            )

            start_time = time.time()
            samples, sample_rate = self.read_wave(file_path)
            stream = self.model.create_stream()
            stream.accept_waveform(sample_rate, samples)
            self.model.decode_stream(stream)
            text = stream.result.text.strip()
            logger.bind(tag=TAG).debug(
                f"Nhận dạng: {time.time() - start_time:.3f}s | {text}"
            )

            return text, file_path

        except Exception as e:
            logger.bind(tag=TAG).error(f"Nhận dạng giọng nói thất bại: {e}", exc_info=True)
            return "", file_path
        finally:
            if self.delete_audio_file and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.bind(tag=TAG).debug(f"Đã xóa file tạm: {file_path}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Xóa file thất bại: {file_path} | {e}")
