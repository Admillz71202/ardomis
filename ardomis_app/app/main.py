import random
import time
from datetime import datetime

from ardomis_app.app.constants import CHAT_IDLE_TO_PRESENCE_SEC, FORMAL, NAME, SLEEP_PHRASES, STOP_PHRASES
from ardomis_app.app.humanizer import add_tts_vocalization, humanize_reply
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


# ─────────────────────────────────────────────────────────────────────────────
# Presence mode helpers
# ─────────────────────────────────────────────────────────────────────────────

_PRESENCE_CATEGORIES = (
    "random_thought",
    "check_in",
    "question",
    "tease",
    "observation",
    "callback",
    "introspect",
)


def _get_time_label() -> str:
    hour = datetime.now().hour
    if hour < 6:
        return "dead of night"
    if hour < 10:
        return "morning"
    if hour < 12:
        return "late morning"
    if hour < 14:
        return "midday"
    if hour < 17:
        return "afternoon"
    if hour < 20:
        return "evening"
    if hour < 23:
        return "late evening"
    return "past midnight"


def _pick_presence_category(state) -> str:
    weights = {
        "random_thought": 22 + state.playfulness // 6,
        "check_in":       14 + state.loneliness // 5,
        "question":       10 + state.curiosity // 7,
        "tease":           8 + state.sass // 9,
        "observation":    20,
        "callback":       12 + state.warmth // 10,
        "introspect":      6 + state.boredom // 9,
    }
    total = sum(weights.values())
    r = random.uniform(0, total)
    cumulative = 0.0
    for cat, w in weights.items():
        cumulative += w
        if r < cumulative:
            return cat
    return "random_thought"


def _build_presence_prompt(category: str, state, memory: ChatMemory, recent_presence: list[str]) -> tuple[str, list]:
    """Return (prompt_text, history_messages) for this presence category."""
    time_label = _get_time_label()
    vibe = mood_line(state)
    avoid = (
        f"Do NOT repeat or closely echo these recent lines: {'; '.join(recent_presence[-4:])}. "
        if recent_presence else ""
    )

    # For callback use recent messages; for everything else an empty history keeps
    # the LLM from trying to "respond" to the last user turn.
    last_user = ""
    for msg in reversed(memory.messages()):
        if msg.get("role") == "user":
            last_user = (msg.get("content") or "")[:100].strip()
            break

    history = memory.messages()[-6:] if category == "callback" else []

    prompts = {
        "random_thought": (
            f"It's {time_label}. Generate ONE short spontaneous thought (8-18 words). "
            "Absurdist, philosophical, mundane, or weird—whichever feels natural. "
            f"Current vibe: {vibe}. {avoid}"
            "Return only the spoken line. No quotes, no punctuation prefix."
        ),
        "check_in": (
            f"It's {time_label}. Generate ONE casual check-in line to the user (6-14 words). "
            "Sound genuinely curious, not scripted. Each time it should feel completely different. "
            f"Vibe: {vibe}. {avoid}"
            "Return only the spoken line."
        ),
        "question": (
            f"It's {time_label}. Ask ONE short question to the user (6-14 words). "
            "Could be weird, deep, personal, or mundane. Make it feel spontaneous, not interview-like. "
            f"Vibe: {vibe}. Curiosity: {state.curiosity}/100. {avoid}"
            "Return only the question."
        ),
        "tease": (
            f"It's {time_label}. Generate ONE short playful tease or light roast (6-14 words). "
            "Clever and warm, not mean. Real banter energy. "
            f"Sass: {state.sass}/100. Vibe: {vibe}. {avoid}"
            "Return only the spoken line."
        ),
        "observation": (
            f"It's {time_label}. Make ONE short ambient observation (8-16 words). "
            "About the silence, the time, the room, existence—whatever feels present. Keep it real. "
            f"Vibe: {vibe}. {avoid}"
            "Return only the observation."
        ),
        "callback": (
            f"It's {time_label}. "
            + (
                f"Generate ONE brief follow-up thought related to this recent topic: '{last_user}' (6-14 words). "
                "Sound like your brain is still on it—not forced. "
                if last_user else
                "Generate ONE ambient observation (8-14 words). "
            )
            + f"Vibe: {vibe}. {avoid}"
            + "Return only the spoken line."
        ),
        "introspect": (
            f"It's {time_label}. Generate ONE short self-aware or introspective line (6-14 words). "
            "Could be about boredom, the quiet, your own thoughts, or just existing. "
            "Self-aware but not melodramatic. "
            f"Boredom: {state.boredom}/100. Loneliness: {state.loneliness}/100. Vibe: {vibe}. {avoid}"
            "Return only the spoken line."
        ),
    }

    return prompts.get(category, prompts["random_thought"]), history


_PRESENCE_FALLBACKS = {
    "random_thought": [
        "okay but why do birds sound like they're gossiping.",
        "existence is wild. like. genuinely.",
        "I keep thinking about how weird rooms are when no one's talking in them.",
        "time is moving at a suspicious pace right now.",
        "I wonder if fish know they're wet.",
    ],
    "check_in": [
        "you good over there?",
        "still breathing?",
        "what's actually going on with you today?",
        "you still with me?",
    ],
    "question": [
        "what's the last thing that genuinely surprised you?",
        "if you had to describe today in one word, what would it be?",
        "what are you actually thinking about right now?",
    ],
    "tease": [
        "you've been suspiciously quiet. plotting something?",
        "I'm starting to think you're avoiding me.",
        "this silence is very telling.",
    ],
    "observation": [
        "it's weirdly quiet in here.",
        "I like the part of the day where nothing is exploding.",
        "the air in this room has a vibe.",
    ],
    "callback": [
        "still thinking about what you said earlier.",
        "anyway.",
        "that came back to me just now.",
    ],
    "introspect": [
        "I get bored in an interesting way.",
        "the quiet has a texture to it, you know?",
        "I wonder what I'd be doing if I didn't have anything to do.",
    ],
}


def _generate_presence_line(state, memory: ChatMemory, recent_presence: list[str]) -> str:
    category = _pick_presence_category(state)
    prompt, history = _build_presence_prompt(category, state, memory, recent_presence)

    try:
        line = deepseek_reply(build_system_prompt(state), history, prompt, deep=False).strip().strip(" '\"")
        if line and line.lower() not in (p.lower() for p in recent_presence):
            return line
    except Exception:
        pass

    return random.choice(_PRESENCE_FALLBACKS.get(category, _PRESENCE_FALLBACKS["random_thought"]))


def _next_chime_delay(state) -> float:
    low = max(20, min(PRESENCE_CHIME_MIN_SEC, PRESENCE_CHIME_MAX_SEC))
    high = max(low, PRESENCE_CHIME_MAX_SEC)
    base = random.uniform(float(low), float(high))

    # Annoyance/irritation/sass → speak less often
    annoyance_factor = 1.0 - min(0.55, (state.annoyance + state.irritation + state.sass) / 300.0)

    # Boredom + loneliness → speak more often (they want company)
    idle_factor = 1.0 - min(0.40, (state.boredom + state.loneliness) / 380.0)

    return max(10.0, base * annoyance_factor * idle_factor)


def _presence_interrupt(runtime: AudioRuntime, state, memory: ChatMemory, recent_presence: list[str]) -> None:
    # Chance of a sound effect scales with playfulness + excitement
    odds_sound = 0.14 + (state.playfulness / 650.0) + (state.excitement / 900.0)
    if random.random() < odds_sound:
        runtime.sound_effect_and_cooldown(random.choice(("beep", "laser", "robot", "glitch")))
        return

    line = _generate_presence_line(state, memory, recent_presence)
    recent_presence.append(line.lower())
    if len(recent_presence) > 10:
        recent_presence.pop(0)
    runtime.speak_and_cooldown(line)


# ─────────────────────────────────────────────────────────────────────────────
# Chat mode helpers
# ─────────────────────────────────────────────────────────────────────────────

def _generate_mode_line(state, memory: ChatMemory, intent: str) -> str:
    if intent == "chat_to_presence":
        prompt = (
            "Generate one short natural line for stepping back to background / ambient mode (5-14 words). "
            "Sound like yourself fading out for a bit—not overly polite or formal. "
            "No emojis, no hashtags. Return only the line."
        )
        fallback = (
            "Alright, I'll be around.",
            "Going quiet for now.",
            "Back in the background.",
            "Catch you later.",
            "I'll be here.",
            "Cool. I'll fade out.",
        )
    else:
        prompt = (
            "Generate one short natural line for waking up to active chat (4-12 words). "
            "Sound present and real—not performatively energetic. Could be a simple acknowledgment or quick quip. "
            "No emojis, no hashtags. Return only the line."
        )
        fallback = (
            "Yeah?",
            "I'm here.",
            "What's up.",
            "Listening.",
            "Go ahead.",
            "Hey.",
            "Yeah, what.",
        )

    try:
        line = deepseek_reply(
            build_system_prompt(state), memory.messages(), prompt, deep=False
        ).strip().strip(" '\"")
        if line:
            return line
    except Exception:
        pass

    return random.choice(fallback)


def _is_repeated_reply(reply: str, memory: ChatMemory) -> bool:
    normalized = (reply or "").strip().lower()
    if not normalized:
        return False
    recent_assistant = [
        m.get("content", "").strip().lower()
        for m in memory.messages()
        if m.get("role") == "assistant"
    ]
    return bool(recent_assistant and normalized == recent_assistant[-1])


def _generate_chat_reply(state, memory: ChatMemory, user_text: str, text_norm: str) -> str:
    deep = (
        "deep mode" in text_norm
        or "big brain" in text_norm
        or "use reasoner" in text_norm
    )
    reply = deepseek_reply(build_system_prompt(state), memory.messages(), user_text, deep=deep)
    reply = humanize_reply(reply)
    reply = add_tts_vocalization(reply, state=state)

    if not _is_repeated_reply(reply, memory):
        return reply

    retry_prompt = (
        f"{user_text}\n\n"
        "Do not repeat earlier assistant wording. Answer directly in one short natural response."
    )
    retry = deepseek_reply(build_system_prompt(state), memory.messages(), retry_prompt, deep=deep)
    retry = humanize_reply(retry)
    retry = add_tts_vocalization(retry, state=state)
    if retry and not _is_repeated_reply(retry, memory):
        return retry

    return "I heard you. Ask that again plainly."


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

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
        # ── Scheduled items ──────────────────────────────────────────────────
        due_items = scheduler.due_items()
        for item in due_items:
            runtime.speak_and_cooldown(f"{item.kind.capitalize()} reminder: {item.text}")

        drift(state)
        save_state(STATE_PATH, state)

        # ════════════════════════════════════════════════════════════════════
        # PRESENCE MODE
        # ════════════════════════════════════════════════════════════════════
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
                runtime.speak_and_cooldown("Copy. Dialing it back.")
                continue

            if text_norm in [norm(p) for p in SERIOUS_PHRASES]:
                state.seriousness = clamp(state.seriousness + 30)
                state.sass = clamp(state.sass - 22)
                state.irritation = clamp(state.irritation - 18)
                state.playfulness = clamp(state.playfulness - 25)
                state.annoyance = clamp(state.annoyance - 15)
                save_state(STATE_PATH, state)
                mode = "chat"
                runtime.speak_and_cooldown("Got it. Serious mode. I'm locked in.")
                continue

            if is_stop_request(text_norm):
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown("Got you. Back to normal.")
                continue

            if is_command_phrase(text_norm, SLEEP_PHRASES):
                runtime.speak_and_cooldown("Alright. Sleeping.")
                response_window_until = 0.0
                continue

            if said_wake(transcript):
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown(_generate_mode_line(state, memory, "presence_to_chat"))
                continue

            if time.time() <= response_window_until:
                mode = "chat"
                response_window_until = 0.0
                runtime.speak_and_cooldown(_generate_mode_line(state, memory, "presence_to_chat"))

            continue

        # ════════════════════════════════════════════════════════════════════
        # CHAT MODE
        # ════════════════════════════════════════════════════════════════════
        user_text = runtime.listen_text(max_wait_seconds=CHAT_IDLE_TO_PRESENCE_SEC)
        if not user_text:
            runtime.speak_and_cooldown(_generate_mode_line(state, memory, "chat_to_presence"))
            mode = "presence"
            next_chime_at = time.time() + _next_chime_delay(state)
            continue

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
            runtime.speak_and_cooldown(_generate_mode_line(state, memory, "chat_to_presence"))
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
                reply = f"Tried to look but it crashed: {exc}"
        else:
            reply = _generate_chat_reply(state, memory, user_text, text_norm)
            memory.add_user(user_text)

        memory.add_assistant(reply)
        print(f"Ardomis: {reply}")
        runtime.speak_and_cooldown(reply)
