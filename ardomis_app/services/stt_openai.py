import os
import tempfile
import wave

from ardomis_app.config.settings import OPENAI_API_KEY, OPENAI_STT_MODEL

_client = None


def _client_get():
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set.")
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError("openai package is required for speech-to-text. Install requirements.txt.") from exc
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def transcribe_int16(audio_i16, sample_rate: int, prompt: str = "") -> str:
    """
    Transcribe int16 mono audio using OpenAI STT.
    We FORCE English to avoid random language drift on noise.
    """
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise RuntimeError("numpy is required for speech-to-text audio preprocessing. Install requirements.txt.") from exc

    audio_i16 = np.asarray(audio_i16, dtype=np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name

    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_i16.tobytes())

        client = _client_get()
        with open(path, "rb") as af:
            r = client.audio.transcriptions.create(
                model=OPENAI_STT_MODEL,
                file=af,
                language="en",
                prompt=prompt or None,
            )
        return (getattr(r, "text", "") or "").strip()
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
