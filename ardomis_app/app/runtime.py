import time

from ardomis_app.app.constants import DEDUPE_WINDOW_SEC, POST_TTS_COOLDOWN_SEC
from ardomis_app.services.audio_io import record_until_silence, speak_elevenlabs
from ardomis_app.services.stt_openai import transcribe_int16


class AudioRuntime:
    def __init__(self) -> None:
        self.ignore_audio_until = 0.0
        self.last_user_norm = ""
        self.last_user_ts = 0.0

    def listen_text(self, prompt_hint: str = "", max_wait_seconds: float | None = None) -> str:
        now = time.time()
        if now < self.ignore_audio_until:
            time.sleep(self.ignore_audio_until - now)

        audio = record_until_silence(max_wait_seconds=max_wait_seconds)
        if audio.size == 0:
            return ""
        return transcribe_int16(audio, 44100, prompt=prompt_hint).strip()

    def speak_and_cooldown(self, text: str) -> None:
        speak_elevenlabs(text)
        self.ignore_audio_until = time.time() + POST_TTS_COOLDOWN_SEC

    def should_dedupe(self, text_norm: str) -> bool:
        now = time.time()
        if text_norm and text_norm == self.last_user_norm and (now - self.last_user_ts) <= DEDUPE_WINDOW_SEC:
            return True
        self.last_user_norm = text_norm
        self.last_user_ts = now
        return False
