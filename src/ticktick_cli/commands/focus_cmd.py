"""Focus / Pomodoro commands — start, stop, log, delete, status, stats, heatmap, by-tag (V2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import click

from ticktick_cli.api.v2 import _generate_object_id
from ticktick_cli.auth import get_client
from ticktick_cli.output import (
    is_dry_run,
    output_dry_run,
    output_error,
    output_item,
    output_list,
    output_message,
)

# TickTick UTC time format used by pomodoro APIs
_UTC_FMT = "%Y-%m-%dT%H:%M:%S.000+0000"


def _utcnow() -> datetime:
    """Current time in UTC."""
    return datetime.now(timezone.utc)


def _fmt_utc(dt: datetime) -> str:
    """Format a datetime to TickTick UTC pomodoro format."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(_UTC_FMT)


def _resolve_date_range(
    from_date: str | None, to_date: str | None, days: int
) -> tuple[date, date]:
    """Resolve CLI options to a (start, end) date pair."""
    if from_date and to_date:
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()
    else:
        end = date.today()
        start = end - timedelta(days=days)
    return start, end


# ── Group ────────────────────────────────────────────────────


@click.group("focus")
def focus_group() -> None:
    """Focus / Pomodoro — start, stop, log, delete, status, stats (V2)."""


# ── start ────────────────────────────────────────────────────


@focus_group.command("start")
@click.option("--duration", "-d", type=int, default=25, help="Duration in minutes (default: 25).")
@click.option("--note", "-n", default="", help="Focus note.")
@click.pass_context
def focus_start(ctx: click.Context, duration: int, note: str) -> None:
    """Start a pomodoro focus timer."""
    if is_dry_run(ctx):
        output_dry_run("focus start", {"duration": duration, "note": note}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        # 1. Get current focus state to obtain lastPoint
        state = client.v2.focus_op(last_point=0, operations=[])
        last_point = state.get("point", 0)

        # Check if there's already an active session
        current = state.get("current", {})
        if current and not current.get("exited", True) and current.get("status", 3) == 0:
            output_error("A focus session is already running. Use `focus stop` first.", ctx)
            raise SystemExit(1)

        # 2. Generate IDs
        session_id = _generate_object_id()
        op_id = _generate_object_id()
        now = _utcnow()

        # 3. Build start operation
        start_op = {
            "id": op_id,
            "oId": session_id,
            "oType": 0,
            "op": "start",
            "duration": duration,
            "firstFocusId": session_id,
            "focusOnId": "",
            "autoPomoLeft": 5,
            "pomoCount": 1,
            "manual": True,
            "note": note,
            "time": _fmt_utc(now),
        }

        result = client.v2.focus_op(last_point=last_point, operations=[start_op])
        current = result.get("current", {})
        output_item(
            {
                "action": "started",
                "sessionId": current.get("id", session_id),
                "duration": duration,
                "startTime": current.get("startTime", _fmt_utc(now)),
                "endTime": current.get("endTime", ""),
                "note": note,
            },
            ctx,
        )
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── stop ─────────────────────────────────────────────────────


@focus_group.command("stop")
@click.option("--save/--no-save", default=True, help="Save the record (default: save). --no-save abandons.")
@click.pass_context
def focus_stop(ctx: click.Context, save: bool) -> None:
    """Stop the current pomodoro focus timer.

    By default saves the record. Use --no-save to abandon (drop) it.
    """
    if is_dry_run(ctx):
        output_dry_run("focus stop", {"save": save}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        # 1. Get current state
        state = client.v2.focus_op(last_point=0, operations=[])
        last_point = state.get("point", 0)
        current = state.get("current", {})

        if not current or current.get("exited", True):
            output_error("No active focus session to stop.", ctx)
            raise SystemExit(1)

        session_id = current["id"]
        first_id = current.get("firstId", session_id)
        now = _utcnow()

        ops: list[dict[str, Any]] = []

        if save:
            # Pause first, then exit — this saves the record
            pause_op = {
                "id": _generate_object_id(),
                "oId": session_id,
                "oType": 0,
                "op": "pause",
                "duration": current.get("duration", 25),
                "firstFocusId": first_id,
                "focusOnId": "",
                "autoPomoLeft": current.get("autoPomoLeft", 5),
                "pomoCount": current.get("pomoCount", 1),
                "manual": True,
                "note": "",
                "time": _fmt_utc(now),
            }
            exit_op = {
                "id": _generate_object_id(),
                "oId": session_id,
                "oType": 0,
                "op": "exit",
                "duration": 0,
                "firstFocusId": first_id,
                "focusOnId": "",
                "autoPomoLeft": 0,
                "pomoCount": 0,
                "manual": True,
                "note": "",
                "time": _fmt_utc(now + timedelta(milliseconds=10)),
            }
            ops = [pause_op, exit_op]

            # Also save the pomodoro record via batch API
            start_time = current.get("startTime", "")
            end_time = _fmt_utc(now)
            record_id = _generate_object_id()
            record = {
                "startTime": start_time,
                "endTime": end_time,
                "pauseDuration": 0,
                "status": 1,
                "id": record_id,
                "tasks": [
                    {
                        "tags": [],
                        "projectName": "",
                        "startTime": start_time,
                        "endTime": end_time,
                    }
                ],
                "added": True,
                "note": "",
            }
            client.v2.batch_pomodoros(add=[record])
        else:
            # Drop + exit — abandon without saving
            drop_op = {
                "id": _generate_object_id(),
                "oId": session_id,
                "oType": 0,
                "op": "drop",
                "duration": 0,
                "firstFocusId": first_id,
                "focusOnId": "",
                "autoPomoLeft": current.get("autoPomoLeft", 5),
                "pomoCount": current.get("pomoCount", 1),
                "manual": True,
                "note": "",
                "time": _fmt_utc(now),
            }
            exit_op = {
                "id": _generate_object_id(),
                "oId": session_id,
                "oType": 0,
                "op": "exit",
                "duration": 0,
                "firstFocusId": first_id,
                "focusOnId": "",
                "autoPomoLeft": 0,
                "pomoCount": 0,
                "manual": True,
                "note": "",
                "time": _fmt_utc(now + timedelta(milliseconds=10)),
            }
            ops = [drop_op, exit_op]

        client.v2.focus_op(last_point=last_point, operations=ops)
        action = "saved" if save else "abandoned"
        output_item({"action": action, "sessionId": session_id}, ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── status ───────────────────────────────────────────────────


@focus_group.command("status")
@click.pass_context
def focus_status(ctx: click.Context) -> None:
    """Show current focus timer status."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        state = client.v2.focus_op(last_point=0, operations=[])
        current = state.get("current", {})

        if not current or current.get("exited", True):
            output_item({"status": "idle", "message": "No active focus session."}, ctx)
            return

        status_code = current.get("status", 0)
        status_map = {0: "running", 1: "paused", 2: "break", 3: "completed"}
        output_item(
            {
                "status": status_map.get(status_code, f"unknown({status_code})"),
                "sessionId": current.get("id", ""),
                "duration": current.get("duration", 0),
                "startTime": current.get("startTime", ""),
                "endTime": current.get("endTime", ""),
                "pomoCount": current.get("pomoCount", 0),
            },
            ctx,
        )
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── log ──────────────────────────────────────────────────────


@focus_group.command("log")
@click.option("--start", "start_time", required=True, help="Start time (HH:MM or YYYY-MM-DDTHH:MM).")
@click.option("--end", "end_time", required=True, help="End time (HH:MM or YYYY-MM-DDTHH:MM).")
@click.option("--note", "-n", default="", help="Focus note.")
@click.pass_context
def focus_log(ctx: click.Context, start_time: str, end_time: str, note: str) -> None:
    """Manually log a past focus record."""
    if is_dry_run(ctx):
        output_dry_run("focus log", {"start": start_time, "end": end_time, "note": note}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        start_dt = _parse_time(start_time)
        end_dt = _parse_time(end_time)

        if end_dt <= start_dt:
            output_error("End time must be after start time.", ctx)
            raise SystemExit(1)

        record_id = _generate_object_id()
        s = _fmt_utc(start_dt)
        e = _fmt_utc(end_dt)

        record = {
            "startTime": s,
            "endTime": e,
            "pauseDuration": 0,
            "status": 1,
            "id": record_id,
            "tasks": [{"tags": [], "projectName": "", "startTime": s, "endTime": e}],
            "added": True,
            "note": note,
        }

        result = client.v2.batch_pomodoros(add=[record])
        errors = result.get("id2error", {})
        if errors.get(record_id):
            output_error(f"Failed to log record: {errors[record_id]}", ctx)
            raise SystemExit(1)

        mins = int((end_dt - start_dt).total_seconds() / 60)
        output_item(
            {
                "action": "logged",
                "id": record_id,
                "startTime": s,
                "endTime": e,
                "duration": f"{mins}m",
                "note": note,
            },
            ctx,
        )
    except SystemExit:
        raise
    except ValueError as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── delete ───────────────────────────────────────────────────


@focus_group.command("delete")
@click.argument("pomodoro_id")
@click.pass_context
def focus_delete(ctx: click.Context, pomodoro_id: str) -> None:
    """Delete a pomodoro record by ID."""
    if is_dry_run(ctx):
        output_dry_run("focus delete", {"id": pomodoro_id}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.delete_pomodoro(pomodoro_id)
        output_message(f"Pomodoro {pomodoro_id} deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── stats ────────────────────────────────────────────────────


@focus_group.command("stats")
@click.pass_context
def focus_stats(ctx: click.Context) -> None:
    """Show focus/pomodoro statistics (today & total)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        data = client.v2.get_focus_stats()
        output_item(
            {
                "todayPomos": data.get("todayPomoCount", 0),
                "todayMinutes": data.get("todayPomoDuration", 0),
                "totalPomos": data.get("totalPomoCount", 0),
                "totalMinutes": data.get("totalPomoDuration", 0),
            },
            ctx,
        )
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── heatmap ──────────────────────────────────────────────────


@focus_group.command("heatmap")
@click.option("--from", "from_date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--days", type=int, default=30, help="Number of days (default: 30)")
@click.pass_context
def focus_heatmap(ctx: click.Context, from_date: str | None, to_date: str | None, days: int) -> None:
    """View focus time heatmap data."""
    client = get_client(ctx.obj.get("profile", "default"))
    start, end = _resolve_date_range(from_date, to_date, days)

    try:
        data = client.v2.get_focus_heatmap(start, end)
        if isinstance(data, list) and data and "day" in data[0]:
            rows = [
                {"date": item["day"], "minutes": item.get("duration", 0)}
                for item in data
                if item.get("duration", 0) > 0
            ]
            if not rows:
                rows = [{"date": item["day"], "minutes": 0} for item in data[-7:]]
            output_list(rows, columns=["date", "minutes"], title="Focus Heatmap", ctx=ctx)
        elif isinstance(data, list):
            output_list(data, title="Focus Heatmap", ctx=ctx)
        elif isinstance(data, dict):
            output_item(data, ctx)
        else:
            output_item({"raw": data}, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── by-tag ───────────────────────────────────────────────────


@focus_group.command("by-tag")
@click.option("--from", "from_date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--days", type=int, default=30, help="Number of days (default: 30)")
@click.pass_context
def focus_by_tag(ctx: click.Context, from_date: str | None, to_date: str | None, days: int) -> None:
    """View focus time distribution by tag."""
    client = get_client(ctx.obj.get("profile", "default"))
    start, end = _resolve_date_range(from_date, to_date, days)

    try:
        data = client.v2.get_focus_by_tag(start, end)
        if isinstance(data, dict) and any(
            k in data for k in ("tagDurations", "projectDurations", "taskDurations")
        ):
            sections: list[dict[str, Any]] = []
            for section_key, label in [
                ("projectDurations", "project"),
                ("tagDurations", "tag"),
                ("taskDurations", "task"),
            ]:
                for name, minutes in sorted(
                    data.get(section_key, {}).items(), key=lambda x: -x[1]
                ):
                    sections.append({"type": label, "name": name, "minutes": minutes})
            output_list(
                sections,
                columns=["type", "name", "minutes"],
                title="Focus Distribution",
                ctx=ctx,
            )
        elif isinstance(data, list):
            output_list(data, title="Focus Distribution", ctx=ctx)
        else:
            output_item(data, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── helpers ──────────────────────────────────────────────────


def _parse_time(time_str: str) -> datetime:
    """Parse a time string to a UTC datetime.

    Accepts:
      - HH:MM (today, local time → converted to UTC)
      - YYYY-MM-DDTHH:MM (local time → converted to UTC)
      - YYYY-MM-DDTHH:MM:SS
    """
    now = datetime.now()
    s = time_str.strip()

    # HH:MM — assume today
    if len(s) <= 5 and ":" in s:
        parts = s.split(":")
        h, m = int(parts[0]), int(parts[1])
        local_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        # Convert local to UTC
        return local_dt.astimezone(timezone.utc)

    # YYYY-MM-DDTHH:MM or YYYY-MM-DDTHH:MM:SS
    try:
        local_dt = datetime.fromisoformat(s)
        if local_dt.tzinfo is None:
            local_dt = local_dt.astimezone()  # Assume local timezone
        return local_dt.astimezone(timezone.utc)
    except ValueError:
        pass

    raise ValueError(
        f"Cannot parse time: '{time_str}'. Use HH:MM or YYYY-MM-DDTHH:MM"
    )
