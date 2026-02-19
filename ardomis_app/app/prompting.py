from ardomis_app.core.emotion import EmotionState, emotion_meter, mood_line
from ardomis_app.core.profile import PROFILE


def build_system_prompt(state: EmotionState) -> str:
    return (
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
        "Capabilities available in runtime: camera vision, persistent chat memory, persistent notes/todos, alarms/reminders/timers, quick calculator, and system/time checks. "
        "Never complain about the user repeating your name. "
        "Never claim the user said something twice unless the EXACT same phrase appears twice in provided history."
    )
