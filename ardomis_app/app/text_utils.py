import re

from ardomis_app.app.constants import WAKE_WORDS, WAKE_VARIANTS


def _levenshtein(a: str, b: str) -> int:
    """Bounded Levenshtein edit distance. Returns early if gap > 4."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) > len(b):
        a, b = b, a
    la, lb = len(a), len(b)
    if lb - la > 4:
        return lb - la
    prev = list(range(la + 1))
    for cb in b:
        cur = [prev[0] + 1] + [0] * la
        for i, ca in enumerate(a):
            cur[i + 1] = min(
                prev[i + 1] + 1,
                cur[i] + 1,
                prev[i] + (0 if ca == cb else 1),
            )
        prev = cur
    return prev[la]


def is_vision_request(text: str) -> bool:
    t = (text or "").lower()
    triggers = (
        "look at this", "look at that", "can you see this",
        "what is this", "what am i holding",
        "describe this", "what am i looking at",
        "what do you see", "take a look", "can you see that",
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
    fillers = {
        "hey", "hi", "yo", "yeah", "yah", "yep", "nope", "huh",
        "um", "uh", "but", "ok", "okay", "mhm", "mm", "hmm", "ah",
    }
    parts = text_norm.split()
    return len(parts) == 1 and parts[0] in fillers


def said_wake(raw_text: str) -> bool:
    text_norm = norm(raw_text)
    tokens = text_norm.split()

    # 1. Exact token match (fast path)
    if any(w in tokens for w in WAKE_WORDS):
        return True

    # 2. Substring match for multi-char wake words
    if any(w in text_norm for w in WAKE_WORDS):
        return True

    # 3. Curated phonetic variants (most common STT misrecognitions)
    for variant in WAKE_VARIANTS:
        if variant in text_norm:
            return True

    # 4. Fuzzy single-token match (only tokens ≥ 5 chars to limit false positives)
    for token in tokens:
        if len(token) >= 5:
            for wake in WAKE_WORDS:
                if _levenshtein(token, wake) <= 2:
                    return True

    # 5. Fuzzy bigram match (two adjacent tokens merged, e.g. "art" + "oh" = "artoh")
    for i in range(len(tokens) - 1):
        bigram = tokens[i] + tokens[i + 1]
        if 5 <= len(bigram) <= 10:
            for wake in WAKE_WORDS:
                if _levenshtein(bigram, wake) <= 2:
                    return True

    return False


def is_command_phrase(text_norm: str, phrases: tuple[str, ...]) -> bool:
    return any(
        text_norm == norm(phrase) or text_norm.startswith(norm(phrase))
        for phrase in phrases
    )


def is_stop_request(text_norm: str) -> bool:
    parts = text_norm.split()
    return (
        "stop" in parts
        or text_norm.startswith("hey stop")
        or text_norm.startswith("ardomis stop")
        or text_norm.startswith("ardo stop")
    )
