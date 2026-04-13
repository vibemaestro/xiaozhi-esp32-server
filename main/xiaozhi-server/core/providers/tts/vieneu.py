import os
import uuid
import tempfile
import asyncio
from datetime import datetime
from core.providers.tts.base import TTSProviderBase
from vieneu import Vieneu

class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.tts = Vieneu()
        
        # Load preset voice if provided in config
        voice_id_config = config.get("voice_id")
        self.voice_data = None
        if voice_id_config:
            voices = self.tts.list_preset_voices()
            for desc, voice_id in voices:
                if voice_id == voice_id_config:
                    self.voice_data = self.tts.get_preset_voice(voice_id)
                    break
        
        self.audio_file_type = "wav" # vieneu save method outputs wav typically

    def generate_filename(self, extension=".wav"):
        return os.path.join(
            self.output_file,
            f"tts-{datetime.now().date()}@{uuid.uuid4().hex}{extension}",
        )

    async def text_to_speak(self, text, output_file):
        try:
            # Vieneu tts is synchronous, use run_in_executor to avoid blocking
            loop = asyncio.get_running_loop()
            
            def _infer_and_save():
                # Perform inference
                audio = self.tts.infer(text=text, voice=self.voice_data) if self.voice_data else self.tts.infer(text=text)
                
                if output_file:
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    self.tts.save(audio, output_file)
                    return True
                else:
                    # If output_file is None, we need to return bytes
                    # We can use a temporary file to save the wav and read its content
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_tmp_file:
                        temp_filename = temp_tmp_file.name
                        
                    try:
                        self.tts.save(audio, temp_filename)
                        with open(temp_filename, "rb") as f:
                            audio_bytes = f.read()
                        return audio_bytes
                    finally:
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)

            result = await loop.run_in_executor(None, _infer_and_save)
            return result
        except Exception as e:
            error_msg = f"Vieneu TTS inference failed: {e}"
            raise Exception(error_msg)
