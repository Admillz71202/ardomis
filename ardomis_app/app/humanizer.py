import random
import re


def humanize_reply(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    # Collapse over-structured whitespace/newlines from model output.
    value = re.sub(r"\s+", " ", value).strip()

    # Remove stage directions if model slips.
    value = re.sub(r"\([^)]{1,80}\)", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    # Light contraction normalization for natural voice.
    swaps = {
        "do not": "don't",
        "cannot": "can't",
        "I am": "I'm",
        "you are": "you're",
    }
    for old, new in swaps.items():
        value = re.sub(rf"\b{re.escape(old)}\b", new, value, flags=re.IGNORECASE)

    return value.strip()


def _stretch(seed: str, tail: str, min_repeats: int, max_repeats: int) -> str:
    return f"{seed}{tail * random.randint(min_repeats, max_repeats)}"


def _dynamic_vocalization(state=None) -> str:
    if state is None:
        return random.choice(("RAHHH", "AWOOOO", "UHHHH", "MRMMMM"))

    if state.irritation >= 58 or state.annoyance >= 65:
        return random.choice(
            (
                _stretch("GR", "R", 3, 6),
                _stretch("TCH", "H", 3, 6),
                _stretch("RA", "H", 3, 6),
            )
        )

    if state.playfulness >= 66 and state.mood >= 52:
        return random.choice(
            (
                _stretch("AW", "O", 3, 7),
                _stretch("W", "O", 3, 6),
                _stretch("RA", "H", 3, 7),
                _stretch("Y", "O", 3, 6),
            )
        )

    if state.seriousness >= 68 or state.focus >= 70:
        return random.choice(
            (
                _stretch("H", "M", 3, 7),
                _stretch("MR", "M", 4, 8),
                _stretch("UH", "H", 3, 6),
            )
        )

    return random.choice(
        (
            _stretch("RA", "H", 3, 6),
            _stretch("AW", "O", 3, 6),
            _stretch("UH", "H", 3, 5),
            _stretch("MR", "M", 4, 7),
        )
    )


def add_tts_vocalization(text: str, state=None, chance: float = 0.12) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    if state is not None:
        chance += (state.playfulness - 50) / 500.0
        chance += (state.energy - 50) / 900.0
        chance -= max(0, state.seriousness - 60) / 700.0
        chance -= max(0, state.irritation - 55) / 900.0
    chance = max(0.03, min(0.28, chance))

    if random.random() >= chance:
        return value

    if re.search(r"\b[A-Z]{2,}(?:[HMRWO]){2,}\b", value):
        return value

    if len(value.split()) < 4:
        return value

    token = _dynamic_vocalization(state)
    if random.random() < 0.72:
        return f"{token}... {value}"
    return f"{value} {token}."
