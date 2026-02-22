import random
import re


def humanize_reply(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\([^)]{1,80}\)", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    swaps = {
        "do not": "don't",
        "cannot": "can't",
        "I am": "I'm",
        "you are": "you're",
    }
    for old, new in swaps.items():
        value = re.sub(rf"\b{re.escape(old)}\b", new, value, flags=re.IGNORECASE)

    return value.strip()


def _dynamic_vocalization(state=None) -> str:
    if state is None:
        return random.choice(("heh", "hah", "hmm"))

    if state.irritation >= 58 or state.annoyance >= 65:
        return random.choice(("hmm", "right", "yeah"))

    if state.playfulness >= 66 and state.mood >= 52:
        return random.choice(("heh", "hah", "okay"))

    if state.seriousness >= 68 or state.focus >= 70:
        return random.choice(("hmm", "yeah", "got it"))

    return random.choice(("heh", "hmm", "yeah"))


def add_tts_vocalization(text: str, state=None, chance: float = 0.05) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    if state is not None:
        chance += (state.playfulness - 50) / 800.0
        chance += (state.energy - 50) / 1200.0
        chance -= max(0, state.seriousness - 60) / 700.0
        chance -= max(0, state.irritation - 55) / 900.0
    chance = max(0.01, min(0.10, chance))

    if random.random() >= chance:
        return value

    if len(value.split()) < 5:
        return value

    token = _dynamic_vocalization(state)
    if random.random() < 0.55:
        return f"{token}, {value[0].lower() + value[1:] if len(value) > 1 else value}"
    return f"{value} {token}."
