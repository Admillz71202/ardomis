import re

from ardomis_app.app.constants import WAKE_WORDS


def is_vision_request(text: str) -> bool:
    t = (text or "").lower()
    triggers = (
        "look at this",
        "look at that",
        "can you see this",
        "what is this",
        "what am i holding",
        "describe this",
        "what am i looking at",
    )
    return any(trigger in t for trigger in triggers)


def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def looks_like_garbage(text: str) -> bool:
    value = (text or "").strip()
    if not value or len(value) < 3:
        return True

    non_ascii = sum(1 for ch in value if ord(ch) > 127)
    if non_ascii / max(1, len(value)) > 0.25:
        return True

    alpha = sum(1 for ch in value if ch.isalpha())
    return alpha == 0 and len(value) < 10


def is_tiny_filler(text_norm: str) -> bool:
    fillers = {"hey", "hi", "yo", "yeah", "yah", "yep", "nope", "huh", "um", "uh", "but", "ok", "okay"}
    parts = text_norm.split()
    return len(parts) == 1 and parts[0] in fillers


def said_wake(raw_text: str) -> bool:
    text_norm = norm(raw_text)
    return any(w in text_norm.split() for w in WAKE_WORDS) or any(w in text_norm for w in WAKE_WORDS)


def is_command_phrase(text_norm: str, phrases: tuple[str, ...]) -> bool:
    return any(text_norm == norm(phrase) or text_norm.startswith(norm(phrase)) for phrase in phrases)
