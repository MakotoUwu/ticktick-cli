"""Subtask commands — set/unset parent-child relationships (V2 only)."""

from __future__ import annotations

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_list, output_message, output_error


@click.group("subtask")
def subtask_group() -> None:
    """Manage subtasks / parent-child task relationships (V2)."""


@subtask_group.command("set")
@click.argument("task_id")
@click.option("--parent", required=True, help="Parent task ID")
@click.pass_context
def subtask_set(ctx: click.Context, task_id: str, parent: str) -> None:
    """Make a task a subtask of another task."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        client.v2.set_task_parent(task_id, task["projectId"], parent)
        output_message(f"Task {task_id} is now a subtask of {parent}.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@subtask_group.command("unset")
@click.argument("task_id")
@click.option("--parent", required=True, help="Current parent task ID")
@click.pass_context
def subtask_unset(ctx: click.Context, task_id: str, parent: str) -> None:
    """Remove a task from being a subtask."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        task = client.v2.get_task(task_id)
        client.v2.unset_task_parent(task_id, task["projectId"], parent)
        output_message(f"Task {task_id} removed from parent {parent}.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@subtask_group.command("list")
@click.argument("parent_task_id")
@click.pass_context
def subtask_list(ctx: click.Context, parent_task_id: str) -> None:
    """List subtasks of a parent task."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        # Get all tasks, filter by parentId
        tasks = client.get_all_tasks()
        subtasks = [t for t in tasks if t.get("parentId") == parent_task_id]
        formatted = [
            {
                "id": t.get("id", ""),
                "title": t.get("title", ""),
                "status": "completed" if t.get("status", 0) >= 2 else "active",
                "priority": t.get("priority", 0),
            }
            for t in subtasks
        ]
        output_list(formatted, columns=["id", "title", "status", "priority"], title="Subtasks", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)
