FORMAL = "RDMS (Relational Digital Mind System)"
NAME = "Ardomis"

WAKE_WORDS = ("ardomis", "ardo")

# Common STT misrecognitions of "Ardomis" / "Ardo" — checked as substrings in norm'd text
WAKE_VARIANTS = (
    # Two-word forms of "ardomis"
    "art miss", "artmiss", "art-miss",
    "art oh miss", "art oh mis", "art oh mist",
    "ardo miss", "ardomiss",
    "art o miss", "arm a miss", "arma miss",
    # Two-word / short forms of "ardo"
    "art oh", "artoh", "art-oh",
    "art o", "arto",
    "ard oh", "arda", "ardoh",
    # Close single-word near-misses (caught by substring before fuzzy)
    "ardomus", "ardemis", "ardumis", "ardimus",
    "ardomas", "ardamis",
)

STOP_PHRASES = ("stop", "that's enough", "thats enough", "enough")
SLEEP_PHRASES = ("sleep ardomis", "sleep ardo", "go to sleep", "power down")

POST_TTS_COOLDOWN_SEC = 0.10
DEDUPE_WINDOW_SEC = 6.0
CHAT_IDLE_TO_PRESENCE_SEC = 12.0
