"""Habit commands — list, show, create, edit, delete, checkin, history, archive (V2 only)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_error, output_item, output_list, output_message


def _format_habit(h: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": h.get("id", ""),
        "name": h.get("name", ""),
        "type": h.get("type", "Boolean"),
        "goal": h.get("goal", 1.0),
        "unit": h.get("unit", "Count"),
        "color": h.get("color", ""),
        "status": "archived" if h.get("status") == 2 else "active",
        "totalCheckIns": h.get("totalCheckIns", 0),
        "currentStreak": h.get("currentStreak", 0),
        "iconRes": h.get("iconRes", ""),
        "sectionId": h.get("sectionId", ""),
    }


@click.group("habit")
def habit_group() -> None:
    """Manage habits (V2)."""


@habit_group.command("list")
@click.option("--include-archived", is_flag=True)
@click.pass_context
def habit_list(ctx: click.Context, include_archived: bool) -> None:
    """List all habits."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        habits = client.v2.get_habits()
        if not include_archived:
            habits = [h for h in habits if h.get("status", 0) != 2]
        formatted = [_format_habit(h) for h in habits]
        output_list(
            formatted,
            columns=["id", "name", "type", "goal", "currentStreak", "totalCheckIns", "status"],
            title="Habits",
            ctx=ctx,
        )
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("show")
@click.argument("habit_id")
@click.pass_context
def habit_show(ctx: click.Context, habit_id: str) -> None:
    """Show detailed habit information."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        habits = client.v2.get_habits()
        habit = next((h for h in habits if h.get("id") == habit_id), None)
        if not habit:
            output_error(f"Habit {habit_id} not found.", ctx)
            raise SystemExit(1) from None
        output_item(_format_habit(habit), ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("create")
@click.argument("name")
@click.option("--type", "habit_type", type=click.Choice(["boolean", "numeric"]), default="boolean")
@click.option("--goal", type=float, default=1.0)
@click.option("--unit", default="Count")
@click.option("--color", default="#97E38B")
@click.option("--icon", default="habit_daily_check_in")
@click.option("--section", type=click.Choice(["morning", "afternoon", "night"]), default=None)
@click.option("--repeat", default="RRULE:FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA")
@click.option("--reminder", default=None, help="Reminder time (HH:MM)")
@click.pass_context
def habit_create(
    ctx: click.Context,
    name: str,
    habit_type: str,
    goal: float,
    unit: str,
    color: str,
    icon: str,
    section: str | None,
    repeat: str,
    reminder: str | None,
) -> None:
    """Create a new habit."""
    client = get_client(ctx.obj.get("profile", "default"))

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    habit_id = uuid.uuid4().hex[:24]

    habit_data: dict[str, Any] = {
        "id": habit_id,
        "name": name,
        "type": "Boolean" if habit_type == "boolean" else "Real",
        "goal": goal,
        "step": 0.0 if habit_type == "boolean" else 1.0,
        "unit": unit,
        "iconRes": icon,
        "color": color,
        "status": 0,
        "totalCheckIns": 0,
        "currentStreak": 0,
        "completedCycles": 0,
        "createdTime": now,
        "modifiedTime": now,
        "repeatRule": repeat,
        "encouragement": "",
        "recordEnable": habit_type == "numeric",
        "exDates": [],
        "style": 1,
        "etag": "",
    }

    section_map = {"morning": "_morning", "afternoon": "_afternoon", "night": "_night"}
    if section:
        habit_data["sectionId"] = section_map[section]
    if reminder:
        habit_data["reminders"] = [reminder]

    try:
        client.v2.batch_habits(add=[habit_data])
        output_message(f"Habit '{name}' created (ID: {habit_id}).", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("edit")
@click.argument("habit_id")
@click.option("--name", default=None)
@click.option("--goal", type=float, default=None)
@click.option("--color", default=None)
@click.option("--icon", default=None)
@click.pass_context
def habit_edit(ctx: click.Context, habit_id: str, **kwargs: Any) -> None:
    """Edit a habit's properties."""
    client = get_client(ctx.obj.get("profile", "default"))
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    update: dict[str, Any] = {"id": habit_id, "modifiedTime": now}
    for key, value in kwargs.items():
        if value is not None:
            api_key = {"icon": "iconRes"}.get(key, key)
            update[api_key] = value
    try:
        client.v2.batch_habits(update=[update])
        output_message(f"Habit {habit_id} updated.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("delete")
@click.argument("habit_id")
@click.option("--yes", is_flag=True)
@click.pass_context
def habit_delete(ctx: click.Context, habit_id: str, yes: bool) -> None:
    """Delete a habit."""
    if not yes:
        click.confirm(f"Delete habit {habit_id}?", abort=True)
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_habits(delete=[habit_id])
        output_message(f"Habit {habit_id} deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("checkin")
@click.argument("habit_id")
@click.option("--date", "checkin_date", default=None, help="Date YYYYMMDD (default: today)")
@click.option("--value", type=float, default=1.0, help="Check-in value")
@click.pass_context
def habit_checkin(ctx: click.Context, habit_id: str, checkin_date: str | None, value: float) -> None:
    """Check in a habit for today (or a specific date)."""
    client = get_client(ctx.obj.get("profile", "default"))
    stamp = int(checkin_date) if checkin_date else int(datetime.now().strftime("%Y%m%d"))
    checkin_id = uuid.uuid4().hex[:24]
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")

    checkin_data = {
        "id": checkin_id,
        "habitId": habit_id,
        "checkinStamp": stamp,
        "value": value,
        "goal": value,
        "status": 2,
        "createdTime": now,
        "modifiedTime": now,
    }

    try:
        client.v2.batch_habit_checkins(add=[checkin_data])
        output_message(f"Checked in habit {habit_id} for {stamp}.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("history")
@click.argument("habit_id")
@click.option("--from", "from_date", default=None, help="Start date YYYYMMDD")
@click.option("--days", type=int, default=30, help="Number of days of history")
@click.pass_context
def habit_history(ctx: click.Context, habit_id: str, from_date: str | None, days: int) -> None:
    """View habit check-in history."""
    client = get_client(ctx.obj.get("profile", "default"))
    from datetime import timedelta

    if from_date:
        after = int(from_date)
    else:
        d = datetime.now() - timedelta(days=days)
        after = int(d.strftime("%Y%m%d"))

    try:
        result = client.v2.query_habit_checkins([habit_id], after_stamp=after)
        checkins = result.get("checkins", {}).get(habit_id, [])
        formatted = [
            {
                "date": c.get("checkinStamp", ""),
                "value": c.get("value", 0),
                "status": c.get("status", 0),
            }
            for c in checkins
        ]
        output_list(formatted, columns=["date", "value", "status"], title=f"Habit History ({habit_id})", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("archive")
@click.argument("habit_id")
@click.pass_context
def habit_archive(ctx: click.Context, habit_id: str) -> None:
    """Archive a habit."""
    client = get_client(ctx.obj.get("profile", "default"))
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    try:
        client.v2.batch_habits(update=[{"id": habit_id, "status": 2, "modifiedTime": now}])
        output_message(f"Habit {habit_id} archived.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@habit_group.command("unarchive")
@click.argument("habit_id")
@click.pass_context
def habit_unarchive(ctx: click.Context, habit_id: str) -> None:
    """Unarchive a habit."""
    client = get_client(ctx.obj.get("profile", "default"))
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    try:
        client.v2.batch_habits(update=[{"id": habit_id, "status": 0, "modifiedTime": now}])
        output_message(f"Habit {habit_id} unarchived.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
