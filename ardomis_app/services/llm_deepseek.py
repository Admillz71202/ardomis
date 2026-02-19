from openai import OpenAI
from ardomis_app.config.settings import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL_FAST, DEEPSEEK_MODEL_DEEP,
    DEEPSEEK_MAX_TOKENS_FAST, DEEPSEEK_MAX_TOKENS_DEEP
)

def deepseek_reply(system_prompt: str, history_messages: list, user_text: str, deep: bool = False) -> str:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set.")

    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    model = DEEPSEEK_MODEL_DEEP if deep else DEEPSEEK_MODEL_FAST
    max_tokens = DEEPSEEK_MAX_TOKENS_DEEP if deep else DEEPSEEK_MAX_TOKENS_FAST

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history_messages)
    messages.append({"role": "user", "content": (user_text or "").strip()})

    r = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )

    out = (r.choices[0].message.content or "").strip()
    return out.replace("\n", " ").strip()
