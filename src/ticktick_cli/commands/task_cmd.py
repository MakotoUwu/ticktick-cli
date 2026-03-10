"""Task commands — full CRUD, search, batch operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_list, output_item, output_message, output_error

PRIORITY_MAP = {"none": 0, "low": 1, "medium": 3, "high": 5}
PRIORITY_REVERSE = {0: "none", 1: "low", 3: "medium", 5: "high"}


def _format_task(task: dict[str, Any]) -> dict[str, Any]:
    """Normalize task dict for output."""
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
        "pinnedTime": task.get("pinnedTime"),
        "items": task.get("items", []),  # subtask checklist items
    }


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
@click.option("--due", "-d", default=None, help="Due date (YYYY-MM-DD, 'today', 'tomorrow', '+3d')")
@click.option("--start", default=None, help="Start date")
@click.option("--tag", "-t", multiple=True, help="Tags (repeatable)")
@click.option("--all-day", is_flag=True, help="Mark as all-day task")
@click.option("--repeat", default=None, help="Recurrence RRULE (e.g., RRULE:FREQ=DAILY)")
@click.option("--reminder", multiple=True, help="Reminder triggers")
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
    all_day: bool,
    repeat: str | None,
    reminder: tuple[str, ...],
) -> None:
    """Create a new task."""
    client = get_client(ctx.obj.get("profile", "default"))

    task_data: dict[str, Any] = {"title": title}
    if project:
        task_data["projectId"] = _resolve_project_id(client, project)
    if content:
        task_data["content"] = content
    task_data["priority"] = PRIORITY_MAP[priority]
    if due:
        task_data["dueDate"] = _parse_date(due)
    if start:
        task_data["startDate"] = _parse_date(start)
    if tag:
        task_data["tags"] = list(tag)
    if all_day:
        task_data["isAllDay"] = True
    if repeat:
        task_data["repeatFlag"] = repeat
    if reminder:
        task_data["reminders"] = list(reminder)

    try:
        if client.has_v2:
            result = client.v2.batch_tasks(add=[task_data])
            output_message(f"Task created: {title}", ctx)
        else:
            result = client.v1.create_task(task_data)
            output_item(_format_task(result), ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("list")
@click.option("--project", "-p", default=None, help="Filter by project name or ID")
@click.option(
    "--status",
    type=click.Choice(["uncompleted", "completed", "abandoned", "all"]),
    default="uncompleted",
)
@click.option("--priority", type=click.Choice(["none", "low", "medium", "high"]), default=None)
@click.option("--due", default=None, help="Filter: today, overdue, this-week, YYYY-MM-DD")
@click.option("--tag", "-t", multiple=True, help="Filter by tag")
@click.option("--sort", type=click.Choice(["due", "priority", "title", "created"]), default="due")
@click.option("--limit", "-n", type=int, default=50, help="Max results")
@click.pass_context
def task_list(
    ctx: click.Context,
    project: str | None,
    status: str,
    priority: str | None,
    due: str | None,
    tag: tuple[str, ...],
    sort: str,
    limit: int,
) -> None:
    """List tasks with optional filters."""
    client = get_client(ctx.obj.get("profile", "default"))

    try:
        if status == "completed" and client.has_v2:
            now = datetime.now()
            tasks = client.v2.get_completed_tasks(now - timedelta(days=365), now, limit=limit)
        elif client.has_v2:
            tasks = client.get_all_tasks()
        else:
            # V1: need to list per project
            projects = client.v1.list_projects()
            tasks = []
            for proj in projects:
                data = client.v1.get_project_with_data(proj["id"])
                tasks.extend(data.get("tasks", []))

        # Apply filters
        if project:
            pid = _resolve_project_id(client, project)
            tasks = [t for t in tasks if t.get("projectId") == pid]
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

        # Limit
        tasks = tasks[:limit]

        formatted = [_format_task(t) for t in tasks]
        columns = ["id", "title", "priority", "dueDate", "projectId", "tags"]
        output_list(formatted, columns=columns, title="Tasks", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


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
        output_error(str(e), ctx)
        raise SystemExit(1)


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
@click.pass_context
def task_edit(ctx: click.Context, task_id: str, **kwargs: Any) -> None:
    """Edit a task's properties."""
    client = get_client(ctx.obj.get("profile", "default"))

    update: dict[str, Any] = {"id": task_id}
    if kwargs.get("title"):
        update["title"] = kwargs["title"]
    if kwargs.get("content"):
        update["content"] = kwargs["content"]
    if kwargs.get("priority"):
        update["priority"] = PRIORITY_MAP[kwargs["priority"]]
    if kwargs.get("due"):
        update["dueDate"] = _parse_date(kwargs["due"])
    if kwargs.get("start"):
        update["startDate"] = _parse_date(kwargs["start"])
    if kwargs.get("project"):
        update["projectId"] = _resolve_project_id(client, kwargs["project"])
    if kwargs.get("tag"):
        update["tags"] = list(kwargs["tag"])
    if kwargs.get("repeat"):
        update["repeatFlag"] = kwargs["repeat"]
    if kwargs.get("column"):
        update["columnId"] = kwargs["column"]

    try:
        if client.has_v2:
            # Need projectId for V2 update
            if "projectId" not in update:
                task = client.v2.get_task(task_id)
                update["projectId"] = task.get("projectId", "")
            client.v2.batch_tasks(update=[update])
        else:
            client.v1.update_task(task_id, update)
        output_message(f"Task {task_id} updated.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("done")
@click.argument("task_ids", nargs=-1, required=True)
@click.pass_context
def task_done(ctx: click.Context, task_ids: tuple[str, ...]) -> None:
    """Mark task(s) as completed."""
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
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("abandon")
@click.argument("task_ids", nargs=-1, required=True)
@click.pass_context
def task_abandon(ctx: click.Context, task_ids: tuple[str, ...]) -> None:
    """Mark task(s) as 'won't do' (V2 only)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        updates = []
        for tid in task_ids:
            task = client.v2.get_task(tid)
            updates.append({"id": tid, "projectId": task["projectId"], "status": -1})
        client.v2.batch_tasks(update=updates)
        output_message(f"Abandoned {len(task_ids)} task(s).", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("delete")
@click.argument("task_ids", nargs=-1, required=True)
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def task_delete(ctx: click.Context, task_ids: tuple[str, ...], yes: bool) -> None:
    """Delete task(s)."""
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
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("move")
@click.argument("task_id")
@click.option("--project", "-p", required=True, help="Target project name or ID")
@click.pass_context
def task_move(ctx: click.Context, task_id: str, project: str) -> None:
    """Move a task to a different project (V2)."""
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
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("search")
@click.argument("query")
@click.option("--limit", "-n", type=int, default=20)
@click.pass_context
def task_search(ctx: click.Context, query: str, limit: int) -> None:
    """Search tasks by text (searches title and content)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        tasks = client.get_all_tasks()
        q = query.lower()
        matches = [
            t
            for t in tasks
            if q in t.get("title", "").lower() or q in t.get("content", "").lower()
        ][:limit]
        formatted = [_format_task(t) for t in matches]
        output_list(formatted, columns=["id", "title", "priority", "dueDate", "projectId"], ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


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
        tasks = client.v2.get_completed_tasks(fd, td, limit=limit)
        formatted = [_format_task(t) for t in tasks]
        output_list(formatted, columns=["id", "title", "priority", "dueDate"], title="Completed Tasks", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("trash")
@click.option("--limit", "-n", type=int, default=50)
@click.pass_context
def task_trash(ctx: click.Context, limit: int) -> None:
    """List deleted tasks in trash (V2)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        result = client.v2.get_deleted_tasks(limit=limit)
        tasks = result.get("tasks", []) if isinstance(result, dict) else result
        formatted = [_format_task(t) for t in tasks[:limit]]
        output_list(formatted, columns=["id", "title", "priority"], title="Trash", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("pin")
@click.argument("task_id")
@click.pass_context
def task_pin(ctx: click.Context, task_id: str) -> None:
    """Pin a task (V2)."""
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
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("unpin")
@click.argument("task_id")
@click.pass_context
def task_unpin(ctx: click.Context, task_id: str) -> None:
    """Unpin a task (V2)."""
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
        output_error(str(e), ctx)
        raise SystemExit(1)


@task_group.command("batch-add")
@click.option("--file", "-f", "filepath", required=True, type=click.Path(exists=True), help="JSON file with task list")
@click.pass_context
def task_batch_add(ctx: click.Context, filepath: str) -> None:
    """Bulk create tasks from a JSON file."""
    import json

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        with open(filepath) as f:
            tasks = json.load(f)
        if not isinstance(tasks, list):
            tasks = [tasks]
        client.v2.batch_tasks(add=tasks)
        output_message(f"Created {len(tasks)} task(s) from {filepath}.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


# ── Helpers ───────────────────────────────────────────────────


def _resolve_project_id(client: Any, name_or_id: str) -> str:
    """Resolve project name to ID. If it looks like an ID, return as-is."""
    if len(name_or_id) == 24 and name_or_id.isalnum():
        return name_or_id  # Likely a MongoDB-style ID
    projects = client.list_projects() if hasattr(client, "list_projects") else []
    for proj in projects:
        if proj.get("name", "").lower() == name_or_id.lower():
            return proj["id"]
    return name_or_id  # Fallback: treat as ID


def _parse_date(date_str: str) -> str:
    """Parse human date strings to ISO format."""
    now = datetime.now()
    lower = date_str.lower().strip()

    if lower == "today":
        return now.strftime("%Y-%m-%dT00:00:00.000+0000")
    elif lower == "tomorrow":
        return (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000+0000")
    elif lower.startswith("+") and lower.endswith("d"):
        days = int(lower[1:-1])
        return (now + timedelta(days=days)).strftime("%Y-%m-%dT00:00:00.000+0000")
    else:
        # Assume ISO date
        try:
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
        except ValueError:
            return date_str


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
    }
    return sorted(tasks, key=key_map.get(sort_key, key_map["due"]))


def _get_task_any(client: Any, task_id: str) -> dict:
    """Get task from either V2 or V1."""
    if client.has_v2:
        return client.v2.get_task(task_id)
    return _find_task_v1(client, task_id)


def _find_task_v1(client: Any, task_id: str) -> dict:
    """Find task via V1 (requires searching across projects)."""
    projects = client.v1.list_projects()
    for proj in projects:
        try:
            return client.v1.get_task(proj["id"], task_id)
        except Exception:
            continue
    from ticktick_cli.exceptions import NotFoundError
    raise NotFoundError(f"Task {task_id} not found in any project.")
