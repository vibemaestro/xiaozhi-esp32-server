import io
import os
import sys
import uuid
import asyncio
from pathlib import Path
from datetime import datetime
from core.providers.tts.base import TTSProviderBase

# valtec_tts.TTS internally does `from infer import VietnameseTTS` which requires
# the project root (containing infer.py + src/) to be on sys.path.
# When installed via `pip install git+...`, infer.py is NOT included in the package.
# So we add the local cloned repo root to sys.path as a fallback.
_PROVIDER_DIR = Path(__file__).parent                        # core/providers/tts/
_SERVER_ROOT = (_PROVIDER_DIR / "../../../").resolve()       # xiaozhi-server/
_VALTEC_REPO = _SERVER_ROOT / "models" / "valtec-tts-repo"

if _VALTEC_REPO.is_dir() and str(_VALTEC_REPO) not in sys.path:
    sys.path.insert(0, str(_VALTEC_REPO))


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)

        # Speaker selection (NF, SF, NM1, SM, NM2)
        self.speaker = config.get("speaker", "NF")

        # Synthesis parameters
        self.speed = float(config.get("speed", 1.0))
        self.noise_scale = float(config.get("noise_scale", 0.6))
        self.noise_scale_w = float(config.get("noise_scale_w", 0.7))
        self.sdp_ratio = float(config.get("sdp_ratio", 0.0))

        self.audio_file_type = "wav"

        # Load TTS model (auto-downloads from HuggingFace on first run)
        from valtec_tts import TTS

        device = config.get("device", "auto")
        model_path = config.get("model_path", None)
        self.tts = TTS(model_path=model_path, device=device)

    def generate_filename(self, extension=".wav"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        try:
            loop = asyncio.get_running_loop()

            def _synthesize():
                audio, sr = self.tts.synthesize(
                    text=text,
                    speaker=self.speaker,
                    speed=self.speed,
                    noise_scale=self.noise_scale,
                    noise_scale_w=self.noise_scale_w,
                    sdp_ratio=self.sdp_ratio,
                )
                return audio, sr

            audio, sr = await loop.run_in_executor(None, _synthesize)

            import soundfile as sf

            if output_file:
                output_dir = os.path.dirname(output_file)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                sf.write(output_file, audio, sr)
                return True
            else:
                buf = io.BytesIO()
                sf.write(buf, audio, sr, format="WAV")
                return buf.getvalue()

        except Exception as e:
            raise Exception(f"Valtec TTS inference failed: {e}")
