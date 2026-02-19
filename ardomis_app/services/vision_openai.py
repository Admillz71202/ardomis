import base64

from ardomis_app.config.settings import OPENAI_API_KEY, OPENAI_VISION_MODEL

_client = None


def _client_get():
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not set.")
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError("openai package is required for vision features. Install requirements.txt.") from exc
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def describe_image(image_path: str, question: str) -> str:
    client = _client_get()
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    msg = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }
    ]

    r = client.chat.completions.create(
        model=OPENAI_VISION_MODEL,
        messages=msg,
        max_tokens=220,
    )
    return (r.choices[0].message.content or "").strip()
