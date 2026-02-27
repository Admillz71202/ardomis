import time

from ardomis_app.app.constants import DEDUPE_WINDOW_SEC, POST_TTS_COOLDOWN_SEC
from ardomis_app.services.audio_io import play_sound_effect, record_until_silence, speak_elevenlabs
from ardomis_app.services.oled_face import make_face
from ardomis_app.services.stt_openai import transcribe_int16


class AudioRuntime:
    def __init__(self) -> None:
        self.ignore_audio_until = 0.0
        self.last_user_norm = ""
        self.last_user_ts = 0.0

        self.face = make_face()
        self.face.start()

    def listen_text(self, prompt_hint: str = "", max_wait_seconds: float | None = None) -> str:
        now = time.time()
        if now < self.ignore_audio_until:
            time.sleep(self.ignore_audio_until - now)

        audio = record_until_silence(max_wait_seconds=max_wait_seconds)
        if audio.size == 0:
            return ""
        return transcribe_int16(audio, 44100, prompt=prompt_hint).strip()

    def speak_and_cooldown(self, text: str) -> None:
        self.face.set_speaking(True)
        speak_elevenlabs(text)
        self.face.set_speaking(False)
        self.ignore_audio_until = time.time() + POST_TTS_COOLDOWN_SEC

    def should_dedupe(self, text_norm: str) -> bool:
        now = time.time()
        if text_norm and text_norm == self.last_user_norm and (now - self.last_user_ts) <= DEDUPE_WINDOW_SEC:
            return True
        self.last_user_norm = text_norm
        self.last_user_ts = now
        return False


    def sound_effect_and_cooldown(self, effect: str = "beep") -> None:
        play_sound_effect(effect)
        self.ignore_audio_until = time.time() + POST_TTS_COOLDOWN_SEC
