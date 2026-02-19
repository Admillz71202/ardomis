import os

def load_env_file(path: str) -> None:
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and (os.getenv(k) is None or os.getenv(k) == ""):
                    os.environ[k] = v
    except FileNotFoundError:
        pass

BASE_DIR = os.path.expanduser("~/ardomis")
os.makedirs(BASE_DIR, exist_ok=True)
ENV_PATH = os.path.join(BASE_DIR, "ardomis.env")
STATE_PATH = os.path.join(BASE_DIR, "state.json")

load_env_file(ENV_PATH)

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL_FAST = os.getenv("DEEPSEEK_MODEL_FAST", "deepseek-chat")
DEEPSEEK_MODEL_DEEP = os.getenv("DEEPSEEK_MODEL_DEEP", "deepseek-reasoner")
DEEPSEEK_MAX_TOKENS_FAST = int(os.getenv("DEEPSEEK_MAX_TOKENS_FAST", "180"))
DEEPSEEK_MAX_TOKENS_DEEP = int(os.getenv("DEEPSEEK_MAX_TOKENS_DEEP", "450"))

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "gpt-4o-transcribe")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")

# ElevenLabs
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5")


# Memory + Time
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", os.path.join(BASE_DIR, "memory.db"))
MEMORY_MAX_ROWS = int(os.getenv("MEMORY_MAX_ROWS", "800"))
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "America/New_York")

PRESENCE_RESPONSE_WINDOW_SEC = int(os.getenv("PRESENCE_RESPONSE_WINDOW_SEC", "20"))
PRESENCE_CHIME_MIN_SEC = int(os.getenv("PRESENCE_CHIME_MIN_SEC", "300"))
PRESENCE_CHIME_MAX_SEC = int(os.getenv("PRESENCE_CHIME_MAX_SEC", "900"))
PRESENCE_LISTEN_POLL_SEC = float(os.getenv("PRESENCE_LISTEN_POLL_SEC", "2.0"))
