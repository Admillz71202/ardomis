# ─────────────────────────────────────────────────────────────────────────────
# constants.py — safe to edit for wake words, phrases, and timing
# ─────────────────────────────────────────────────────────────────────────────

FORMAL = "RDMS (Relational Digital Mind System)"
NAME   = "Ardomis"

# ── Wake words ────────────────────────────────────────────────────────────────
# WAKE_WORDS: exact tokens Ardomis listens for. Add alternate names here.
# WAKE_VARIANTS: common STT mis-transcriptions — add more if the mic misses you.
#   text_utils.said_wake() also runs Levenshtein fuzzy matching as a safety net.
WAKE_WORDS = ("ardomis", "ardo")

WAKE_VARIANTS = (
    # ── Two-word mis-reads of "ardomis" ──────────────────────────────────────
    "art miss", "artmiss", "art-miss",
    "art oh miss", "art oh mis", "art oh mist",
    "ardo miss", "ardomiss",
    "art o miss", "arm a miss", "arma miss",
    # ── Two-word / short mis-reads of "ardo" ─────────────────────────────────
    "art oh", "artoh", "art-oh",
    "art o", "arto",
    "ard oh", "arda", "ardoh",
    # ── Single-word near-misses ───────────────────────────────────────────────
    "ardomus", "ardemis", "ardumis", "ardimus",
    "ardomas", "ardamis",
)

# ── Mode-control phrases ──────────────────────────────────────────────────────
# Exact normalized match OR prefix match (see text_utils.is_command_phrase).
# Add alternatives freely — no other code changes needed.
STOP_PHRASES  = ("stop", "that's enough", "thats enough", "enough")
SLEEP_PHRASES = ("sleep ardomis", "sleep ardo", "go to sleep", "power down")

# ── Timing (seconds) ─────────────────────────────────────────────────────────
# POST_TTS_COOLDOWN_SEC     — dead silence after Ardomis speaks before mic re-opens.
#                             Raise slightly if your TTS clips the first word.
# DEDUPE_WINDOW_SEC         — same phrase heard twice within this window → ignored.
#                             Raise if echo/reverb is causing double-triggers.
# CHAT_IDLE_TO_PRESENCE_SEC — silence in chat mode before dropping to presence.
#                             Raise to give yourself more time between turns.
POST_TTS_COOLDOWN_SEC     = 0.10
DEDUPE_WINDOW_SEC         = 6.0
CHAT_IDLE_TO_PRESENCE_SEC = 12.0
