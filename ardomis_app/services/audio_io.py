import json
import subprocess

import numpy as np
import sounddevice as sd

from ardomis_app.config.settings import ELEVENLABS_API_KEY, ELEVENLABS_MODEL_ID, ELEVENLABS_VOICE_ID

MIC_SR = 44100
CHANNELS = 1

MAX_RECORD_SECONDS = 7.0
START_THRESHOLD = 0.012
STOP_THRESHOLD = 0.009
SILENCE_SECONDS_TO_STOP = 0.45
PRE_ROLL_SECONDS = 0.20


def rms_int16(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    xf = x.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(xf * xf) + 1e-12))


def pick_mic() -> int:
    devices = sd.query_devices()
    preferred = ("USB", "Mic", "microphone", "Audio", "PnP")

    for i, d in enumerate(devices):
        if int(d.get("max_input_channels", 0) or 0) > 0:
            name = (d.get("name") or "")
            if any(k.lower() in name.lower() for k in preferred):
                return i

    for i, d in enumerate(devices):
        if int(d.get("max_input_channels", 0) or 0) > 0:
            return i

    raise RuntimeError("No input-capable audio device found.")


def record_until_silence(max_wait_seconds: float | None = None) -> np.ndarray:
    mic_idx = pick_mic()
    sd.default.device = (mic_idx, None)

    chunk_ms = 20
    frames_per_chunk = int(MIC_SR * (chunk_ms / 1000.0))
    max_chunks_after_start = int((MAX_RECORD_SECONDS * 1000) / chunk_ms)

    pre_roll_chunks = max(1, int((PRE_ROLL_SECONDS * 1000) / chunk_ms))
    silence_chunks_to_stop = max(1, int((SILENCE_SECONDS_TO_STOP * 1000) / chunk_ms))
    max_wait_chunks = None if max_wait_seconds is None else max(1, int((max_wait_seconds * 1000) / chunk_ms))

    pre_roll: list[np.ndarray] = []
    captured: list[np.ndarray] = []

    print("Listening… (start talking)")

    with sd.InputStream(
        samplerate=MIC_SR,
        channels=CHANNELS,
        dtype="int16",
        blocksize=frames_per_chunk,
    ) as stream:
        wait_chunks = 0
        while True:
            data, _ = stream.read(frames_per_chunk)
            chunk = np.squeeze(data)
            pre_roll.append(chunk.copy())
            if len(pre_roll) > pre_roll_chunks:
                pre_roll.pop(0)

            if rms_int16(chunk) >= START_THRESHOLD:
                captured.extend(pre_roll)
                captured.append(chunk.copy())
                break

            wait_chunks += 1
            if max_wait_chunks is not None and wait_chunks >= max_wait_chunks:
                return np.array([], dtype=np.int16)

        silent_run = 0
        for _ in range(max_chunks_after_start):
            data, _ = stream.read(frames_per_chunk)
            chunk = np.squeeze(data)
            captured.append(chunk.copy())

            if rms_int16(chunk) < STOP_THRESHOLD:
                silent_run += 1
            else:
                silent_run = 0

            if silent_run >= silence_chunks_to_stop:
                break

    audio = np.concatenate(captured).astype(np.int16)
    dur = len(audio) / MIC_SR
    print(f"Recorded {dur:.2f}s")
    return audio


def stop_all_audio_now() -> None:
    subprocess.run(["bash", "-lc", "pkill -9 aplay >/dev/null 2>&1 || true"], check=False)


def speak_elevenlabs(text: str) -> None:
    t = (text or "").strip()
    if not t:
        return
    if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
        print("[TTS] Missing ELEVENLABS_API_KEY or ELEVENLABS_VOICE_ID")
        return

    out_mp3 = "/tmp/ardomis_tts.mp3"
    out_wav = "/tmp/ardomis_tts.wav"
    pre_wav = "/tmp/ardomis_pre.wav"

    payload = {"text": t, "model_id": ELEVENLABS_MODEL_ID}

    stop_all_audio_now()

    subprocess.run(
        [
            "curl", "-sS", "-X", "POST",
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
            "-H", f"xi-api-key: {ELEVENLABS_API_KEY}",
            "-H", "Content-Type: application/json",
            "-H", "Accept: audio/mpeg",
            "-d", json.dumps(payload),
            "--output", out_mp3,
        ],
        check=False,
        timeout=35,
    )

    subprocess.run(
        ["ffmpeg", "-y", "-i", out_mp3, "-ac", "1", "-ar", "48000", out_wav],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=25,
        check=False,
    )

    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "0.10", pre_wav],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )

    subprocess.run(["aplay", "-D", "default", pre_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    subprocess.run(["aplay", "-D", "default", out_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40, check=False)
