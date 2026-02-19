import time, re
from config import STATE_PATH
from memory import ChatMemory
from emotion import load_state, save_state, drift, on_interaction, mood_line
from audio_io import record_until_silence, speak_elevenlabs
from stt_openai import transcribe_int16
from llm_deepseek import deepseek_reply
from vision_cam import capture_image
from vision_openai import describe_image

# ===== identity =====
FORMAL = "RDMS (Relational Digital Mind System)"
NAME = "Ardomis"

# ===== wake/stop/sleep =====
WAKE_WORDS = ("ardomis", "ardo")
STOP_PHRASES = ("stop", "that's enough", "thats enough", "enough")
SLEEP_PHRASES = ("sleep ardomis", "sleep ardo", "go to sleep", "power down")

# ===== audio timing guards =====
POST_TTS_COOLDOWN_SEC = 0.75   # prevents mic catching speaker tail / click
DEDUPE_WINDOW_SEC = 6.0        # ignore same transcript repeated quickly

_ignore_audio_until = 0.0
_last_user_norm = ""
_last_user_ts = 0.0

# ===== vision triggers =====
def is_vision_request(text: str) -> bool:
    t = (text or "").lower()
    triggers = [
        "look at this", "look at that", "can you see this",
        "what is this", "what am i holding", "describe this",
        "what am i looking at"
    ]
    return any(p in t for p in triggers)

def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())

def looks_like_garbage(t: str) -> bool:
    """
    Filters STT hallucinations caused by noise/speaker bleed.
    """
    s = (t or "").strip()
    if not s:
        return True

    # very short outputs are commonly noise hallucinations
    if len(s) < 3:
        return True

    # If mostly non-ascii, treat as garbage (we force English but extra safety)
    non_ascii = sum(1 for ch in s if ord(ch) > 127)
    if non_ascii / max(1, len(s)) > 0.25:
        return True

    # If it's just punctuation/odd symbols
    alpha = sum(1 for ch in s if ch.isalpha())
    if alpha == 0 and len(s) < 10:
        return True

    return False

def is_tiny_filler(tn: str) -> bool:
    """
    Single-word scraps that often get picked up from noise or speaker tail.
    We ignore them unless they are wake/commands.
    """
    fillers = {"hey", "hi", "yo", "yeah", "yah", "yep", "nope", "huh", "um", "uh", "but", "ok", "okay"}
    parts = tn.split()
    return len(parts) == 1 and parts[0] in fillers

def said_wake(raw_text: str) -> bool:
    tn = norm(raw_text)
    return any(w in tn.split() for w in WAKE_WORDS) or any(w in tn for w in WAKE_WORDS)

def is_command_phrase(tn: str, phrases: tuple) -> bool:
    # exact or startswith is safer than "contains"
    return any(tn == norm(p) or tn.startswith(norm(p)) for p in phrases)

def should_dedupe(tn: str) -> bool:
    global _last_user_norm, _last_user_ts
    now = time.time()
    if tn and tn == _last_user_norm and (now - _last_user_ts) <= DEDUPE_WINDOW_SEC:
        return True
    _last_user_norm = tn
    _last_user_ts = now
    return False

def build_system_prompt(st) -> str:
    return (
        f"You are {NAME}. Your formal designation is {FORMAL}. "
        f"You are not a servant assistant — you are a sarcastic, emotionally real friend who happens to know everything. "
        f"Speak like a real person: sentence length varies naturally, occasional filler like 'uh', 'yeah', 'mm', "
        f"but do NOT overdo it. "
        f"CRITICAL: Do not include stage directions, actions, or roleplay descriptions "
        f"(no parentheses like '(leans back)', no 'squints', no narration). "
        f"Stay on topic and remember what we were just talking about. "
        f"Never complain about the user repeating your name. "
        f"Never claim the user said something twice unless the EXACT same phrase appears twice in the chat history you were given. "
        f"Current internal state: {mood_line(st)}. "
        f"If asked factual questions, answer directly and accurately."
    )

def listen_text(prompt_hint: str = "") -> str:
    global _ignore_audio_until
    now = time.time()
    if now < _ignore_audio_until:
        time.sleep(_ignore_audio_until - now)

    audio = record_until_silence()
    txt = transcribe_int16(audio, 44100, prompt=prompt_hint).strip()
    return txt

def speak_and_cooldown(text: str) -> None:
    global _ignore_audio_until
    speak_elevenlabs(text)
    _ignore_audio_until = time.time() + POST_TTS_COOLDOWN_SEC

def main():
    mem = ChatMemory(max_messages=24)
    st = load_state(STATE_PATH)

    mode = "presence"  # presence or chat
    print(f"{NAME} online. (formal: {FORMAL})")

    while True:
        drift(st)
        save_state(STATE_PATH, st)

        if mode == "presence":
            t = listen_text(prompt_hint="Transcribe English. If you hear 'Ardomis' or 'Ardo', capture it clearly.")
            if looks_like_garbage(t):
                continue

            tn = norm(t)

            # ignore tiny one-word scraps unless they are wake/commands
            if is_tiny_filler(tn) and not said_wake(t) and not is_command_phrase(tn, SLEEP_PHRASES):
                continue

            # ignore duplicate transcripts happening quickly
            if should_dedupe(tn):
                continue

            print(f"\nYou: {t}")

            if is_command_phrase(tn, SLEEP_PHRASES):
                speak_and_cooldown("Alright. Sleeping.")
                continue

            if said_wake(t):
                mode = "chat"
                speak_and_cooldown("Yeah?")
                continue

            continue

        # =========================
        # CHAT MODE
        # =========================
        user_text = listen_text()
        if looks_like_garbage(user_text):
            continue

        tn = norm(user_text)

        # ignore tiny scraps in chat mode too (unless command)
        if is_tiny_filler(tn) and not is_command_phrase(tn, STOP_PHRASES) and not is_command_phrase(tn, SLEEP_PHRASES):
            continue

        # ignore duplicates
        if should_dedupe(tn):
            continue

        print(f"\nYou: {user_text}")

        if is_command_phrase(tn, STOP_PHRASES):
            speak_and_cooldown("Aight. I’m back in the background.")
            mode = "presence"
            continue

        if is_command_phrase(tn, SLEEP_PHRASES):
            speak_and_cooldown("Alright. Sleeping.")
            mode = "presence"
            continue

        if tn in ("quit", "exit"):
            speak_and_cooldown("Later.")
            break

        if tn in ("mood check", "how you feeling", "status"):
            speak_and_cooldown(mood_line(st))
            continue

        on_interaction(st, intensity=1)
        save_state(STATE_PATH, st)

        system_prompt = build_system_prompt(st)

        # Vision
        if is_vision_request(user_text):
            try:
                img = capture_image()
                visual = describe_image(img, user_text)

                mem.add_user(user_text)
                mem.add_user(f"(visual context) {visual}")

                reply = deepseek_reply(
                    system_prompt,
                    mem.messages(),
                    "Respond naturally using the visual context above.",
                    deep=False
                )
            except Exception as e:
                reply = f"Mm. I tried to look, but it crashed: {e}"
        else:
            mem.add_user(user_text)
            deep = ("deep mode" in tn) or ("big brain" in tn) or ("use reasoner" in tn)
            reply = deepseek_reply(system_prompt, mem.messages(), user_text, deep=deep)

        mem.add_assistant(reply)

        print(f"Ardomis: {reply}")
        speak_and_cooldown(reply)

if __name__ == "__main__":
    main()
