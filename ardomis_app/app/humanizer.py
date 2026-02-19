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
