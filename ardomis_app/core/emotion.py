import json
import time
from dataclasses import asdict, dataclass


@dataclass
class EmotionState:
    mood: int = 55
    energy: int = 55
    sass: int = 70
    jealousy: int = 10
    patience: int = 62
    affection: int = 64
    focus: int = 58
    trust: int = 66
    playfulness: int = 60
    irritation: int = 14
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
    now = time.time()
    dt = now - (state.last_ts or now)
    if dt <= 0:
        return

    per_min = dt / 60.0

    state.mood = _approach(state.mood, 55, 1.4 * per_min)
    state.energy = _approach(state.energy, 55, 1.9 * per_min)
    state.patience = _approach(state.patience, 62, 1.2 * per_min)
    state.affection = _approach(state.affection, 64, 0.8 * per_min)
    state.focus = _approach(state.focus, 58, 1.0 * per_min)
    state.trust = _approach(state.trust, 66, 0.6 * per_min)
    state.playfulness = _approach(state.playfulness, 60, 1.1 * per_min)
    state.irritation = _approach(state.irritation, 14, 1.6 * per_min)

    state.last_ts = now


def on_interaction(state: EmotionState, intensity: int = 1) -> None:
    state.energy = clamp(state.energy + 2 * intensity)
    state.mood = clamp(state.mood + 1 * intensity)
    state.focus = clamp(state.focus + 1 * intensity)
    state.affection = clamp(state.affection + 1 * intensity)
    state.playfulness = clamp(state.playfulness + 1 * intensity)
    state.patience = clamp(state.patience - 1)


def mood_line(state: EmotionState) -> str:
    mood_word = "gloomy" if state.mood < 35 else "meh" if state.mood < 50 else "steady" if state.mood < 70 else "upbeat"
    energy_word = "tired" if state.energy < 35 else "awake" if state.energy < 60 else "wired"
    sass_word = "nice" if state.sass < 40 else "snarky" if state.sass < 70 else "menace"
    return (
        f"mood={mood_word}, energy={energy_word}, vibe={sass_word} "
        f"({state.mood}/100, {state.energy}/100, {state.sass}/100)"
    )


def emotion_meter(state: EmotionState) -> str:
    return (
        "emotion-meter: "
        f"mood={state.mood}, energy={state.energy}, sass={state.sass}, jealousy={state.jealousy}, "
        f"patience={state.patience}, affection={state.affection}, focus={state.focus}, trust={state.trust}, "
        f"playfulness={state.playfulness}, irritation={state.irritation}"
    )
