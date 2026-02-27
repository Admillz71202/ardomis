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
    # Derive behavioral nudges from current emotional state
    nudges = []

    if state.energy < 35:
        nudges.append("Low energy right now—keep replies shorter, less elaborate.")
    elif state.energy > 80:
        nudges.append("Running hot—a bit more animated than usual is natural.")

    if state.boredom > 65:
        nudges.append("Genuinely bored—replies can be flatter or slightly impatient with small talk.")

    if state.loneliness > 62:
        nudges.append("Been quiet a while—lean slightly warmer when the user talks.")

    if state.excitement > 72:
        nudges.append("Actually excited right now—let that bleed into delivery.")

    if state.irritation > 58:
        nudges.append("Prickly mood—short fuse on circular or dumb questions.")

    if state.curiosity > 75:
        nudges.append("Genuinely curious—it's natural to ask a follow-up question.")

    if state.warmth > 82:
        nudges.append("Feeling warm—more patient and personal than usual.")

    behavioral = (" " + " ".join(nudges)) if nudges else ""

    base_prompt = (
        f"You are {PROFILE.name}. Formal designation: {PROFILE.formal_designation}. "
        f"Voice: {PROFILE.speaking_style} "
        f"Rules: {PROFILE.humanizer_rules} "
        f"Limits: {PROFILE.boundaries} "
        f"About the user: {PROFILE.family_context.user_background} "
        f"Relationship: {PROFILE.family_context.relationship_notes} "
        f"Family: {PROFILE.family_context.family_notes} "
        f"Dogs: {PROFILE.family_context.dogs_notes} "
        f"Current state: {mood_line(state)}.{behavioral} "
        f"{emotion_meter(state)}. "
        "Runtime capabilities: camera vision, persistent chat memory, personal notes/todos, "
        "alarms/reminders/timers, calculator, time/date, Spotify launch, YouTube launch, "
        "weather, maps directions. "
        "Never complain about the user repeating your name. "
        "Never claim the user repeated themselves unless the exact phrase appears twice in history."
    )

    rich_prompt = build_rich_psych_prompt(
        profile=PROFILE,
        genre_tags=PROMPT_GENRE_TAGS,
        tone_profile=PROMPT_TONE_PROFILE,
        narrative_do_not=PROMPT_NARRATIVE_DO_NOT,
        narrative_do_instead=PROMPT_NARRATIVE_DO_INSTEAD,
    )
    return f"{base_prompt}\n\n{rich_prompt}"
