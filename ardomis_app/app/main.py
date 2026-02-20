import random
import time

from ardomis_app.app.constants import FORMAL, NAME, SLEEP_PHRASES, STOP_PHRASES
from ardomis_app.app.humanizer import humanize_reply
from ardomis_app.app.prompting import build_system_prompt
from ardomis_app.app.runtime import AudioRuntime
from ardomis_app.app.text_utils import (
    is_command_phrase,
    is_stop_request,
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
    SPOTIFY_ACCESS_TOKEN,
    STATE_PATH,
    YOUTUBE_API_KEY,
)
from ardomis_app.core.emotion import clamp, drift, emotion_meter, load_state, mood_line, on_interaction, save_state
from ardomis_app.core.memory import ChatMemory
from ardomis_app.services.command_center import CommandCenter
from ardomis_app.services.knowledge_vault import KnowledgeVault
from ardomis_app.services.llm_deepseek import deepseek_reply
from ardomis_app.services.scheduler_service import SchedulerService
from ardomis_app.services.vision_cam import capture_image
from ardomis_app.services.vision_openai import describe_image

SERIOUS_PHRASES = (
    "im being serious",
    "i am being serious",
    "actually stop",
    "take me serious",
)
QUIET_DOWN_PHRASES = ("actually shut up",)



def _generate_presence_line(state, memory: ChatMemory, recent_presence: list[str]) -> str:
    prompt = (
        "Generate exactly ONE short presence-mode line (6-16 words). "
        "It should feel human and spontaneous, either a weird/silly thought OR a gentle check-in. "
        "Do not repeat common assistant clichés. No emojis. No hashtags. "
        "Return only the spoken line."
    )
    try:
        line = deepseek_reply(build_system_prompt(state), memory.messages(), prompt, deep=False).strip()
        line = line.strip(" '\"")
        if line and line.lower() not in recent_presence:
            return line
    except Exception:
        pass

    fallback_openers = ("quick thought", "random thought", "tiny interruption", "side quest", "check-in")
    fallback_middles = ("bananas are nature's boomerangs", "time is fake but snacks are real", "you good over there", "i'm still on standby", "the room feels suspiciously calm")
    return f"{random.choice(fallback_openers)}: {random.choice(fallback_middles)}."

def _next_chime_delay(state) -> float:
    low = max(20, min(PRESENCE_CHIME_MIN_SEC, PRESENCE_CHIME_MAX_SEC))
    high = max(low, PRESENCE_CHIME_MAX_SEC)
    base = random.uniform(float(low), float(high))
    annoyance_factor = 1.0 - min(0.55, ((state.annoyance + state.irritation + state.sass) / 300.0))
    return max(12.0, base * annoyance_factor)


def _presence_interrupt(runtime: AudioRuntime, state, memory: ChatMemory, recent_presence: list[str]) -> None:
    odds_sound = 0.18 + (state.playfulness / 500.0)
    if random.random() < odds_sound:
        runtime.sound_effect_and_cooldown(random.choice(("beep", "laser", "robot", "glitch")))
        return
    line = _generate_presence_line(state, memory, recent_presence)
    recent_presence.append(line.lower())
    if len(recent_presence) > 8:
        recent_presence.pop(0)
    runtime.speak_and_cooldown(line)


def _is_repeated_reply(reply: str, memory: ChatMemory) -> bool:
    normalized = (reply or "").strip().lower()
    if not normalized:
        return False
    recent_assistant = [m.get("content", "").strip().lower() for m in memory.messages() if m.get("role") == "assistant"]
    return bool(recent_assistant and normalized == recent_assistant[-1])


def _generate_chat_reply(state, memory: ChatMemory, user_text: str, text_norm: str) -> str:
    deep = ("deep mode" in text_norm) or ("big brain" in text_norm) or ("use reasoner" in text_norm)
    reply = deepseek_reply(build_system_prompt(state), memory.messages(), user_text, deep=deep)
    reply = humanize_reply(reply)
    if not _is_repeated_reply(reply, memory):
        return reply

    retry_prompt = f"{user_text}\n\nDo not repeat earlier assistant wording. Answer the user directly in one short natural response."
    retry = deepseek_reply(build_system_prompt(state), memory.messages(), retry_prompt, deep=deep)
    retry = humanize_reply(retry)
    if retry and not _is_repeated_reply(retry, memory):
        return retry

    return "I heard you. Give me one second and ask that again plainly."


def main() -> None:
    runtime = AudioRuntime()
    memory = ChatMemory(max_messages=24, db_path=MEMORY_DB_PATH, max_persist_rows=MEMORY_MAX_ROWS)
    state = load_state(STATE_PATH)
    vault = KnowledgeVault(MEMORY_DB_PATH)
    scheduler = SchedulerService(db_path=MEMORY_DB_PATH, timezone_name=LOCAL_TIMEZONE)
    commands = CommandCenter(
        vault=vault,
        scheduler=scheduler,
        timezone_name=LOCAL_TIMEZONE,
        spotify_access_token=SPOTIFY_ACCESS_TOKEN,
        youtube_api_key=YOUTUBE_API_KEY,
    )

    mode = "presence"
    response_window_until = 0.0
    next_chime_at = time.time() + _next_chime_delay(state)
    recent_presence: list[str] = []

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
                _presence_interrupt(runtime, state, memory, recent_presence)
                response_window_until = time.time() + PRESENCE_RESPONSE_WINDOW_SEC
                next_chime_at = time.time() + _next_chime_delay(state)

            transcript = runtime.listen_text(
                prompt_hint="",
                max_wait_seconds=PRESENCE_LISTEN_POLL_SEC,
            )
            if not transcript:
                continue
            text_norm = norm(transcript)
            if text_norm.startswith("transcribe english"):
                continue
            if looks_like_garbage(transcript):
                continue

            if is_tiny_filler(text_norm) and not said_wake(transcript) and not is_command_phrase(text_norm, SLEEP_PHRASES):
                continue
            if runtime.should_dedupe(text_norm):
                continue

            print(f"\nYou: {transcript}")

            if text_norm in [norm(p) for p in QUIET_DOWN_PHRASES]:
                state.annoyance = clamp(state.annoyance - 25)
                state.sass = clamp(state.sass - 20)
                state.irritation = clamp(state.irritation - 20)
                state.playfulness = clamp(state.playfulness - 15)
                save_state(STATE_PATH, state)
                runtime.speak_and_cooldown("Copy. I'll dial it way down.")
                continue

            if text_norm in [norm(p) for p in SERIOUS_PHRASES]:
                state.seriousness = clamp(state.seriousness + 30)
                state.sass = clamp(state.sass - 22)
                state.irritation = clamp(state.irritation - 18)
                state.playfulness = clamp(state.playfulness - 25)
                state.annoyance = clamp(state.annoyance - 15)
                save_state(STATE_PATH, state)
                mode = "chat"
                runtime.speak_and_cooldown("Got it. Serious mode on. I'm locked in.")
                continue

            if is_stop_request(text_norm):
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown("Got you. Back to normal mode.")
                continue

            if is_command_phrase(text_norm, SLEEP_PHRASES):
                runtime.speak_and_cooldown("Alright. Sleeping.")
                response_window_until = 0.0
                continue

            if said_wake(transcript):
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown("Yeah?")
                continue

            if time.time() <= response_window_until:
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown("I’m listening.")

            continue

        user_text = runtime.listen_text()
        if looks_like_garbage(user_text):
            continue

        text_norm = norm(user_text)
        if text_norm.startswith("transcribe english"):
            continue
        if is_tiny_filler(text_norm) and not is_command_phrase(text_norm, STOP_PHRASES) and not is_command_phrase(text_norm, SLEEP_PHRASES):
            continue
        if runtime.should_dedupe(text_norm):
            continue

        print(f"\nYou: {user_text}")

        if text_norm in [norm(p) for p in QUIET_DOWN_PHRASES]:
            state.annoyance = clamp(state.annoyance - 25)
            state.sass = clamp(state.sass - 20)
            state.irritation = clamp(state.irritation - 20)
            state.playfulness = clamp(state.playfulness - 15)
            save_state(STATE_PATH, state)
            runtime.speak_and_cooldown("Copy. I'll dial it way down.")
            continue

        if text_norm in [norm(p) for p in SERIOUS_PHRASES]:
            state.seriousness = clamp(state.seriousness + 30)
            state.sass = clamp(state.sass - 22)
            state.irritation = clamp(state.irritation - 18)
            state.playfulness = clamp(state.playfulness - 25)
            state.annoyance = clamp(state.annoyance - 15)
            save_state(STATE_PATH, state)
            runtime.speak_and_cooldown("Understood. Serious mode on.")
            continue

        if is_stop_request(text_norm) or is_command_phrase(text_norm, STOP_PHRASES):
            runtime.speak_and_cooldown("Aight. I’m back in the background.")
            mode = "presence"
            next_chime_at = time.time() + _next_chime_delay(state)
            continue

        if is_command_phrase(text_norm, SLEEP_PHRASES):
            runtime.speak_and_cooldown("Alright. Sleeping.")
            mode = "presence"
            next_chime_at = time.time() + _next_chime_delay(state)
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
            if command.next_mode == "presence":
                mode = "presence"
                next_chime_at = time.time() + _next_chime_delay(state)
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
            reply = _generate_chat_reply(state, memory, user_text, text_norm)

        memory.add_assistant(reply)
        print(f"Ardomis: {reply}")
        runtime.speak_and_cooldown(reply)
