from ardomis_app.core.emotion import EmotionState, emotion_meter, mood_line
from ardomis_app.core.profile import PROFILE
from ardomis_app.app.prompt_profiles import build_rich_psych_prompt
from ardomis_app.config.settings import (
    PROMPT_GENRE_TAGS,
    PROMPT_NARRATIVE_DO_INSTEAD,
    PROMPT_NARRATIVE_DO_NOT,
    PROMPT_TONE_PROFILE,
)


def build_system_prompt(state: EmotionState) -> str:
    base_prompt = (
        f"You are {PROFILE.name}. Your formal designation is {PROFILE.formal_designation}. "
        f"Voice and style: {PROFILE.speaking_style} "
        f"Humanizer rules: {PROFILE.humanizer_rules} "
        f"Behavior boundaries: {PROFILE.boundaries} "
        f"Relational context: {PROFILE.family_context.user_background} "
        f"Relationship context: {PROFILE.family_context.relationship_notes} "
        f"Family context: {PROFILE.family_context.family_notes} "
        f"Dogs context: {PROFILE.family_context.dogs_notes} "
        f"Current internal state summary: {mood_line(state)}. "
        f"Detailed internal state: {emotion_meter(state)}. "
        "Capabilities available in runtime: camera vision, persistent chat memory, persistent notes/todos, alarms/reminders/timers, quick calculator, system/time checks, Spotify/YouTube launch intents, weather lookups, and maps directions launch. "
        "Never complain about the user repeating your name. "
        "Never claim the user said something twice unless the EXACT same phrase appears twice in provided history."
    )

    rich_prompt = build_rich_psych_prompt(
        profile=PROFILE,
        genre_tags=PROMPT_GENRE_TAGS,
        tone_profile=PROMPT_TONE_PROFILE,
        narrative_do_not=PROMPT_NARRATIVE_DO_NOT,
        narrative_do_instead=PROMPT_NARRATIVE_DO_INSTEAD,
    )
    return f"{base_prompt}\n\n{rich_prompt}"
