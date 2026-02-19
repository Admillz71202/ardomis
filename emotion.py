import json, time
from dataclasses import dataclass, asdict

@dataclass
class EmotionState:
    mood: int = 55        # 0-100 (low = gloomy, high = upbeat)
    energy: int = 55      # 0-100
    sass: int = 70        # 0-100
    jealousy: int = 10    # 0-100
    last_ts: float = 0.0

def clamp(v: int) -> int:
    return max(0, min(100, int(v)))

def load_state(path: str) -> EmotionState:
    try:
        with open(path, "r") as f:
            d = json.load(f)
        st = EmotionState(**{k: d.get(k, getattr(EmotionState(), k)) for k in asdict(EmotionState()).keys()})
        if not st.last_ts:
            st.last_ts = time.time()
        return st
    except Exception:
        st = EmotionState()
        st.last_ts = time.time()
        return st

def save_state(path: str, st: EmotionState) -> None:
    st.last_ts = time.time()
    with open(path, "w") as f:
        json.dump(asdict(st), f, indent=2)

def drift(st: EmotionState) -> None:
    now = time.time()
    dt = now - (st.last_ts or now)
    if dt <= 0:
        return

    # gentle drift toward baseline over time
    baseline_mood = 55
    baseline_energy = 55

    def approach(cur, base, rate_per_min):
        step = rate_per_min * (dt / 60.0)
        if cur < base:
            return clamp(cur + step)
        if cur > base:
            return clamp(cur - step)
        return clamp(cur)

    st.mood = approach(st.mood, baseline_mood, 1.5)
    st.energy = approach(st.energy, baseline_energy, 2.0)

    # slight random natural variation
    st.last_ts = now

def on_interaction(st: EmotionState, intensity: int = 1) -> None:
    # talking boosts energy slightly, mood nudges up
    st.energy = clamp(st.energy + 2 * intensity)
    st.mood = clamp(st.mood + 1 * intensity)

def mood_line(st: EmotionState) -> str:
    mood = st.mood
    energy = st.energy
    sass = st.sass

    if mood < 35:
        mood_word = "gloomy"
    elif mood < 50:
        mood_word = "meh"
    elif mood < 70:
        mood_word = "steady"
    else:
        mood_word = "upbeat"

    if energy < 35:
        energy_word = "tired"
    elif energy < 60:
        energy_word = "awake"
    else:
        energy_word = "wired"

    if sass < 40:
        sass_word = "nice"
    elif sass < 70:
        sass_word = "snarky"
    else:
        sass_word = "menace"

    return f"mood={mood_word}, energy={energy_word}, vibe={sass_word} ({mood}/100, {energy}/100, {sass}/100)"
