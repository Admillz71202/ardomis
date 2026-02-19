"""
Scheduler Test Harness
======================
This file is intentionally simple and heavily commented so you can quickly test
alarms/reminders/timers behavior without running the full voice loop.

How to run:
    python scripts/scheduler_test_harness.py

What it does:
1) Creates an isolated temporary SQLite db.
2) Sets a short timer and a short reminder.
3) Polls due events in a loop and prints when they fire.
4) Shows pending schedule items and a sample alarm creation.
"""

import tempfile
import time
from pathlib import Path
import sys

# Make repo root importable when this file is run directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ardomis_app.services.scheduler_service import SchedulerService


def main() -> None:
    # Use a temp DB so this test doesn't touch your real runtime data.
    with tempfile.TemporaryDirectory() as td:
        db_path = f"{td}/test_memory.db"
        scheduler = SchedulerService(db_path=db_path, timezone_name="America/New_York")

        # 1) Timer test: should fire quickly.
        timer_id, _ = scheduler.add_timer(2, "stretch your legs")
        print(f"Timer created: #{timer_id}")

        # 2) Reminder-in test: 1 minute (longer), used to validate persistence/listing.
        reminder_id, _ = scheduler.add_reminder_in_minutes(1, "check build status")
        print(f"Reminder created: #{reminder_id}")

        # 3) Alarm test: sample next-day HH:MM local-time alarm.
        alarm_id, _ = scheduler.add_alarm_hhmm("23:59", "night shutdown check")
        print(f"Alarm created: #{alarm_id}")

        print("Polling due events for ~5 seconds...")
        started = time.time()
        while time.time() - started < 5:
            due = scheduler.due_items()
            for item in due:
                print(f"FIRED -> #{item.item_id} [{item.kind}] {item.text}")
            time.sleep(0.5)

        # 4) Show what's still pending after timer firing.
        pending = scheduler.list_pending(limit=10)
        print("Pending:")
        for item in pending:
            print(f"  #{item.item_id} [{item.kind}] {item.text}")


if __name__ == "__main__":
    main()
