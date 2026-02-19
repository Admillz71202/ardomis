import random
import time

from ardomis_app.app.constants import FORMAL, NAME, SLEEP_PHRASES, STOP_PHRASES
from ardomis_app.app.humanizer import humanize_reply
from ardomis_app.app.prompting import build_system_prompt
from ardomis_app.app.runtime import AudioRuntime
from ardomis_app.app.text_utils import (
    is_command_phrase,
    is_tiny_filler,
    is_vision_request,
    looks_like_garbage,
    norm,
    said_wake,
)
from ardomis_app.config.settings import (
    LOCAL_TIMEZONE,
    MEMORY_DB_PATH,
    MEMORY_MAX_ROWS,
    PRESENCE_CHIME_MAX_SEC,
    PRESENCE_CHIME_MIN_SEC,
    PRESENCE_LISTEN_POLL_SEC,
    PRESENCE_RESPONSE_WINDOW_SEC,
    STATE_PATH,
)
from ardomis_app.core.emotion import drift, emotion_meter, load_state, mood_line, on_interaction, save_state
from ardomis_app.core.memory import ChatMemory
from ardomis_app.services.command_center import CommandCenter
from ardomis_app.services.knowledge_vault import KnowledgeVault
from ardomis_app.services.llm_deepseek import deepseek_reply
from ardomis_app.services.scheduler_service import SchedulerService
from ardomis_app.services.vision_cam import capture_image
from ardomis_app.services.vision_openai import describe_image


PRESENCE_CHIMES = (
    "Yo. Still alive over there?",
    "Random check-in: you good?",
    "Quiet mode ping. I’m around if you need me.",
)


def _next_chime_delay() -> float:
    low = max(30, min(PRESENCE_CHIME_MIN_SEC, PRESENCE_CHIME_MAX_SEC))
    high = max(low, PRESENCE_CHIME_MAX_SEC)
    return random.uniform(float(low), float(high))


def main() -> None:
    runtime = AudioRuntime()
    memory = ChatMemory(max_messages=24, db_path=MEMORY_DB_PATH, max_persist_rows=MEMORY_MAX_ROWS)
    state = load_state(STATE_PATH)
    vault = KnowledgeVault(MEMORY_DB_PATH)
    scheduler = SchedulerService(db_path=MEMORY_DB_PATH, timezone_name=LOCAL_TIMEZONE)
    commands = CommandCenter(vault=vault, scheduler=scheduler, timezone_name=LOCAL_TIMEZONE)

    mode = "presence"
    response_window_until = 0.0
    next_chime_at = time.time() + _next_chime_delay()

    print(f"{NAME} online. (formal: {FORMAL})")

    while True:
        due_items = scheduler.due_items()
        for item in due_items:
            runtime.speak_and_cooldown(f"{item.kind.capitalize()} reminder: {item.text}")

        drift(state)
        save_state(STATE_PATH, state)

        if mode == "presence":
            now = time.time()
            if now >= next_chime_at:
                runtime.speak_and_cooldown(random.choice(PRESENCE_CHIMES))
                response_window_until = time.time() + PRESENCE_RESPONSE_WINDOW_SEC
                next_chime_at = time.time() + _next_chime_delay()

            transcript = runtime.listen_text(
                prompt_hint="Transcribe English. In background mode, capture wake words clearly.",
                max_wait_seconds=PRESENCE_LISTEN_POLL_SEC,
            )
            if not transcript:
                continue
            if looks_like_garbage(transcript):
                continue

            text_norm = norm(transcript)
            if is_tiny_filler(text_norm) and not said_wake(transcript) and not is_command_phrase(text_norm, SLEEP_PHRASES):
                continue
            if runtime.should_dedupe(text_norm):
                continue

            print(f"\nYou: {transcript}")

            if is_command_phrase(text_norm, SLEEP_PHRASES):
                runtime.speak_and_cooldown("Alright. Sleeping.")
                response_window_until = 0.0
                continue

            if said_wake(transcript):
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown("Yeah?")
                continue

            # Quiet-presence rule: only respond without wake word if Ardomis initiated
            # a check-in and the user replied within the response window.
            if time.time() <= response_window_until:
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown("I’m listening.")

            continue

        user_text = runtime.listen_text()
        if looks_like_garbage(user_text):
            continue

        text_norm = norm(user_text)
        if is_tiny_filler(text_norm) and not is_command_phrase(text_norm, STOP_PHRASES) and not is_command_phrase(text_norm, SLEEP_PHRASES):
            continue
        if runtime.should_dedupe(text_norm):
            continue

        print(f"\nYou: {user_text}")

        if is_command_phrase(text_norm, STOP_PHRASES):
            runtime.speak_and_cooldown("Aight. I’m back in the background.")
            mode = "presence"
            next_chime_at = time.time() + _next_chime_delay()
            continue

        if is_command_phrase(text_norm, SLEEP_PHRASES):
            runtime.speak_and_cooldown("Alright. Sleeping.")
            mode = "presence"
            next_chime_at = time.time() + _next_chime_delay()
            continue

        if text_norm in ("quit", "exit"):
            runtime.speak_and_cooldown("Later.")
            break

        if text_norm in ("mood check", "how you feeling", "status"):
            runtime.speak_and_cooldown(mood_line(state))
            continue

        if text_norm in ("emotion meter", "full status", "state dump"):
            runtime.speak_and_cooldown(emotion_meter(state))
            continue

        command = commands.handle(text_norm, user_text)
        if command.handled:
            runtime.speak_and_cooldown(command.response)
            continue

        on_interaction(state, intensity=1)
        save_state(STATE_PATH, state)

        if is_vision_request(user_text):
            try:
                image_path = capture_image()
                visual_context = describe_image(image_path, user_text)

                memory.add_user(user_text)
                memory.add_user(f"(visual context) {visual_context}")
                reply = deepseek_reply(
                    build_system_prompt(state),
                    memory.messages(),
                    "Respond naturally using the visual context above.",
                    deep=False,
                )
                reply = humanize_reply(reply)
            except Exception as exc:
                reply = f"Mm. I tried to look, but it crashed: {exc}"
        else:
            memory.add_user(user_text)
            deep = ("deep mode" in text_norm) or ("big brain" in text_norm) or ("use reasoner" in text_norm)
            reply = deepseek_reply(build_system_prompt(state), memory.messages(), user_text, deep=deep)
            reply = humanize_reply(reply)

        memory.add_assistant(reply)
        print(f"Ardomis: {reply}")
        runtime.speak_and_cooldown(reply)
