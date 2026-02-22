from __future__ import annotations

import re
from dataclasses import dataclass

from ardomis_app.services.audio_io import get_output_volume, set_output_volume
from ardomis_app.services.integration_service import open_maps_directions, open_spotify, open_youtube, weather_report
from ardomis_app.services.knowledge_vault import KnowledgeVault
from ardomis_app.services.scheduler_service import SchedulerService
from ardomis_app.services.time_service import current_time_line
from ardomis_app.services.utility_service import calculate, system_snapshot


_NUM_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
}


def _parse_number_token(token: str) -> int | None:
    value = (token or "").strip().lower()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if value in _NUM_WORDS:
        return _NUM_WORDS[value]
    if "-" in value:
        parts = [p for p in value.split("-") if p]
        if len(parts) == 2 and all(p in _NUM_WORDS for p in parts):
            return _NUM_WORDS[parts[0]] + _NUM_WORDS[parts[1]]
    return None


@dataclass
class CommandResult:
    handled: bool
    response: str = ""
    next_mode: str | None = None


class CommandCenter:
    def __init__(
        self,
        vault: KnowledgeVault,
        scheduler: SchedulerService,
        timezone_name: str,
        spotify_access_token: str = "",
        youtube_api_key: str = "",
    ):
        self.vault = vault
        self.scheduler = scheduler
        self.timezone_name = timezone_name
        self.spotify_access_token = spotify_access_token
        self.youtube_api_key = youtube_api_key

    @staticmethod
    def _extract_spotify_query(raw_text: str) -> str:
        text = (raw_text or "").strip()
        patterns = [
            r"^open\s+spotify\s+and\s+play\s+(.+)$",
            r"^play\s+(.+?)\s+on\s+spotify$",
            r"^(?:play\s+music|play|spotify)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_youtube_query(raw_text: str) -> str:
        text = (raw_text or "").strip()
        patterns = [
            r"^open\s+youtube\s+and\s+play\s+(.+)$",
            r"^play\s+(.+?)\s+on\s+youtube$",
            r"^(?:watch|youtube|play\s+video)\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def handle(self, text_norm: str, raw_text: str) -> CommandResult:
        if text_norm in {"help", "commands", "what can you do", "capabilities", "list me your commands", "what are your commands", "show commands"}:
            return CommandResult(
                True,
                "Quick commands: time | calc <expr> | volume <0-100> | what's the volume | remember <note> | show notes | todo <task> | show todos | set timer <n> seconds/minutes for <note> | remind me in <n> minutes to <note> | set alarm HH:MM for <note> | remind me at YYYY-MM-DD HH:MM to <note> | show schedule | play music <song> | watch <video> | weather in <city> | directions to <place> | say 'actually shut up' to reduce interruptions | say 'im being serious' for serious mode | system snapshot.",
            )

        if text_norm in {"what's the volume", "whats the volume", "current volume", "volume status", "volume"}:
            return CommandResult(True, get_output_volume())

        volume_match = re.match(r"^(?:set\s+)?volume\s+(\d{1,3})$", text_norm)
        if volume_match:
            level = int(volume_match.group(1))
            if level < 0 or level > 100:
                return CommandResult(True, "Give me a volume between 0 and 100.")
            ok, msg = set_output_volume(level)
            return CommandResult(True, msg if ok else f"{msg} Requested level was {level}%.")

        if ("what time" in text_norm) or (text_norm in {"time", "current time", "what time is it"}):
            return CommandResult(True, current_time_line(self.timezone_name))

        if text_norm.startswith("calc ") or text_norm.startswith("calculate "):
            expr = raw_text.split(" ", 1)[1] if " " in raw_text else ""
            try:
                return CommandResult(True, f"That comes out to {calculate(expr)}.")
            except Exception as exc:
                return CommandResult(True, f"Math blew up: {exc}")

        if text_norm in {"system", "system status", "system snapshot"}:
            return CommandResult(True, system_snapshot())

        youtube_match = re.match(
            r"^(?:watch|youtube|play video)(?:\s+(.+))?$|^play\s+(.+?)\s+on\s+youtube$|^open\s+youtube\s+and\s+play\s+(.+)$",
            raw_text.strip(),
            flags=re.IGNORECASE,
        )
        if youtube_match:
            query = self._extract_youtube_query(raw_text)
            result = open_youtube(query=query, api_key=self.youtube_api_key)
            return CommandResult(True, result.message, next_mode="presence" if result.ok else None)

        spotify_match = re.match(
            r"^(?:play|spotify|play music)(?:\s+(.+))?$|^play\s+(.+?)\s+on\s+spotify$|^open\s+spotify\s+and\s+play\s+(.+)$",
            raw_text.strip(),
            flags=re.IGNORECASE,
        )
        if spotify_match:
            query = self._extract_spotify_query(raw_text)
            result = open_spotify(query=query, access_token=self.spotify_access_token)
            return CommandResult(True, result.message, next_mode="presence" if result.ok else None)

        weather_match = re.match(r"^(?:weather)(?:\s+(?:in|for))?\s*(.*)$", raw_text.strip(), flags=re.IGNORECASE)
        if weather_match:
            location = (weather_match.group(1) or "").strip()
            result = weather_report(location)
            return CommandResult(True, result.message)

        directions_match = re.match(
            r"^(?:directions|navigate|maps?|route)(?:\s+(?:to|for))?\s+(.+)$",
            raw_text.strip(),
            flags=re.IGNORECASE,
        )
        if directions_match:
            destination = directions_match.group(1).strip()
            result = open_maps_directions(destination)
            return CommandResult(True, result.message, next_mode="presence" if result.ok else None)

        timer_match = re.match(r"^set timer (\d+) (second|seconds|minute|minutes)(?: for (.+))?$", text_norm)
        if timer_match:
            qty = int(timer_match.group(1))
            unit = timer_match.group(2)
            note = (timer_match.group(3) or "timer done").strip()
            seconds = qty * 60 if "minute" in unit else qty
            tid, _ = self.scheduler.add_timer(seconds, note)
            return CommandResult(True, f"Timer #{tid} set for {qty} {unit}. I will remind you: {note}")

        timer_natural = re.match(
            r"^set (?:a )?timer(?: for)?\s+([a-z0-9-]+)\s+(second|seconds|minute|minutes)(?:\s+for\s+(.+))?$",
            text_norm,
        )
        if timer_natural:
            qty = _parse_number_token(timer_natural.group(1))
            unit = timer_natural.group(2)
            note = (timer_natural.group(3) or "timer done").strip()
            if qty is None:
                return CommandResult(True, "I couldn't parse that timer amount. Try a number like 1 minute.")
            seconds = qty * 60 if "minute" in unit else qty
            tid, _ = self.scheduler.add_timer(seconds, note)
            return CommandResult(True, f"Timer #{tid} set for {qty} {unit}. I will remind you: {note}")

        reminder_in = re.match(r"^remind me in (\d+) (minute|minutes) to (.+)$", text_norm)
        if reminder_in:
            mins = int(reminder_in.group(1))
            note = reminder_in.group(3).strip()
            rid, _ = self.scheduler.add_reminder_in_minutes(mins, note)
            return CommandResult(True, f"Reminder #{rid} set for {mins} minutes from now: {note}")

        alarm_match = re.match(r"^set alarm (\d{1,2}:\d{2})(?: for (.+))?$", text_norm)
        if alarm_match:
            hhmm = alarm_match.group(1)
            label = (alarm_match.group(2) or "alarm").strip()
            try:
                aid, _ = self.scheduler.add_alarm_hhmm(hhmm, label)
                return CommandResult(True, f"Alarm #{aid} set for {hhmm} ({self.timezone_name}) with note: {label}")
            except Exception as exc:
                return CommandResult(True, f"Couldn't set alarm: {exc}")

        reminder_at = re.match(r"^remind me at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) to (.+)$", text_norm)
        if reminder_at:
            when_local = reminder_at.group(1)
            note = reminder_at.group(2).strip()
            try:
                rid, _ = self.scheduler.add_reminder_at_iso(when_local, note)
                return CommandResult(True, f"Reminder #{rid} set for {when_local} ({self.timezone_name}): {note}")
            except Exception as exc:
                return CommandResult(True, f"Couldn't set that reminder: {exc}")

        if text_norm in {"show reminders", "show alarms", "show timers", "schedule", "show schedule"}:
            items = self.scheduler.list_pending(limit=12)
            if not items:
                return CommandResult(True, "No pending alarms, reminders, or timers.")
            out = "; ".join([f"#{i.item_id} [{i.kind}] {i.text}" for i in items])
            return CommandResult(True, out)

        note_match = re.match(r"^(remember|note)\s+(.+)$", raw_text.strip(), flags=re.IGNORECASE)
        if note_match:
            content = note_match.group(2).strip()
            note_id = self.vault.add_note(content)
            return CommandResult(True, f"Saved note #{note_id}: {content}")

        if text_norm in {"show notes", "list notes", "notes"}:
            notes = self.vault.list_notes(limit=8)
            if not notes:
                return CommandResult(True, "No notes saved yet.")
            out = "; ".join([f"#{nid}: {content}" for nid, content in notes])
            return CommandResult(True, out)

        todo_match = re.match(r"^(todo|task)\s+(.+)$", raw_text.strip(), flags=re.IGNORECASE)
        if todo_match:
            content = todo_match.group(2).strip()
            tid = self.vault.add_todo(content)
            return CommandResult(True, f"Added todo #{tid}: {content}")

        done_match = re.match(r"^(done|complete)\s+#?(\d+)$", text_norm)
        if done_match:
            tid = int(done_match.group(2))
            ok = self.vault.complete_todo(tid)
            return CommandResult(True, f"Marked todo #{tid} complete." if ok else f"Couldn't find todo #{tid}.")

        if text_norm in {"show todos", "list todos", "todos"}:
            todos = self.vault.list_todos(include_done=False, limit=10)
            if not todos:
                return CommandResult(True, "No open todos.")
            out = "; ".join([f"#{tid}: {content}" for tid, content, _ in todos])
            return CommandResult(True, out)

        return CommandResult(False, "")
