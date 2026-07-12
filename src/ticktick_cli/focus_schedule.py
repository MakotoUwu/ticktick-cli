"""Pure scheduling helpers for timed TickTick focus sessions."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from math import ceil
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MIN_FOCUS_MINUTES = 5
MAX_FOCUS_MINUTES = 180


def parse_task_datetime(value: str | None, time_zone: str | None = None) -> datetime | None:
    """Parse a TickTick task timestamp, preserving its explicit offset."""

    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed
    try:
        task_zone = ZoneInfo(time_zone) if time_zone else timezone.utc
    except ZoneInfoNotFoundError:
        task_zone = timezone.utc
    return parsed.replace(tzinfo=task_zone)


def scheduled_focus_plan(
    task: dict[str, Any],
    *,
    now: datetime | None = None,
    require_active: bool = True,
    min_minutes: int = MIN_FOCUS_MINUTES,
    max_minutes: int = MAX_FOCUS_MINUTES,
) -> dict[str, Any] | None:
    """Return a focus plan for a positive-length timed task."""

    status = task.get("status", 0)
    if status not in (0, "0", "active", "uncompleted") or task.get("isAllDay"):
        return None
    task_id = str(task.get("id") or task.get("ticktickId") or "").strip()
    if not task_id:
        return None

    start = parse_task_datetime(task.get("startDate"), task.get("timeZone"))
    end = parse_task_datetime(task.get("dueDate"), task.get("timeZone"))
    if not start or not end or end <= start:
        return None

    check_time = now or datetime.now(timezone.utc)
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=timezone.utc)
    check_time = check_time.astimezone(start.tzinfo)
    if require_active and not (start <= check_time < end):
        return None
    if not require_active and check_time >= end:
        return None

    effective_start = max(check_time, start)
    remaining_seconds = (end - effective_start).total_seconds()
    if remaining_seconds < min_minutes * 60:
        return None

    scheduled_minutes = ceil((end - start).total_seconds() / 60)
    remaining_minutes = ceil(remaining_seconds / 60)
    focus_minutes = min(max_minutes, remaining_minutes)
    duration_source = "scheduled_window"
    if check_time > start and (check_time - start).total_seconds() >= 60:
        duration_source = "scheduled_remaining"

    return {
        "attemptKey": f"{task_id}:{start.isoformat()}",
        "taskId": task_id,
        "title": str(task.get("title") or task.get("text") or "TickTick task"),
        "scheduledStart": start.isoformat(),
        "scheduledEnd": end.isoformat(),
        "scheduledDurationMinutes": scheduled_minutes,
        "remainingScheduledMinutes": remaining_minutes,
        "focusMinutes": focus_minutes,
        "durationSource": duration_source,
        "priority": int(task.get("priority") or 0),
    }


def select_scheduled_focus(
    tasks: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    attempted_keys: Iterable[str] = (),
) -> dict[str, Any] | None:
    """Select the most recently started active task that has not run yet."""

    attempted = set(attempted_keys)
    candidates = [
        plan
        for task in tasks
        if (plan := scheduled_focus_plan(task, now=now)) and plan["attemptKey"] not in attempted
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda plan: (plan["scheduledStart"], plan["priority"]),
    )


def next_scheduled_focus(
    tasks: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    attempted_keys: Iterable[str] = (),
) -> dict[str, Any] | None:
    """Return the next future timed task for status displays."""

    check_time = now or datetime.now(timezone.utc)
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=timezone.utc)
    attempted = set(attempted_keys)
    candidates: list[dict[str, Any]] = []
    for task in tasks:
        plan = scheduled_focus_plan(task, now=check_time, require_active=False)
        if not plan or plan["attemptKey"] in attempted:
            continue
        start = parse_task_datetime(plan["scheduledStart"])
        if start and start > check_time.astimezone(start.tzinfo):
            candidates.append(plan)
    if not candidates:
        return None
    return min(candidates, key=lambda plan: (plan["scheduledStart"], -plan["priority"]))
