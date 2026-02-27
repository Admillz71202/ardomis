import random
import re


# Ordered so longer patterns match before their subsets
_CONTRACTION_SWAPS = [
    (r"\bwould not\b", "wouldn't"),
    (r"\bcould not\b", "couldn't"),
    (r"\bshould not\b", "shouldn't"),
    (r"\bwill not\b", "won't"),
    (r"\bdid not\b", "didn't"),
    (r"\bhave not\b", "haven't"),
    (r"\bhas not\b", "hasn't"),
    (r"\bdo not\b", "don't"),
    (r"\bcannot\b", "can't"),
    (r"\bI am\b", "I'm"),
    (r"\bI will\b", "I'll"),
    (r"\bI would\b", "I'd"),
    (r"\bI have\b", "I've"),
    (r"\byou are\b", "you're"),
    (r"\byou will\b", "you'll"),
    (r"\byou would\b", "you'd"),
    (r"\byou have\b", "you've"),
    (r"\bthey are\b", "they're"),
    (r"\bwe are\b", "we're"),
    (r"\bit is\b", "it's"),
    (r"\bthat is\b", "that's"),
    (r"\bthere is\b", "there's"),
    (r"\bhere is\b", "here's"),
    (r"\bwhat is\b", "what's"),
    (r"\blet us\b", "let's"),
    (r"\bhe is\b", "he's"),
    (r"\bshe is\b", "she's"),
]


def humanize_reply(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    # Collapse whitespace
    value = re.sub(r"\s+", " ", value).strip()

    # Strip parenthetical asides — (text up to 120 chars)
    value = re.sub(r"\([^)]{1,120}\)", "", value)
    # Strip bracket stage directions — [text up to 120 chars]
    value = re.sub(r"\[[^\]]{1,120}\]", "", value)
    # Strip *action narration* — *text up to 80 chars*
    value = re.sub(r"\*[^*]{1,80}\*", "", value)
    # Strip leading stage-direction fragments
    value = re.sub(r"^\s*[\[\(][^\]\)]*[\]\)]\s*", "", value)

    value = re.sub(r"\s+", " ", value).strip()

    # Apply contractions
    for pattern, replacement in _CONTRACTION_SWAPS:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)

    return value.strip()


def _dynamic_vocalization(state=None) -> str:
    """Pick a mood-appropriate short vocal token."""
    if state is None:
        return random.choice(("heh", "hmm", "mm"))

    if state.irritation >= 62 or state.annoyance >= 70:
        return random.choice(("right", "yeah", "mm", "look"))

    if state.excitement >= 70:
        return random.choice(("oh", "okay", "hah", "damn", "hey"))

    if state.playfulness >= 70 and state.mood >= 52:
        return random.choice(("heh", "hah", "okay", "hey", "oh"))

    if state.seriousness >= 72 or state.focus >= 74:
        return random.choice(("mm", "yeah", "right", "look"))

    if state.boredom >= 68:
        return random.choice(("mm", "yeah", "huh", "right"))

    if state.warmth >= 80:
        return random.choice(("yeah", "hey", "mm", "heh"))

    if state.curiosity >= 75:
        return random.choice(("hm", "hmm", "oh", "wait"))

    return random.choice(("heh", "mm", "yeah", "right", "hm"))


def add_tts_vocalization(text: str, state=None, chance: float = 0.06) -> str:
    """Occasionally prepend or append a short natural vocalization token."""
    value = (text or "").strip()
    if not value:
        return ""

    if state is not None:
        chance += (state.playfulness - 50) / 700.0
        chance += (state.energy - 50) / 1100.0
        chance += max(0, state.excitement - 40) / 1100.0
        chance -= max(0, state.seriousness - 55) / 600.0
        chance -= max(0, state.irritation - 48) / 800.0
        chance += (state.warmth - 68) / 2000.0
    chance = max(0.02, min(0.13, chance))

    if random.random() >= chance:
        return value

    # Don't add to very short replies
    if len(value.split()) < 4:
        return value

    token = _dynamic_vocalization(state)

    # Prepend ~65% of the time, append otherwise
    if random.random() < 0.65:
        return f"{token}, {value[0].lower() + value[1:] if len(value) > 1 else value}"
    return f"{value} {token}."
