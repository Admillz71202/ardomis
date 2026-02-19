from collections import deque

class ChatMemory:
    def __init__(self, max_messages: int = 24):
        self.buf = deque(maxlen=max_messages)

    def add_user(self, text: str) -> None:
        t = (text or "").strip()
        if t:
            self.buf.append({"role": "user", "content": t})

    def add_assistant(self, text: str) -> None:
        t = (text or "").strip()
        if t:
            self.buf.append({"role": "assistant", "content": t})

    def messages(self):
        return list(self.buf)

    def clear(self):
        self.buf.clear()
