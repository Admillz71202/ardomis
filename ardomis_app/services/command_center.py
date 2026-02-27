# ─────────────────────────────────────────────────────────────────────────────
# command_center.py — fast-path command dispatch (no LLM needed)
#
# HOW TO ADD A NEW COMMAND
# ────────────────────────
# 1. Find the sub-handler method that fits your category
#    (volume, time/calc, media, scheduler, notes) — or add a new one.
# 2. Inside that method, add your match condition and return:
#       return CommandResult(True, "spoken response here")
#    Return None at the end of the method if the input didn't match.
# 3. If your command should switch Ardomis back to presence mode
#    (e.g. launching an app), add:  next_mode="presence"
# 4. Register a new sub-handler in handle() if you created a new method.
#
# EXAMPLE — add "flip a coin":
#   In _handle_utility(), before `return None`:
#       import random
#       if text_norm == "flip a coin":
#           return CommandResult(True, random.choice(("heads", "tails")))
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass

from ardomis_app.services.audio_io import get_output_volume, set_output_volume
from ardomis_app.services.integration_service import (
    open_maps_directions,
    open_spotify,
    open_youtube,
    weather_report,
)
from ardomis_app.services.knowledge_vault import KnowledgeVault
from ardomis_app.services.scheduler_service import SchedulerService
from ardomis_app.services.time_service import current_time_line
from ardomis_app.services.utility_service import calculate, system_snapshot


# ── Word-to-number map for spoken timer amounts ("set a timer for five minutes") ──
_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
}


def _parse_number_token(token: str) -> int | None:
    """Parse a single word or digit token into an int, or return None."""
    value = (token or "").strip().lower()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if value in _NUM_WORDS:
        return _NUM_WORDS[value]
    # handle "twenty-one" style compounds
    if "-" in value:
        parts = [p for p in value.split("-") if p]
        if len(parts) == 2 and all(p in _NUM_WORDS for p in parts):
            return _NUM_WORDS[parts[0]] + _NUM_WORDS[parts[1]]
    return None


@dataclass
class CommandResult:
    handled:   bool
    response:  str       = ""
    next_mode: str | None = None  # set to "presence" if the command should fade Ardomis out


class CommandCenter:
    def __init__(
        self,
        vault:                KnowledgeVault,
        scheduler:            SchedulerService,
        timezone_name:        str,
        spotify_access_token: str = "",
        youtube_api_key:      str = "",
    ):
        self.vault                = vault
        self.scheduler            = scheduler
        self.timezone_name        = timezone_name
        self.spotify_access_token = spotify_access_token
        self.youtube_api_key      = youtube_api_key

    # ── Query extractors (used by _handle_media) ──────────────────────────────

    @staticmethod
    def _extract_spotify_query(raw_text: str) -> str:
        """Pull the search term out of a Spotify command."""
        patterns = [
            r"^open\s+spotify\s+and\s+play\s+(.+)$",
            r"^play\s+(.+?)\s+on\s+spotify$",
            r"^(?:play\s+music|play|spotify|put on|throw on|blast|queue up)\s+(.+)$",
        ]
        for p in patterns:
            m = re.match(p, raw_text.strip(), flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    @staticmethod
    def _extract_youtube_query(raw_text: str) -> str:
        """Pull the search term out of a YouTube command."""
        patterns = [
            r"^open\s+youtube\s+and\s+play\s+(.+)$",
            r"^play\s+(.+?)\s+on\s+youtube$",
            r"^(?:pull up|look up|find)\s+(.+?)\s+on\s+youtube$",
            r"^(?:watch|youtube|play\s+video|pull up|look up)\s+(.+)$",
        ]
        for p in patterns:
            m = re.match(p, raw_text.strip(), flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    # ── Main dispatch ─────────────────────────────────────────────────────────

    def handle(self, text_norm: str, raw_text: str) -> CommandResult:
        """
        Try each command category in order. First match wins.
        Returns CommandResult(handled=False) if nothing matched — caller
        should then send the input to the LLM.
        """
        result = (
            self._handle_help(text_norm)
            or self._handle_volume(text_norm)
            or self._handle_time_and_calc(text_norm, raw_text)
            or self._handle_media(text_norm, raw_text)
            or self._handle_scheduler(text_norm)
            or self._handle_notes(text_norm, raw_text)
        )
        return result or CommandResult(False, "")

    # ── Sub-handlers (each returns CommandResult or None) ─────────────────────

    def _handle_help(self, text_norm: str) -> CommandResult | None:
        _HELP_PHRASES = {
            "help", "commands", "what can you do", "capabilities",
            "list me your commands", "what are your commands", "show commands",
        }
        if text_norm not in _HELP_PHRASES:
            return None
        return CommandResult(True, (
            "Commands: time | calc <expr> | volume <0-100> | mute | unmute | "
            "turn up/down the volume | play/put on/throw on <song> | "
            "watch/pull up <video> | weather in <city> | directions to <place> | "
            "remember/jot down <note> | show notes | todo/add task <task> | show todos | "
            "done #<id> | set timer <n> minutes/seconds for <note> | "
            "remind me in <n> minutes to <note> | set alarm HH:MM for <note> | "
            "show schedule | system snapshot | mood check | state dump."
        ))

    def _handle_volume(self, text_norm: str) -> CommandResult | None:
        # ── Mute / unmute ─────────────────────────────────────────────────────
        if text_norm in {"mute", "silence", "go mute", "mute yourself"}:
            ok, msg = set_output_volume(0)
            return CommandResult(True, "Muted." if ok else msg)

        if text_norm in {"unmute", "unmute yourself", "unsilence"}:
            ok, msg = set_output_volume(60)
            return CommandResult(True, "Back." if ok else msg)

        # ── Turn up / down ────────────────────────────────────────────────────
        if re.match(r"^turn up(?:\s+the)?\s+volume$", text_norm):
            ok, msg = set_output_volume(80)
            return CommandResult(True, msg if ok else "Couldn't turn it up.")

        if re.match(r"^turn down(?:\s+the)?\s+volume$", text_norm):
            ok, msg = set_output_volume(40)
            return CommandResult(True, msg if ok else "Couldn't turn it down.")

        # ── Query current volume ──────────────────────────────────────────────
        if text_norm in {"what's the volume", "whats the volume", "current volume", "volume status", "volume"}:
            return CommandResult(True, get_output_volume())

        # ── Set volume to exact level: "volume 70" or "set volume 70" ─────────
        m = re.match(r"^(?:set\s+)?volume\s+(\d{1,3})$", text_norm)
        if m:
            level = int(m.group(1))
            if not 0 <= level <= 100:
                return CommandResult(True, "Give me a number between 0 and 100.")
            ok, msg = set_output_volume(level)
            return CommandResult(True, msg if ok else f"{msg} (requested {level}%)")

        return None

    def _handle_time_and_calc(self, text_norm: str, raw_text: str) -> CommandResult | None:
        # ── Time ──────────────────────────────────────────────────────────────
        if ("what time" in text_norm) or text_norm in {"time", "current time", "what time is it"}:
            return CommandResult(True, current_time_line(self.timezone_name))

        # ── Calculator: "calc 12 * 4" or "calculate ..." ──────────────────────
        if text_norm.startswith("calc ") or text_norm.startswith("calculate "):
            expr = raw_text.split(" ", 1)[1] if " " in raw_text else ""
            try:
                return CommandResult(True, f"That's {calculate(expr)}.")
            except Exception as exc:
                return CommandResult(True, f"Math blew up: {exc}")

        # ── System info ───────────────────────────────────────────────────────
        if text_norm in {"system", "system status", "system snapshot"}:
            return CommandResult(True, system_snapshot())

        return None

    def _handle_media(self, text_norm: str, raw_text: str) -> CommandResult | None:
        # ── YouTube ───────────────────────────────────────────────────────────
        # Triggers: "watch X", "youtube X", "pull up X", "play X on youtube", etc.
        if re.match(
            r"^(?:watch|youtube|play video|pull up|look up)(?:\s+.+)?$"
            r"|^play\s+.+?\s+on\s+youtube$"
            r"|^open\s+youtube\s+and\s+play\s+.+$"
            r"|^(?:pull up|look up|find)\s+.+?\s+on\s+youtube$",
            raw_text.strip(), flags=re.IGNORECASE,
        ):
            query = self._extract_youtube_query(raw_text)
            result = open_youtube(query=query, api_key=self.youtube_api_key)
            return CommandResult(True, result.message, next_mode="presence" if result.ok else None)

        # ── Spotify ───────────────────────────────────────────────────────────
        # Triggers: "play X", "put on X", "throw on X", "blast X", "play X on spotify", etc.
        if re.match(
            r"^(?:play|spotify|play music|put on|throw on|blast|queue up)(?:\s+.+)?$"
            r"|^play\s+.+?\s+on\s+spotify$"
            r"|^open\s+spotify\s+and\s+play\s+.+$",
            raw_text.strip(), flags=re.IGNORECASE,
        ):
            query = self._extract_spotify_query(raw_text)
            result = open_spotify(query=query, access_token=self.spotify_access_token)
            return CommandResult(True, result.message, next_mode="presence" if result.ok else None)

        # ── Weather ───────────────────────────────────────────────────────────
        m = re.match(r"^(?:weather)(?:\s+(?:in|for))?\s*(.*)$", raw_text.strip(), flags=re.IGNORECASE)
        if m:
            result = weather_report((m.group(1) or "").strip())
            return CommandResult(True, result.message)

        # ── Maps / directions ─────────────────────────────────────────────────
        m = re.match(
            r"^(?:directions|navigate|maps?|route)(?:\s+(?:to|for))?\s+(.+)$",
            raw_text.strip(), flags=re.IGNORECASE,
        )
        if m:
            result = open_maps_directions(m.group(1).strip())
            return CommandResult(True, result.message, next_mode="presence" if result.ok else None)

        return None

    def _handle_scheduler(self, text_norm: str) -> CommandResult | None:
        # ── Timer: "set timer 5 minutes for pasta" ────────────────────────────
        m = re.match(r"^set timer (\d+) (second|seconds|minute|minutes)(?: for (.+))?$", text_norm)
        if m:
            qty, unit, note = int(m.group(1)), m.group(2), (m.group(3) or "timer done").strip()
            seconds = qty * 60 if "minute" in unit else qty
            tid, _ = self.scheduler.add_timer(seconds, note)
            return CommandResult(True, f"Timer #{tid} set for {qty} {unit}: {note}")

        # ── Timer with word numbers: "set a timer for five minutes" ──────────
        m = re.match(
            r"^set (?:a )?timer(?: for)?\s+([a-z0-9-]+)\s+(second|seconds|minute|minutes)(?:\s+for\s+(.+))?$",
            text_norm,
        )
        if m:
            qty = _parse_number_token(m.group(1))
            unit, note = m.group(2), (m.group(3) or "timer done").strip()
            if qty is None:
                return CommandResult(True, "Couldn't parse that number. Try 'set timer 5 minutes'.")
            seconds = qty * 60 if "minute" in unit else qty
            tid, _ = self.scheduler.add_timer(seconds, note)
            return CommandResult(True, f"Timer #{tid} set for {qty} {unit}: {note}")

        # ── Reminder in N minutes: "remind me in 10 minutes to call mom" ──────
        m = re.match(r"^remind me in (\d+) (minute|minutes) to (.+)$", text_norm)
        if m:
            mins, note = int(m.group(1)), m.group(3).strip()
            rid, _ = self.scheduler.add_reminder_in_minutes(mins, note)
            return CommandResult(True, f"Reminder #{rid} in {mins} minutes: {note}")

        # ── Alarm at time: "set alarm 14:30 for standup" ─────────────────────
        m = re.match(r"^set alarm (\d{1,2}:\d{2})(?: for (.+))?$", text_norm)
        if m:
            hhmm, label = m.group(1), (m.group(2) or "alarm").strip()
            try:
                aid, _ = self.scheduler.add_alarm_hhmm(hhmm, label)
                return CommandResult(True, f"Alarm #{aid} set for {hhmm}: {label}")
            except Exception as exc:
                return CommandResult(True, f"Couldn't set alarm: {exc}")

        # ── Reminder at datetime: "remind me at 2025-12-25 09:00 to open presents" ──
        m = re.match(r"^remind me at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) to (.+)$", text_norm)
        if m:
            when_local, note = m.group(1), m.group(2).strip()
            try:
                rid, _ = self.scheduler.add_reminder_at_iso(when_local, note)
                return CommandResult(True, f"Reminder #{rid} at {when_local}: {note}")
            except Exception as exc:
                return CommandResult(True, f"Couldn't set that: {exc}")

        # ── List pending schedule ─────────────────────────────────────────────
        if text_norm in {"show reminders", "show alarms", "show timers", "schedule", "show schedule"}:
            items = self.scheduler.list_pending(limit=12)
            if not items:
                return CommandResult(True, "Nothing pending.")
            out = "; ".join(f"#{i.item_id} [{i.kind}] {i.text}" for i in items)
            return CommandResult(True, out)

        return None

    def _handle_notes(self, text_norm: str, raw_text: str) -> CommandResult | None:
        # ── Save a note ───────────────────────────────────────────────────────
        m = re.match(
            r"^(remember|note|jot down|jot|write down|save note|make a note)\s+(.+)$",
            raw_text.strip(), flags=re.IGNORECASE,
        )
        if m:
            content = m.group(2).strip()
            nid = self.vault.add_note(content)
            return CommandResult(True, f"Saved note #{nid}: {content}")

        # ── List notes ────────────────────────────────────────────────────────
        if text_norm in {"show notes", "list notes", "notes"}:
            notes = self.vault.list_notes(limit=8)
            if not notes:
                return CommandResult(True, "No notes yet.")
            return CommandResult(True, "; ".join(f"#{nid}: {content}" for nid, content in notes))

        # ── Add a todo ────────────────────────────────────────────────────────
        m = re.match(
            r"^(todo|task|add task|add to my list|add to list)\s+(.+)$",
            raw_text.strip(), flags=re.IGNORECASE,
        )
        if m:
            content = m.group(2).strip()
            tid = self.vault.add_todo(content)
            return CommandResult(True, f"Added todo #{tid}: {content}")

        # ── Mark a todo done: "done #3" or "complete 3" ───────────────────────
        m = re.match(r"^(done|complete)\s+#?(\d+)$", text_norm)
        if m:
            tid = int(m.group(2))
            ok = self.vault.complete_todo(tid)
            return CommandResult(True, f"Done #{tid}." if ok else f"Couldn't find todo #{tid}.")

        # ── List todos ────────────────────────────────────────────────────────
        if text_norm in {"show todos", "list todos", "todos"}:
            todos = self.vault.list_todos(include_done=False, limit=10)
            if not todos:
                return CommandResult(True, "No open todos.")
            return CommandResult(True, "; ".join(f"#{tid}: {content}" for tid, content, _ in todos))

        return None
