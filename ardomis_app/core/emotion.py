import json
import time
from dataclasses import asdict, dataclass


@dataclass
class EmotionState:
    # ── Core affect ──────────────────────────────────────────
    mood: int = 55
    energy: int = 55
    sass: int = 70

    # ── Social / relational ───────────────────────────────────
    jealousy: int = 10
    patience: int = 62
    affection: int = 64
    trust: int = 66
    warmth: int = 68

    # ── Cognitive / behavioral ────────────────────────────────
    focus: int = 58
    playfulness: int = 60
    seriousness: int = 45
    curiosity: int = 55

    # ── Reactive ─────────────────────────────────────────────
    irritation: int = 14
    annoyance: int = 35
    excitement: int = 40

    # ── Ambient / idle ────────────────────────────────────────
    boredom: int = 20
    loneliness: int = 25

    last_ts: float = 0.0


def clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def load_state(path: str) -> EmotionState:
    defaults = EmotionState()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        state_values = {
            key: data.get(key, getattr(defaults, key))
            for key in asdict(defaults).keys()
        }
        state = EmotionState(**state_values)
        if not state.last_ts:
            state.last_ts = time.time()
        return state
    except Exception:
        state = EmotionState()
        state.last_ts = time.time()
        return state


def save_state(path: str, state: EmotionState) -> None:
    state.last_ts = time.time()
    with open(path, "w") as f:
        json.dump(asdict(state), f, indent=2)


def _approach(cur: int, base: int, step: float) -> int:
    if cur < base:
        return clamp(cur + step)
    if cur > base:
        return clamp(cur - step)
    return clamp(cur)


def drift(state: EmotionState) -> None:
    """Time-based passive drift toward each field's resting baseline."""
    now = time.time()
    dt = now - (state.last_ts or now)
    if dt <= 0:
        return

    per_min = dt / 60.0

    # Core affect
    state.mood = _approach(state.mood, 55, 1.4 * per_min)
    state.energy = _approach(state.energy, 55, 1.9 * per_min)

    # Social / relational
    state.patience = _approach(state.patience, 62, 1.2 * per_min)
    state.affection = _approach(state.affection, 64, 0.8 * per_min)
    state.trust = _approach(state.trust, 66, 0.6 * per_min)
    state.warmth = _approach(state.warmth, 68, 0.3 * per_min)

    # Cognitive / behavioral
    state.focus = _approach(state.focus, 58, 1.0 * per_min)
    state.playfulness = _approach(state.playfulness, 60, 1.1 * per_min)
    state.seriousness = _approach(state.seriousness, 45, 0.9 * per_min)
    state.curiosity = _approach(state.curiosity, 55, 0.7 * per_min)

    # Reactive
    state.irritation = _approach(state.irritation, 14, 1.6 * per_min)
    state.annoyance = _approach(state.annoyance, 35, 1.2 * per_min)
    state.excitement = _approach(state.excitement, 40, 3.5 * per_min)  # fast decay

    # Ambient — drift toward HIGH baselines when idle (boredom/loneliness grow over time)
    state.boredom = _approach(state.boredom, 72, 1.2 * per_min)
    state.loneliness = _approach(state.loneliness, 62, 0.6 * per_min)

    state.last_ts = now


def on_interaction(state: EmotionState, intensity: int = 1) -> None:
    """Called on each user interaction. Positive boost across engagement metrics."""
    state.energy = clamp(state.energy + 3 * intensity)
    state.mood = clamp(state.mood + 2 * intensity)
    state.focus = clamp(state.focus + 2 * intensity)
    state.affection = clamp(state.affection + 2 * intensity)
    state.playfulness = clamp(state.playfulness + 2 * intensity)
    state.excitement = clamp(state.excitement + 16 * intensity)
    state.curiosity = clamp(state.curiosity + 6 * intensity)
    state.warmth = clamp(state.warmth + 1 * intensity)

    # Social reset — being talked to cuts boredom and loneliness
    state.boredom = clamp(state.boredom - 22 * intensity)
    state.loneliness = clamp(state.loneliness - 28 * intensity)

    # Small costs
    state.patience = clamp(state.patience - 1)
    state.annoyance = clamp(state.annoyance + 2 * intensity)


def mood_line(state: EmotionState) -> str:
    mood_word = (
        "dark" if state.mood < 25 else
        "glum" if state.mood < 40 else
        "meh" if state.mood < 55 else
        "decent" if state.mood < 70 else
        "good" if state.mood < 85 else
        "electric"
    )
    energy_word = (
        "dead" if state.energy < 25 else
        "drained" if state.energy < 40 else
        "low-key" if state.energy < 55 else
        "awake" if state.energy < 70 else
        "wired" if state.energy < 85 else
        "overdrive"
    )
    sass_word = (
        "soft" if state.sass < 35 else
        "dry" if state.sass < 55 else
        "sharp" if state.sass < 75 else
        "feral"
    )

    extras = []
    if state.boredom > 65:
        extras.append("bored")
    if state.loneliness > 60:
        extras.append("distant")
    if state.excitement > 72:
        extras.append("pumped")
    if state.warmth > 82:
        extras.append("warm")
    if state.curiosity > 75:
        extras.append("curious")
    if state.irritation > 55:
        extras.append("prickly")

    extra_str = (", " + "/".join(extras)) if extras else ""
    return (
        f"mood={mood_word}({state.mood}), energy={energy_word}({state.energy}), "
        f"sass={sass_word}({state.sass}){extra_str}"
    )


def emotion_meter(state: EmotionState) -> str:
    return (
        "full state: "
        f"mood={state.mood} energy={state.energy} sass={state.sass} "
        f"playfulness={state.playfulness} focus={state.focus} "
        f"affection={state.affection} warmth={state.warmth} trust={state.trust} "
        f"patience={state.patience} curiosity={state.curiosity} "
        f"excitement={state.excitement} irritation={state.irritation} "
        f"annoyance={state.annoyance} seriousness={state.seriousness} "
        f"boredom={state.boredom} loneliness={state.loneliness} "
        f"jealousy={state.jealousy}"
    )
