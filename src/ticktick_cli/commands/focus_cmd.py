"""Focus / Pomodoro commands — start, stop, log, delete, status, stats, heatmap, by-tag (V2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import click

from ticktick_cli.api.v2 import _generate_object_id
from ticktick_cli.auth import get_client
from ticktick_cli.exceptions import RateLimitError
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
DEFAULT_FOCUS_MINUTES = 25


def _utcnow() -> datetime:
    """Current time in UTC."""
    return datetime.now(timezone.utc)


def _fmt_utc(dt: datetime) -> str:
    """Format a datetime to TickTick UTC pomodoro format."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(_UTC_FMT)


def _focus_task_id(current: dict[str, Any]) -> str:
    for key in ("focusTasks", "focusOnLogs"):
        for item in current.get(key) or []:
            if item.get("id"):
                return item["id"]
    return current.get("focusOnId") or ""


def _focus_operation(
    current: dict[str, Any],
    op: str,
    when: datetime | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a TickTick web focus operation.

    Chrome inspection of TickTick's web app showed these Pomo operations:
    pause, continue, finish, drop, startBreak, endBreak, exit.
    """

    when = when or _utcnow()
    session_id = current.get("id") or _generate_object_id()
    first_id = current.get("firstId") or current.get("firstFocusId") or session_id
    task_id = _focus_task_id(current)
    return {
        "id": _generate_object_id(),
        "oId": session_id,
        "oType": overrides.pop("oType", current.get("oType", 0)),
        "op": op,
        "duration": overrides.pop("duration", current.get("duration", 25)),
        "firstFocusId": overrides.pop("firstFocusId", first_id),
        "focusOnId": overrides.pop("focusOnId", task_id),
        "autoPomoLeft": overrides.pop("autoPomoLeft", current.get("autoPomoLeft", 5)),
        "pomoCount": overrides.pop("pomoCount", current.get("pomoCount", 1)),
        "manual": overrides.pop("manual", True),
        "note": overrides.pop("note", current.get("note", "")),
        "time": _fmt_utc(when),
        **overrides,
    }


def _current_focus(client: Any) -> tuple[int, dict[str, Any]]:
    state = client.v2.focus_op(last_point=0, operations=[])
    return state.get("point", 0), state.get("current", {})


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def resolve_focus_duration(
    task: dict[str, Any],
    *,
    default_minutes: int = DEFAULT_FOCUS_MINUTES,
) -> dict[str, Any]:
    """Resolve one bounded focus block from TickTick's native estimate fields."""

    if default_minutes <= 0:
        raise click.ClickException("Fallback focus duration must be greater than zero.")

    estimated_seconds = _nonnegative_int(task.get("estimatedDurationSeconds"))
    estimated_pomo = _nonnegative_int(task.get("estimatedPomo"))
    ambiguous = bool(task.get("focusEstimateAmbiguous"))

    if not estimated_seconds and not estimated_pomo:
        estimates = [
            summary
            for summary in (task.get("focusSummaries") or [])
            if _nonnegative_int(summary.get("estimatedDuration")) > 0
            or _nonnegative_int(summary.get("estimatedPomo")) > 0
        ]
        if len(estimates) == 1:
            estimated_seconds = _nonnegative_int(estimates[0].get("estimatedDuration"))
            estimated_pomo = _nonnegative_int(estimates[0].get("estimatedPomo"))
        elif len(estimates) > 1:
            ambiguous = True

    estimated_minutes = (estimated_seconds + 59) // 60
    if ambiguous and not estimated_minutes and not estimated_pomo:
        return {
            "focusMinutes": default_minutes,
            "durationSource": "default_ambiguous",
            "estimatedDurationMinutes": 0,
            "estimatedPomo": 0,
        }

    if estimated_minutes:
        if estimated_minutes <= 15:
            focus_minutes = max(5, estimated_minutes)
        elif estimated_minutes <= 35:
            focus_minutes = 25
        else:
            focus_minutes = 50
        return {
            "focusMinutes": focus_minutes,
            "durationSource": "estimated_duration",
            "estimatedDurationMinutes": estimated_minutes,
            "estimatedPomo": estimated_pomo,
        }

    if estimated_pomo:
        return {
            "focusMinutes": DEFAULT_FOCUS_MINUTES,
            "durationSource": "estimated_pomo",
            "estimatedDurationMinutes": 0,
            "estimatedPomo": estimated_pomo,
        }

    return {
        "focusMinutes": default_minutes,
        "durationSource": "default",
        "estimatedDurationMinutes": 0,
        "estimatedPomo": 0,
    }


def _require_focus(current: dict[str, Any]) -> None:
    if not current or current.get("exited", True):
        raise click.ClickException("No active focus session.")


def _run_focus_control(client: Any, action: str, *, duration: int | None = None) -> dict[str, Any]:
    last_point, current = _current_focus(client)
    _require_focus(current)

    status = current.get("status", 0)
    now = _utcnow()
    if action == "pause":
        if status != 0:
            raise click.ClickException("Focus session is not running.")
        op = _focus_operation(current, "pause", now)
    elif action == "resume":
        if status != 1:
            raise click.ClickException("Focus session is not paused.")
        op = _focus_operation(current, "continue", now)
    elif action == "finish":
        if status not in (0, 1):
            raise click.ClickException("Focus session is not running or paused.")
        op = _focus_operation(current, "finish", now)
    elif action == "abandon":
        if status not in (0, 1):
            raise click.ClickException("Focus session is not running or paused.")
        op = _focus_operation(current, "drop", now)
    elif action == "start-break":
        op = _focus_operation(current, "startBreak", now, duration=duration or 5)
    elif action == "skip-break":
        if status != 2:
            raise click.ClickException("No active break to skip.")
        op = _focus_operation(current, "endBreak", now)
    else:
        raise click.ClickException(f"Unsupported focus action: {action}")

    result = client.v2.focus_op(last_point=last_point, operations=[op])
    return {
        "action": action,
        "sessionId": current.get("id", ""),
        "operation": op["op"],
        "ticktickPoint": result.get("point"),
    }


def run_focus_control(client: Any, action: str, *, duration: int | None = None) -> dict[str, Any]:
    """Run a live TickTick focus timer control operation.

    This helper is intentionally importable by local operator surfaces such as
    Mission Control's macOS menu-bar tracker.
    """

    return _run_focus_control(client, action, duration=duration)


def run_focus_start(
    client: Any,
    *,
    duration: int = 25,
    note: str = "",
    task_id: str = "",
    auto_duration: bool = False,
) -> dict[str, Any]:
    """Start a live TickTick focus timer, optionally linked to a task.

    Local operator surfaces use this helper so task-linked focus starts share
    the same validation and payload shape as the CLI command.
    """

    if duration <= 0:
        raise click.ClickException("Focus duration must be greater than zero.")
    if auto_duration and not task_id:
        raise click.ClickException("Automatic focus duration requires a linked task ID.")

    last_point, current = _current_focus(client)
    if current and not current.get("exited", True) and current.get("status", 3) in (0, 1, 2):
        raise click.ClickException(
            "A focus session or rest break is already active. Finish or abandon it first."
        )

    duration_plan = {
        "focusMinutes": duration,
        "durationSource": "manual",
        "estimatedDurationMinutes": 0,
        "estimatedPomo": 0,
    }
    if auto_duration:
        try:
            duration_plan = resolve_focus_duration(
                client.v2.get_task(task_id),
                default_minutes=duration,
            )
        except RateLimitError:
            duration_plan = {
                "focusMinutes": duration,
                "durationSource": "default_rate_limited",
                "estimatedDurationMinutes": 0,
                "estimatedPomo": 0,
            }
        duration = duration_plan["focusMinutes"]

    session_id = _generate_object_id()
    now = _utcnow()
    start_op = {
        "id": _generate_object_id(),
        "oId": session_id,
        "oType": 0,
        "op": "start",
        "duration": duration,
        "firstFocusId": session_id,
        "focusOnId": task_id,
        "autoPomoLeft": 5,
        "pomoCount": 1,
        "manual": True,
        "note": note,
        "time": _fmt_utc(now),
    }

    result = client.v2.focus_op(last_point=last_point, operations=[start_op])
    started = result.get("current", {})
    return {
        "action": "started",
        "sessionId": started.get("id", session_id),
        "duration": duration,
        "focusMinutes": duration,
        "durationSource": duration_plan["durationSource"],
        "estimatedDurationMinutes": duration_plan["estimatedDurationMinutes"],
        "estimatedPomo": duration_plan["estimatedPomo"],
        "startTime": started.get("startTime", _fmt_utc(now)),
        "endTime": started.get("endTime", ""),
        "taskId": task_id or None,
        "note": note,
        "operation": start_op["op"],
        "ticktickPoint": result.get("point"),
    }


def _resolve_date_range(from_date: str | None, to_date: str | None, days: int) -> tuple[date, date]:
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
    """Focus / Pomodoro — timer controls, log, delete, status, stats (V2)."""


# ── start ────────────────────────────────────────────────────


@focus_group.command("start")
@click.option("--duration", "-d", type=int, default=25, help="Duration in minutes (default: 25).")
@click.option("--note", "-n", default="", help="Focus note.")
@click.option("--task", "-t", default="", help="Task ID to link this focus session to.")
@click.option(
    "--auto-duration",
    is_flag=True,
    help="Use the linked task's native estimate; fall back to --duration.",
)
@click.pass_context
def focus_start(
    ctx: click.Context,
    duration: int,
    note: str,
    task: str,
    auto_duration: bool,
) -> None:
    """Start a pomodoro focus timer."""
    if is_dry_run(ctx):
        output_dry_run(
            "focus start",
            {
                "duration": duration,
                "note": note,
                "task": task,
                "auto_duration": auto_duration,
            },
            ctx,
        )
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        output_item(
            run_focus_start(
                client,
                duration=duration,
                note=note,
                task_id=task,
                auto_duration=auto_duration,
            ),
            ctx,
        )
    except click.ClickException as exc:
        output_error(str(exc), ctx)
        raise SystemExit(1) from None
    except Exception as exc:
        output_error(str(exc), ctx)
        raise SystemExit(1) from None


@focus_group.command("recommend")
@click.argument("task_id")
@click.option(
    "--fallback",
    "fallback_minutes",
    type=int,
    default=DEFAULT_FOCUS_MINUTES,
    help="Fallback duration when the task has no estimate (default: 25).",
)
@click.pass_context
def focus_recommend(ctx: click.Context, task_id: str, fallback_minutes: int) -> None:
    """Recommend one focus block from a task's native TickTick estimate."""

    if is_dry_run(ctx):
        output_dry_run(
            "focus recommend",
            {"task_id": task_id, "fallback_minutes": fallback_minutes},
            ctx,
        )
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        output_item(
            {
                "taskId": task_id,
                "title": task.get("title", ""),
                **resolve_focus_duration(task, default_minutes=fallback_minutes),
            },
            ctx,
        )
    except click.ClickException as exc:
        output_error(str(exc), ctx)
        raise SystemExit(1) from None
    except Exception as exc:
        output_error(str(exc), ctx)
        raise SystemExit(1) from None


# ── stop ─────────────────────────────────────────────────────


@focus_group.command("stop")
@click.option(
    "--save/--no-save", default=True, help="Save the record (default: save). --no-save abandons."
)
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


# ── live controls ────────────────────────────────────────────


@focus_group.command("pause")
@click.pass_context
def focus_pause(ctx: click.Context) -> None:
    """Pause the current Pomodoro focus timer."""
    if is_dry_run(ctx):
        output_dry_run("focus pause", {}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        output_item(_run_focus_control(client, "pause"), ctx)
    except click.ClickException as e:
        output_error(e.message, ctx)
        raise SystemExit(1) from None
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@focus_group.command("resume")
@click.pass_context
def focus_resume(ctx: click.Context) -> None:
    """Continue a paused Pomodoro focus timer."""
    if is_dry_run(ctx):
        output_dry_run("focus resume", {}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        output_item(_run_focus_control(client, "resume"), ctx)
    except click.ClickException as e:
        output_error(e.message, ctx)
        raise SystemExit(1) from None
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@focus_group.command("finish")
@click.pass_context
def focus_finish(ctx: click.Context) -> None:
    """Finish and save the current Pomodoro focus timer."""
    if is_dry_run(ctx):
        output_dry_run("focus finish", {}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        output_item(_run_focus_control(client, "finish"), ctx)
    except click.ClickException as e:
        output_error(e.message, ctx)
        raise SystemExit(1) from None
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@focus_group.command("abandon")
@click.pass_context
def focus_abandon(ctx: click.Context) -> None:
    """Drop the current Pomodoro focus timer without saving it."""
    if is_dry_run(ctx):
        output_dry_run("focus abandon", {}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        output_item(_run_focus_control(client, "abandon"), ctx)
    except click.ClickException as e:
        output_error(e.message, ctx)
        raise SystemExit(1) from None
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@focus_group.command("start-break")
@click.option(
    "--duration", "-d", type=int, default=5, help="Break duration in minutes (default: 5)."
)
@click.pass_context
def focus_start_break(ctx: click.Context, duration: int) -> None:
    """Start a rest break after a Pomodoro focus timer."""
    if is_dry_run(ctx):
        output_dry_run("focus start-break", {"duration": duration}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        output_item(_run_focus_control(client, "start-break", duration=duration), ctx)
    except click.ClickException as e:
        output_error(e.message, ctx)
        raise SystemExit(1) from None
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@focus_group.command("skip-break")
@click.pass_context
def focus_skip_break(ctx: click.Context) -> None:
    """End the current Pomodoro rest break."""
    if is_dry_run(ctx):
        output_dry_run("focus skip-break", {}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        output_item(_run_focus_control(client, "skip-break"), ctx)
    except click.ClickException as e:
        output_error(e.message, ctx)
        raise SystemExit(1) from None
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


# ── link ─────────────────────────────────────────────────────


@focus_group.command("link")
@click.argument("task_id")
@click.pass_context
def focus_link(ctx: click.Context, task_id: str) -> None:
    """Link (or change) the task attached to the currently running focus session."""
    if is_dry_run(ctx):
        output_dry_run("focus link", {"task_id": task_id}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        # 1. Get current state
        state = client.v2.focus_op(last_point=0, operations=[])
        current = state.get("current", {})

        if not current or current.get("exited", True):
            output_error("No active focus session. Start one first with `focus start`.", ctx)
            raise SystemExit(1)
        # Observed web behavior preserves a single session and appends task segments.
        # Until the CLI can reproduce that operation sequence safely, fail fast instead
        # of silently restarting the pomodoro under a new session ID.
        output_error(
            "Linking a running focus session is not supported reliably yet. "
            "Use `focus stop --no-save` and `focus start --task TASK_ID` instead.",
            ctx,
        )
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


# ── log ──────────────────────────────────────────────────────


@focus_group.command("log")
@click.option(
    "--start", "start_time", required=True, help="Start time (HH:MM or YYYY-MM-DDTHH:MM)."
)
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
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def focus_delete(ctx: click.Context, pomodoro_id: str, yes: bool) -> None:
    """Delete a pomodoro record by ID."""
    if is_dry_run(ctx):
        output_dry_run("focus delete", {"id": pomodoro_id}, ctx)
        return

    if not yes:
        click.confirm(f"Delete pomodoro record {pomodoro_id}?", abort=True)
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
def focus_heatmap(
    ctx: click.Context, from_date: str | None, to_date: str | None, days: int
) -> None:
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
                for name, minutes in sorted(data.get(section_key, {}).items(), key=lambda x: -x[1]):
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

    raise ValueError(f"Cannot parse time: '{time_str}'. Use HH:MM or YYYY-MM-DDTHH:MM")
