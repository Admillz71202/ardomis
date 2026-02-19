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
