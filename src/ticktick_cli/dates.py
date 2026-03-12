"""Natural language date parsing — zero dependencies.

Supports:
  today, tomorrow, yesterday
  monday, tuesday, ..., sunday (next occurrence)
  next monday, next friday, this friday
  +3d, +1w, +2m (relative offsets: days/weeks/months)
  -2d (past offsets)
  YYYY-MM-DD (ISO date)
  YYYY-MM-DDTHH:MM:SS (ISO datetime)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_TICKTICK_FMT = "%Y-%m-%dT%H:%M:%S.000+0000"

_WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_RELATIVE_RE = re.compile(r"^([+-]?)(\d+)([dwm])$")


def parse_date(date_str: str) -> str:
    """Parse a human-friendly date string into TickTick's date format.

    Returns ISO-ish string: ``YYYY-MM-DDT00:00:00.000+0000``

    Raises ``ValueError`` if the string cannot be parsed.
    """
    now = datetime.now()
    token = date_str.strip().lower()

    # -- Aliases --------------------------------------------------------
    if token == "today":
        return _fmt(now)
    if token == "tomorrow":
        return _fmt(now + timedelta(days=1))
    if token == "yesterday":
        return _fmt(now - timedelta(days=1))

    # -- Relative offsets: +3d, +1w, +2m, -2d --------------------------
    m = _RELATIVE_RE.match(token)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        amount = int(m.group(2))
        unit = m.group(3)
        if unit == "d":
            return _fmt(now + timedelta(days=sign * amount))
        if unit == "w":
            return _fmt(now + timedelta(weeks=sign * amount))
        if unit == "m":
            # Approximate month offset
            return _fmt(_add_months(now, sign * amount))
        raise ValueError(f"Unknown offset unit: {unit}")  # pragma: no cover

    # -- "next <weekday>" / "this <weekday>" / bare weekday -------------
    for prefix in ("next ", "this "):
        if token.startswith(prefix):
            day_name = token[len(prefix) :].strip()
            if day_name in _WEEKDAYS:
                return _fmt(_next_weekday(now, _WEEKDAYS[day_name]))

    if token in _WEEKDAYS:
        return _fmt(_next_weekday(now, _WEEKDAYS[token]))

    # -- "end of week" / "end of month" --------------------------------
    if token in ("eow", "end of week"):
        # Sunday of this week
        days_until_sun = (6 - now.weekday()) % 7
        if days_until_sun == 0:
            days_until_sun = 7
        return _fmt(now + timedelta(days=days_until_sun))
    if token in ("eom", "end of month"):
        return _fmt(_end_of_month(now))

    # -- ISO date / datetime fallback -----------------------------------
    try:
        dt = datetime.fromisoformat(date_str.strip())
        return dt.strftime(_TICKTICK_FMT)
    except ValueError:
        pass

    raise ValueError(
        f"Cannot parse date: '{date_str}'. "
        "Try: today, tomorrow, monday, +3d, +1w, +2m, or YYYY-MM-DD"
    )


# ── helpers ──────────────────────────────────────────────────


def _fmt(dt: datetime) -> str:
    """Format datetime to TickTick's expected format (midnight)."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0).strftime(_TICKTICK_FMT)


def _next_weekday(now: datetime, target_weekday: int) -> datetime:
    """Return the next occurrence of the given weekday (0=Monday)."""
    days_ahead = target_weekday - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return now + timedelta(days=days_ahead)


def _add_months(dt: datetime, months: int) -> datetime:
    """Add *months* to *dt*, clamping day to valid range."""
    import calendar

    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _end_of_month(dt: datetime) -> datetime:
    """Return the last day of *dt*'s month."""
    import calendar

    last_day = calendar.monthrange(dt.year, dt.month)[1]
    return dt.replace(day=last_day)
