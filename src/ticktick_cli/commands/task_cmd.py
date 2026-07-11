"""Task commands — full CRUD, search, batch operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import click

from ticktick_cli.api.v2 import (
    _format_attachment_markdown,
    _generate_object_id,
    _infer_attachment_file_type,
)
from ticktick_cli.auth import get_client
from ticktick_cli.dates import parse_date
from ticktick_cli.exceptions import TickTickCLIError, handle_cli_error
from ticktick_cli.models.comment import Activity, Comment
from ticktick_cli.models.task import Task
from ticktick_cli.output import (
    is_dry_run,
    output_dry_run,
    output_error,
    output_existing_item,
    output_item,
    output_list,
    output_message,
)

PRIORITY_MAP = {"none": 0, "low": 1, "medium": 3, "high": 5}
PRIORITY_REVERSE = {0: "none", 1: "low", 3: "medium", 5: "high"}
_FETCH_ALL_LIMIT = 10_000
_TICKTICK_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
)
_RECURRENCE_SKIP_PRESERVE_FIELDS = (
    "repeatFlag",
    "repeatFrom",
    "dueDate",
    "startDate",
    "timeZone",
    "isAllDay",
    "reminder",
    "reminders",
)
_V1_TASK_EDIT_FIELDS = {
    "id",
    "title",
    "content",
    "priority",
    "dueDate",
    "startDate",
    "timeZone",
    "isAllDay",
    "tags",
    "projectId",
    "columnId",
}
_V1_TASK_CREATE_FIELDS = _V1_TASK_EDIT_FIELDS - {"id", "tags", "columnId"}


def _handle_task_error(error: Exception, ctx: click.Context) -> NoReturn:
    """Preserve typed CLI errors while keeping generic task errors formatted."""
    if isinstance(error, TickTickCLIError):
        handle_cli_error(error)
    output_error(str(error), ctx)
    raise SystemExit(1) from None


def _format_task(task: dict[str, Any]) -> dict[str, Any]:
    """Normalize task dict for output."""
    try:
        return Task(**task).to_output()
    except Exception:
        return {
            "id": task.get("id", ""),
            "title": task.get("title", ""),
            "status": "completed" if task.get("status", 0) >= 2 else "active",
            "priority": PRIORITY_REVERSE.get(task.get("priority", 0), "none"),
            "projectId": task.get("projectId", ""),
            "dueDate": task.get("dueDate", ""),
            "startDate": task.get("startDate", ""),
            "tags": task.get("tags", []),
            "content": task.get("content", ""),
            "isAllDay": task.get("isAllDay", False),
            "parentId": task.get("parentId"),
            "columnId": task.get("columnId"),
            "columnName": task.get("columnName"),
            "pinnedTime": task.get("pinnedTime"),
            "sortOrder": task.get("sortOrder"),
            "items": task.get("items", []),  # subtask checklist items
        }


def _format_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    """Normalize attachment dict for output."""
    return {
        "id": attachment.get("id", ""),
        "refId": attachment.get("refId", ""),
        "taskId": attachment.get("taskId", ""),
        "projectId": attachment.get("projectId", ""),
        "fileName": attachment.get("fileName", ""),
        "fileType": attachment.get("fileType", ""),
        "size": attachment.get("size", 0),
        "path": attachment.get("path"),
    }


def _request_page_limit(ctx: click.Context, limit: int) -> int:
    """Fetch enough rows for global offset pagination before local slicing."""
    offset = int(ctx.obj.get("offset", 0)) if ctx.obj else 0
    fetch_all = bool(ctx.obj.get("all")) if ctx.obj else False
    if fetch_all:
        return max(limit + offset, _FETCH_ALL_LIMIT)
    return limit + offset


def _parse_ticktick_datetime(value: str) -> datetime:
    """Parse TickTick's datetime strings, including compact numeric offsets."""
    normalized = value.strip()
    if len(normalized) >= 5 and normalized[-5] in ("+", "-") and ":" not in normalized[-5:]:
        normalized = f"{normalized[:-2]}:{normalized[-2:]}"
    for fmt in _TICKTICK_DATETIME_FORMATS:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(normalized)


def _normalize_ex_date(date_value: str) -> str:
    """Convert a user date token into TickTick's recurrence exception stamp."""
    token = date_value.strip()
    if len(token) == 8 and token.isdigit():
        return token
    parsed = parse_date(token)
    return _parse_ticktick_datetime(parsed).strftime("%Y%m%d")


def _task_ex_date(task: dict[str, Any], occurrence_date: str | None) -> str:
    """Return the recurrence exception date for a task occurrence."""
    if occurrence_date:
        return _normalize_ex_date(occurrence_date)

    raw_date = task.get("dueDate") or task.get("startDate")
    if not raw_date:
        raise ValueError("Recurring task has no dueDate/startDate to skip. Pass --date YYYY-MM-DD.")

    dt = _parse_ticktick_datetime(raw_date)
    if task.get("isAllDay") or "T" not in raw_date:
        return dt.strftime("%Y%m%d")

    timezone_name = task.get("timeZone")
    if timezone_name:
        try:
            dt = dt.astimezone(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            pass
    return dt.strftime("%Y%m%d")


def _build_skip_recurrence_update(
    task: dict[str, Any],
    occurrence_date: str | None = None,
) -> tuple[dict[str, Any], str, bool]:
    """Build the V2 update payload for skipping one recurring occurrence."""
    if not task.get("repeatFlag"):
        raise ValueError("Task is not recurring; skip is only available for tasks with repeatFlag.")

    task_id = task.get("id")
    project_id = task.get("projectId")
    if not task_id or not project_id:
        raise ValueError("Task is missing id/projectId and cannot be updated through V2.")

    ex_date = _task_ex_date(task, occurrence_date)
    existing = [str(value) for value in (task.get("exDate") or [])]
    seen: set[str] = set()
    ex_dates = []
    for value in existing:
        if value not in seen:
            ex_dates.append(value)
            seen.add(value)

    already_skipped = ex_date in seen
    if not already_skipped:
        ex_dates.append(ex_date)

    update = {"id": task_id, "projectId": project_id}
    for field in _RECURRENCE_SKIP_PRESERVE_FIELDS:
        if field in task:
            update[field] = task[field]
    update["exDate"] = ex_dates
    return update, ex_date, already_skipped


@click.group("task")
def task_group() -> None:
    """Manage tasks."""


@task_group.command("add")
@click.argument("title")
@click.option("--project", "-p", default=None, help="Project name or ID")
@click.option("--content", "-c", default=None, help="Task body/notes")
@click.option(
    "--priority",
    type=click.Choice(["none", "low", "medium", "high"]),
    default="none",
    help="Task priority",
)
@click.option("--due", "-d", default=None, help="Due date (YYYY-MM-DD, today, tomorrow, monday, +3d, +1w, +2m)")
@click.option("--start", default=None, help="Start date")
@click.option("--tag", "-t", multiple=True, help="Tags (repeatable)")
@click.option(
    "--all-day/--timed",
    default=None,
    help="Set whether the task is all-day or timed",
)
@click.option("--timezone", default=None, help="IANA timezone, for example Europe/Brussels")
@click.option("--repeat", default=None, help="Recurrence RRULE (e.g., RRULE:FREQ=DAILY)")
@click.option("--reminder", multiple=True, help="Reminder triggers")
@click.option("--if-not-exists", "if_not_exists", is_flag=True, help="Skip creation if a task with the same title exists in the project")
@click.pass_context
def task_add(
    ctx: click.Context,
    title: str,
    project: str | None,
    content: str | None,
    priority: str,
    due: str | None,
    start: str | None,
    tag: tuple[str, ...],
    all_day: bool | None,
    timezone: str | None,
    repeat: str | None,
    reminder: tuple[str, ...],
    if_not_exists: bool,
) -> None:
    """Create a new task."""
    task_data: dict[str, Any] = {"title": title}
    if project:
        task_data["project"] = project
    if content:
        task_data["content"] = content
    task_data["priority"] = PRIORITY_MAP[priority]
    if due:
        task_data["dueDate"] = parse_date(due)
    if start:
        task_data["startDate"] = parse_date(start)
    if tag:
        task_data["tags"] = list(tag)
    if all_day is not None:
        task_data["isAllDay"] = all_day
    if timezone:
        task_data["timeZone"] = timezone
    if repeat:
        task_data["repeatFlag"] = repeat
    if reminder:
        task_data["reminders"] = list(reminder)

    if is_dry_run(ctx):
        output_dry_run("task.add", task_data, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    project_id = _resolve_project_id(client, project) if project else None

    if if_not_exists:
        try:
            tasks = client.get_all_tasks()
        except Exception as e:
            if not (client.has_v1 and _is_rate_limit_error(e)):
                _handle_task_error(e, ctx)
            project_ids = {project_id} if project_id else None
            tasks = _get_project_tasks_v1(client, project_ids)
        for t in tasks:
            if (
                t.get("title", "").lower() == title.lower()
                and t.get("status", 0) < 2
                and (project_id is None or t.get("projectId") == project_id)
            ):
                output_existing_item(_format_task(t), ctx)
                return

    if project:
        task_data["projectId"] = project_id
        task_data.pop("project", None)

    try:
        if client.has_v2:
            task_data.setdefault("id", _generate_object_id())
            try:
                client.v2.batch_tasks(add=[task_data])
            except Exception as v2_error:
                if not (client.has_v1 and _is_rate_limit_error(v2_error)):
                    raise
                v1_task_data = {
                    key: value for key, value in task_data.items() if key in _V1_TASK_CREATE_FIELDS
                }
                result = client.v1.create_task(v1_task_data)
                output_item(
                    _format_task(result),
                    ctx,
                    message=f"Task created: {result.get('title', title)}",
                )
                return
            output_item(_format_task(task_data), ctx, message=f"Task created: {title}")
        else:
            result = client.v1.create_task(task_data)
            output_item(
                _format_task(result),
                ctx,
                message=f"Task created: {result.get('title', title)}",
            )
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("list")
@click.option("--project", "-p", default=None, help="Filter by project name or ID")
@click.option("--folder", default=None, help="Filter by folder/group name or ID")
@click.option("--folder-id", default=None, help="Filter by folder/group ID without V2 lookup")
@click.option(
    "--status",
    type=click.Choice(["uncompleted", "completed", "abandoned", "all"]),
    default="uncompleted",
)
@click.option("--priority", type=click.Choice(["none", "low", "medium", "high"]), default=None)
@click.option("--due", default=None, help="Filter: today, overdue, this-week, YYYY-MM-DD")
@click.option("--tag", "-t", multiple=True, help="Filter by tag")
@click.option("--sort", type=click.Choice(["due", "priority", "title", "created", "sortOrder"]), default="due")
@click.option("--limit", "-n", type=int, default=50, help="Max results")
@click.pass_context
def task_list(
    ctx: click.Context,
    project: str | None,
    folder: str | None,
    folder_id: str | None,
    status: str,
    priority: str | None,
    due: str | None,
    tag: tuple[str, ...],
    sort: str,
    limit: int,
) -> None:
    """List tasks with optional filters."""
    if project and (folder or folder_id):
        raise click.UsageError("--project cannot be combined with --folder or --folder-id.")
    if folder and folder_id:
        raise click.UsageError("--folder and --folder-id are mutually exclusive.")

    client = get_client(ctx.obj.get("profile", "default"))

    try:
        project_id = _resolve_project_id(client, project) if project else None
        folder_project_ids: set[str] | None = None
        if folder or folder_id:
            resolved_folder_id = folder_id or _resolve_folder_id(client, folder or "")
            folder_project_ids = _resolve_project_ids_for_folder(client, resolved_folder_id)

        if status == "completed" and client.has_v2:
            now = datetime.now()
            tasks = client.v2.get_completed_tasks(now - timedelta(days=365), now, limit=limit)
        elif folder_project_ids is not None and client.has_v1:
            tasks = _get_project_tasks_v1(client, folder_project_ids)
        elif project_id and client.has_v1:
            tasks = _get_project_tasks_v1(client, {project_id})
        elif client.has_v2:
            tasks = client.get_all_tasks()
        else:
            tasks = _get_project_tasks_v1(client)

        # Apply filters
        if project_id:
            tasks = [t for t in tasks if t.get("projectId") == project_id]
        if folder_project_ids is not None:
            tasks = [t for t in tasks if t.get("projectId") in folder_project_ids]
        if status == "uncompleted":
            tasks = [t for t in tasks if t.get("status", 0) == 0]
        elif status == "abandoned":
            tasks = [t for t in tasks if t.get("status", 0) == -1]
        if priority:
            p = PRIORITY_MAP[priority]
            tasks = [t for t in tasks if t.get("priority", 0) == p]
        if tag:
            tag_set = set(tag)
            tasks = [t for t in tasks if tag_set.intersection(set(t.get("tags", [])))]
        if due:
            tasks = _filter_by_due(tasks, due)

        # Sort
        tasks = _sort_tasks(tasks, sort)

        formatted = [_format_task(t) for t in tasks]
        columns = ["id", "title", "priority", "dueDate", "projectId", "tags"]
        output_list(formatted, columns=columns, title="Tasks", ctx=ctx, limit=limit)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("show")
@click.argument("task_id")
@click.pass_context
def task_show(ctx: click.Context, task_id: str) -> None:
    """Show detailed task information."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        if client.has_v2:
            task = client.v2.get_task(task_id)
        else:
            # V1 requires project_id — search for it
            task = _find_task_v1(client, task_id)
        output_item(_format_task(task), ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("edit")
@click.argument("task_id")
@click.option("--title", default=None)
@click.option("--content", default=None)
@click.option("--priority", type=click.Choice(["none", "low", "medium", "high"]), default=None)
@click.option("--due", default=None)
@click.option("--start", default=None)
@click.option("--project", default=None)
@click.option("--tag", "-t", multiple=True)
@click.option("--repeat", default=None)
@click.option("--column", default=None, help="Kanban column ID")
@click.option(
    "--all-day/--timed",
    default=None,
    help="Set whether the task is all-day or timed",
)
@click.option("--timezone", default=None, help="IANA timezone, for example Europe/Brussels")
@click.pass_context
def task_edit(ctx: click.Context, task_id: str, **kwargs: Any) -> None:
    """Edit a task's properties."""
    update: dict[str, Any] = {"id": task_id}
    if kwargs.get("title"):
        update["title"] = kwargs["title"]
    if kwargs.get("content"):
        update["content"] = kwargs["content"]
    if kwargs.get("priority"):
        update["priority"] = PRIORITY_MAP[kwargs["priority"]]
    if kwargs.get("due"):
        update["dueDate"] = parse_date(kwargs["due"])
    if kwargs.get("start"):
        update["startDate"] = parse_date(kwargs["start"])
    if kwargs.get("tag"):
        update["tags"] = list(kwargs["tag"])
    if kwargs.get("repeat"):
        update["repeatFlag"] = kwargs["repeat"]
    if kwargs.get("column"):
        update["columnId"] = kwargs["column"]
    if kwargs.get("all_day") is not None:
        update["isAllDay"] = kwargs["all_day"]
    if kwargs.get("timezone"):
        update["timeZone"] = kwargs["timezone"]

    if is_dry_run(ctx):
        output_dry_run("task.edit", update, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    if kwargs.get("project"):
        update["projectId"] = _resolve_project_id(client, kwargs["project"])
    try:
        try:
            if client.has_v2:
                # Need projectId for V2 update
                if "projectId" not in update:
                    task = client.v2.get_task(task_id)
                    update["projectId"] = task.get("projectId", "")
                client.v2.batch_tasks(update=[update])
            else:
                client.v1.update_task(task_id, update)
        except Exception as v2_error:
            if not (_can_edit_task_with_v1(client, update) and _is_rate_limit_error(v2_error)):
                raise
            v1_update = {key: value for key, value in update.items() if key in _V1_TASK_EDIT_FIELDS}
            if "projectId" not in v1_update:
                task = _find_task_v1(client, task_id)
                if task.get("projectId"):
                    v1_update["projectId"] = task["projectId"]
            client.v1.update_task(task_id, v1_update)
        output_message(f"Task {task_id} updated.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("done")
@click.argument("task_ids", nargs=-1, required=True)
@click.pass_context
def task_done(ctx: click.Context, task_ids: tuple[str, ...]) -> None:
    """Mark task(s) as completed."""
    if is_dry_run(ctx):
        output_dry_run("task.done", {"task_ids": list(task_ids)}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        if client.has_v1:
            for tid in task_ids:
                task = _get_task_any(client, tid)
                client.v1.complete_task(task["projectId"], tid)
        elif client.has_v2:
            updates = []
            for tid in task_ids:
                task = client.v2.get_task(tid)
                updates.append({"id": tid, "projectId": task["projectId"], "status": 2})
            client.v2.batch_tasks(update=updates)
        output_message(f"Completed {len(task_ids)} task(s).", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("abandon")
@click.argument("task_ids", nargs=-1, required=True)
@click.pass_context
def task_abandon(ctx: click.Context, task_ids: tuple[str, ...]) -> None:
    """Mark task(s) as 'won't do' (V2 only)."""
    if is_dry_run(ctx):
        output_dry_run("task.abandon", {"task_ids": list(task_ids)}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        updates = []
        for tid in task_ids:
            task = _get_task_any(client, tid)
            updates.append({"id": tid, "projectId": task["projectId"], "status": -1})
        client.v2.batch_tasks(update=updates)
        output_message(f"Abandoned {len(task_ids)} task(s).", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("skip")
@click.argument("task_id")
@click.option("--date", "occurrence_date", default=None, help="Occurrence date to skip (default: task due date)")
@click.pass_context
def task_skip(ctx: click.Context, task_id: str, occurrence_date: str | None) -> None:
    """Skip one occurrence of a recurring task (V2)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        if not client.has_v2:
            raise ValueError("Skipping recurring task occurrences requires V2 authentication.")

        task = client.v2.get_task(task_id)
        update, ex_date, already_skipped = _build_skip_recurrence_update(task, occurrence_date)
        details = {
            "id": task_id,
            "title": task.get("title", ""),
            "projectId": update["projectId"],
            "exDate": ex_date,
            "repeatFlag": task.get("repeatFlag", ""),
            "alreadySkipped": already_skipped,
            "payload": update,
        }

        if is_dry_run(ctx):
            output_dry_run("task.skip", details, ctx)
            return

        if already_skipped:
            output_item(details, ctx, message=f"Task occurrence {ex_date} was already skipped.")
            return

        client.v2.skip_task_recurrence(update)
        output_item(details, ctx, message=f"Skipped recurrence {ex_date} for task {task_id}.")
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("delete")
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def task_delete(ctx: click.Context, task_ids: tuple[str, ...], yes: bool) -> None:
    """Delete task(s)."""
    if is_dry_run(ctx):
        output_dry_run("task.delete", {"task_ids": list(task_ids)}, ctx)
        return

    if not yes:
        click.confirm(f"Delete {len(task_ids)} task(s)?", abort=True)
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        if client.has_v2:
            deletes = []
            for tid in task_ids:
                task = client.v2.get_task(tid)
                deletes.append({"taskId": tid, "projectId": task["projectId"]})
            client.v2.batch_tasks(delete=deletes)
        else:
            for tid in task_ids:
                task = _find_task_v1(client, tid)
                client.v1.delete_task(task["projectId"], tid)
        output_message(f"Deleted {len(task_ids)} task(s).", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("move")
@click.argument("task_id")
@click.option("--project", "-p", required=True, help="Target project name or ID")
@click.pass_context
def task_move(ctx: click.Context, task_id: str, project: str) -> None:
    """Move a task to a different project (V2)."""
    if is_dry_run(ctx):
        output_dry_run("task.move", {"task_id": task_id, "project": project}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        to_project = _resolve_project_id(client, project)
        client.v2.move_tasks([{
            "taskId": task_id,
            "fromProjectId": task["projectId"],
            "toProjectId": to_project,
        }])
        output_message(f"Task {task_id} moved to {project}.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("search")
@click.argument("query")
@click.option("--limit", "-n", type=int, default=20)
@click.option("--project", "-p", default=None, help="Filter by project name or ID")
@click.option("--tag", "-t", multiple=True, help="Filter by tag")
@click.option("--priority", type=click.Choice(["none", "low", "medium", "high"]), default=None)
@click.pass_context
def task_search(
    ctx: click.Context,
    query: str,
    limit: int,
    project: str | None,
    tag: tuple[str, ...],
    priority: str | None,
) -> None:
    """Search tasks by text with optional filters."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        tasks = client.get_all_tasks()
        q = query.lower()
        matches = [
            t
            for t in tasks
            if q in t.get("title", "").lower() or q in t.get("content", "").lower()
        ]
        if project:
            pid = _resolve_project_id(client, project)
            matches = [t for t in matches if t.get("projectId") == pid]
        if priority:
            p = PRIORITY_MAP[priority]
            matches = [t for t in matches if t.get("priority", 0) == p]
        if tag:
            tag_set = set(tag)
            matches = [t for t in matches if tag_set.intersection(set(t.get("tags", [])))]
        formatted = [_format_task(t) for t in matches]
        output_list(
            formatted,
            columns=["id", "title", "priority", "dueDate", "projectId"],
            ctx=ctx,
            limit=limit,
        )
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("today")
@click.pass_context
def task_today(ctx: click.Context) -> None:
    """List tasks due today."""
    ctx.invoke(task_list, due="today")


@task_group.command("overdue")
@click.pass_context
def task_overdue(ctx: click.Context) -> None:
    """List overdue tasks."""
    ctx.invoke(task_list, due="overdue")


@task_group.command("completed")
@click.option("--from", "from_date", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default=None, help="End date (YYYY-MM-DD)")
@click.option("--limit", "-n", type=int, default=50)
@click.pass_context
def task_completed(ctx: click.Context, from_date: str | None, to_date: str | None, limit: int) -> None:
    """List completed tasks (V2)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        now = datetime.now()
        fd = datetime.fromisoformat(from_date) if from_date else now - timedelta(days=30)
        td = datetime.fromisoformat(to_date) if to_date else now
        tasks = client.v2.get_completed_tasks(fd, td, limit=_request_page_limit(ctx, limit))
        formatted = [_format_task(t) for t in tasks]
        output_list(
            formatted,
            columns=["id", "title", "priority", "dueDate"],
            title="Completed Tasks",
            ctx=ctx,
            limit=limit,
        )
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("trash")
@click.option("--limit", "-n", type=int, default=50)
@click.pass_context
def task_trash(ctx: click.Context, limit: int) -> None:
    """List deleted tasks in trash (V2)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        result = client.v2.get_deleted_tasks(limit=_request_page_limit(ctx, limit))
        tasks = result.get("tasks", []) if isinstance(result, dict) else result
        formatted = [_format_task(t) for t in tasks]
        output_list(
            formatted,
            columns=["id", "title", "priority"],
            title="Trash",
            ctx=ctx,
            limit=limit,
        )
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("pin")
@click.argument("task_id")
@click.pass_context
def task_pin(ctx: click.Context, task_id: str) -> None:
    """Pin a task (V2)."""
    if is_dry_run(ctx):
        output_dry_run("task.pin", {"task_id": task_id}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        client.v2.batch_tasks(update=[{
            "id": task_id,
            "projectId": task["projectId"],
            "pinnedTime": now,
        }])
        output_message(f"Task {task_id} pinned.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("unpin")
@click.argument("task_id")
@click.pass_context
def task_unpin(ctx: click.Context, task_id: str) -> None:
    """Unpin a task (V2)."""
    if is_dry_run(ctx):
        output_dry_run("task.unpin", {"task_id": task_id}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        client.v2.batch_tasks(update=[{
            "id": task_id,
            "projectId": task["projectId"],
            "pinnedTime": None,
        }])
        output_message(f"Task {task_id} unpinned.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@task_group.command("batch-add")
@click.option("--file", "-f", "filepath", required=True, type=click.Path(exists=True), help="JSON file with task list")
@click.pass_context
def task_batch_add(ctx: click.Context, filepath: str) -> None:
    """Bulk create tasks from a JSON file."""
    import json

    try:
        with open(filepath) as f:
            tasks = json.load(f)
        if not isinstance(tasks, list):
            tasks = [tasks]
        if is_dry_run(ctx):
            output_dry_run(
                "task.batch-add",
                {"file": filepath, "count": len(tasks), "tasks": tasks},
                ctx,
            )
            return

        client = get_client(ctx.obj.get("profile", "default"))
        client.v2.batch_tasks(add=tasks)
        output_message(f"Created {len(tasks)} task(s) from {filepath}.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


# ── Attachment subgroup ───────────────────────────────────────


@task_group.group("attachment")
def attachment_group() -> None:
    """Manage task attachments."""


@attachment_group.command("list")
@click.argument("task_id")
@click.pass_context
def attachment_list(ctx: click.Context, task_id: str) -> None:
    """List attachments on a task."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        attachments = [_format_attachment(a) for a in task.get("attachments", [])]
        output_list(
            attachments,
            columns=["id", "fileName", "fileType", "size", "path"],
            title="Attachments",
            ctx=ctx,
        )
    except Exception as e:
        _handle_task_error(e, ctx)


@attachment_group.command("add")
@click.argument("task_id")
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--project", "project_id", default=None, help="Project ID (auto-detected if omitted)")
@click.option("--file-type", default=None, help="Override TickTick fileType, e.g. IMAGE or PDF")
@click.option(
    "--no-content-link",
    is_flag=True,
    help="Attach the file without appending TickTick's inline markdown marker.",
)
@click.pass_context
def attachment_add(
    ctx: click.Context,
    task_id: str,
    file_path: str,
    project_id: str | None,
    file_type: str | None,
    no_content_link: bool,
) -> None:
    """Upload and attach a file to a task."""
    path = Path(file_path).expanduser()
    inferred_file_type = file_type or _infer_attachment_file_type(path)
    insert_content_link = not no_content_link
    dry_run_id = _generate_object_id()
    details = {
        "task_id": task_id,
        "project_id": project_id,
        "file": str(path),
        "fileName": path.name,
        "fileType": inferred_file_type,
        "size": path.stat().st_size,
        "insert_content_link": insert_content_link,
        "markdown": (
            _format_attachment_markdown(dry_run_id, inferred_file_type, path.name)
            if insert_content_link
            else None
        ),
    }
    if is_dry_run(ctx):
        output_dry_run("task.attachment.add", details, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        result = client.v2.add_task_attachment(
            task_id,
            str(path),
            project_id=project_id,
            insert_content_link=insert_content_link,
            file_type=file_type,
        )
        attachment = _format_attachment(result.get("attachment", {}))
        attachment["markdown"] = result.get("markdown")
        attachment["contentLinked"] = result.get("contentLinked", False)
        output_item(attachment, ctx, message="Attachment added.")
    except Exception as e:
        _handle_task_error(e, ctx)


# ── Comment subgroup ──────────────────────────────────────────


@task_group.group("comment")
def comment_group() -> None:
    """Manage task comments."""


@comment_group.command("list")
@click.argument("task_id")
@click.option("--project", "project_id", default=None, help="Project ID (auto-detected if omitted)")
@click.pass_context
def comment_list(ctx: click.Context, task_id: str, project_id: str | None) -> None:
    """List comments on a task."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        if not project_id:
            task = client.v2.get_task(task_id)
            project_id = task.get("projectId", "")
        raw = client.v2.get_task_comments(project_id, task_id)
        comments = [Comment(**c).to_output() for c in raw]
        output_list(comments, columns=["id", "title", "createdTime"], title="Comments", ctx=ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@comment_group.command("add")
@click.argument("task_id")
@click.argument("text")
@click.option("--project", "project_id", default=None, help="Project ID (auto-detected if omitted)")
@click.pass_context
def comment_add(ctx: click.Context, task_id: str, text: str, project_id: str | None) -> None:
    """Add a comment to a task."""
    if is_dry_run(ctx):
        output_dry_run("task.comment.add", {"task_id": task_id, "text": text}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        if not project_id:
            task = client.v2.get_task(task_id)
            project_id = task.get("projectId", "")
        client.v2.create_task_comment(project_id, task_id, text)
        output_message("Comment added.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


@comment_group.command("delete")
@click.argument("task_id")
@click.argument("comment_id")
@click.option("--project", "project_id", default=None, help="Project ID (auto-detected if omitted)")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def comment_delete(ctx: click.Context, task_id: str, comment_id: str, project_id: str | None, yes: bool) -> None:
    """Delete a comment from a task."""
    if is_dry_run(ctx):
        output_dry_run("task.comment.delete", {"comment_id": comment_id}, ctx)
        return

    if not yes:
        click.confirm(f"Delete comment {comment_id} from task {task_id}?", abort=True)
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        if not project_id:
            task = client.v2.get_task(task_id)
            project_id = task.get("projectId", "")
        client.v2.delete_task_comment(project_id, task_id, comment_id)
        output_message("Comment deleted.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


# ── Activity command ──────────────────────────────────────────


@task_group.command("activity")
@click.argument("task_id")
@click.pass_context
def task_activity(ctx: click.Context, task_id: str) -> None:
    """Show change history for a task."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        raw = client.v2.get_task_activities(task_id)
        activities = [Activity(**a).to_output() for a in raw]
        output_list(activities, columns=["id", "action", "when"], title="Activities", ctx=ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


# ── Duplicate command ─────────────────────────────────────────


@task_group.command("duplicate")
@click.argument("task_id")
@click.pass_context
def task_duplicate(ctx: click.Context, task_id: str) -> None:
    """Duplicate a task."""
    if is_dry_run(ctx):
        output_dry_run("task.duplicate", {"task_id": task_id}, ctx)
        return
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        new_task = dict(task)
        new_task["id"] = _generate_object_id()
        new_task["title"] = task.get("title", "") + " (copy)"
        # Remove server-generated fields
        for key in ("etag", "sortOrder", "modifiedTime", "createdTime"):
            new_task.pop(key, None)
        client.v2.batch_tasks(add=[new_task])
        output_message(f"Task duplicated. New ID: {new_task['id']}", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


# ── Convert (task ↔ note) ─────────────────────────────────────


@task_group.command("convert")
@click.argument("task_id")
@click.option(
    "--to",
    "target_kind",
    required=True,
    type=click.Choice(["note", "task"]),
    help="Convert to 'note' or back to 'task'",
)
@click.pass_context
def task_convert(ctx: click.Context, task_id: str, target_kind: str) -> None:
    """Convert a task to a note or a note back to a task."""
    kind_value = "NOTE" if target_kind == "note" else "TEXT"

    if is_dry_run(ctx):
        output_dry_run("task.convert", {"task_id": task_id, "kind": kind_value}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        client.v2.batch_tasks(update=[{
            "id": task_id,
            "projectId": task.get("projectId", ""),
            "kind": kind_value,
        }])
        output_message(f"Task {task_id} converted to {target_kind}.", ctx)
    except Exception as e:
        _handle_task_error(e, ctx)


# ── Helpers ───────────────────────────────────────────────────


def _resolve_project_id(client: Any, name_or_id: str) -> str:
    """Resolve project name to ID. If it looks like an ID, return as-is."""
    if _looks_like_object_id(name_or_id):
        return name_or_id  # Likely a MongoDB-style ID
    projects = _list_projects(client)
    for proj in projects:
        if proj.get("name", "").lower() == name_or_id.lower():
            return proj["id"]
    return name_or_id  # Fallback: treat as ID


def _is_rate_limit_error(error: Exception) -> bool:
    """Return whether an API error is a TickTick rate-limit failure."""
    message = str(error).lower()
    return "429" in message or "rate limit" in message


def _can_edit_task_with_v1(client: Any, update: dict[str, Any]) -> bool:
    """Return whether a task edit can fall back to the official V1 API."""
    return bool(getattr(client, "has_v1", False)) and set(update).issubset(_V1_TASK_EDIT_FIELDS)


def _looks_like_object_id(value: str) -> bool:
    """Return whether a value looks like TickTick's 24-character object IDs."""
    return len(value) == 24 and value.isalnum()


def _list_projects(client: Any) -> list[dict[str, Any]]:
    """List projects, preferring V1 because V2 sync can be rate-limited."""
    if getattr(client, "has_v1", False):
        return client.v1.list_projects()
    if hasattr(client, "list_projects"):
        return client.list_projects()
    return []


def _resolve_folder_id(client: Any, name_or_id: str) -> str:
    """Resolve a folder/group name to ID when V2 sync is available."""
    if _looks_like_object_id(name_or_id):
        return name_or_id

    try:
        folders = client.get_all_project_groups()
    except Exception as exc:
        raise ValueError(
            f"Could not resolve folder '{name_or_id}' by name because TickTick V2 sync failed. "
            "Use --folder-id if you know the folder/group ID."
        ) from exc

    for folder in folders:
        if folder.get("name", "").lower() == name_or_id.lower():
            return folder["id"]
    raise ValueError(f"Folder '{name_or_id}' not found. Use --folder-id if you know the folder/group ID.")


def _resolve_project_ids_for_folder(client: Any, folder_id: str) -> set[str]:
    """Return project IDs that belong to a TickTick folder/group."""
    project_ids = {
        project["id"]
        for project in _list_projects(client)
        if project.get("groupId") == folder_id and project.get("id")
    }
    if not project_ids:
        raise ValueError(f"No projects found in folder/group {folder_id}.")
    return project_ids


def _get_project_tasks_v1(client: Any, project_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Fetch tasks from V1 project data, preserving project/group context."""
    tasks: list[dict[str, Any]] = []
    for project in _list_projects(client):
        project_id = project.get("id")
        if not project_id or (project_ids is not None and project_id not in project_ids):
            continue

        data = client.v1.get_project_with_data(project_id)
        project_data = data.get("project") or project
        project_name = project_data.get("name") or project.get("name", "")
        group_id = project_data.get("groupId") or project.get("groupId", "")
        column_names = {
            column.get("id"): column.get("name")
            for column in data.get("columns", [])
            if column.get("id")
        }

        for raw_task in data.get("tasks", []):
            task = dict(raw_task)
            task.setdefault("projectId", project_id)
            task.setdefault("projectName", project_name)
            if group_id:
                task.setdefault("groupId", group_id)
            column_id = task.get("columnId")
            if column_id and column_id in column_names:
                task.setdefault("columnName", column_names[column_id])
            tasks.append(task)
    return tasks


def _filter_by_due(tasks: list[dict], due_filter: str) -> list[dict]:
    """Filter tasks by due date."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    def get_due(t: dict) -> str | None:
        d = t.get("dueDate", "")
        return d[:10] if d else None

    if due_filter == "today":
        return [t for t in tasks if get_due(t) == today_str]
    elif due_filter == "overdue":
        return [t for t in tasks if get_due(t) and get_due(t) < today_str]
    elif due_filter == "this-week":
        week_end = (now + timedelta(days=7)).strftime("%Y-%m-%d")
        return [t for t in tasks if get_due(t) and today_str <= get_due(t) <= week_end]
    else:
        return [t for t in tasks if get_due(t) == due_filter]


def _sort_tasks(tasks: list[dict], sort_key: str) -> list[dict]:
    """Sort tasks by given key."""
    key_map = {
        "due": lambda t: t.get("dueDate") or "9999",
        "priority": lambda t: -t.get("priority", 0),
        "title": lambda t: t.get("title", "").lower(),
        "created": lambda t: t.get("createdTime") or "",
        "sortOrder": lambda t: (t.get("sortOrder") is None, t.get("sortOrder") or 0),
    }
    return sorted(tasks, key=key_map.get(sort_key, key_map["due"]))


def _get_task_any(client: Any, task_id: str) -> dict:
    """Get task from either V2 or V1."""
    if client.has_v2:
        try:
            return client.v2.get_task(task_id)
        except Exception as v2_error:
            if not (client.has_v1 and _is_rate_limit_error(v2_error)):
                raise
    return _find_task_v1(client, task_id)


def _find_task_v1(client: Any, task_id: str) -> dict:
    """Find a task and its project through V1 project data."""
    for task in _get_project_tasks_v1(client):
        if task.get("id") == task_id:
            return task
    from ticktick_cli.exceptions import NotFoundError
    raise NotFoundError(f"Task {task_id} not found in any project.")
