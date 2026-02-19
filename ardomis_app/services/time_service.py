from datetime import datetime
from zoneinfo import ZoneInfo


def current_time_line(timezone_name: str) -> str:
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:
        zone = ZoneInfo("America/New_York")
        timezone_name = "America/New_York"

    now = datetime.now(zone)
    return f"It is {now.strftime('%I:%M %p')} on {now.strftime('%A, %B %d, %Y')} ({timezone_name})."
