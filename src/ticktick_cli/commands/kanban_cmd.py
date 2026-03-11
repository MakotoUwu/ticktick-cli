"""Kanban column commands — list, create, edit, delete (V2 only)."""

from __future__ import annotations

from typing import Any

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_error, output_list, output_message


@click.group("column")
def column_group() -> None:
    """Manage kanban columns (V2)."""


@column_group.command("list")
@click.argument("project_id")
@click.pass_context
def column_list(ctx: click.Context, project_id: str) -> None:
    """List kanban columns for a project."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        columns = client.v2.get_columns(project_id)
        formatted = [
            {"id": c.get("id", ""), "name": c.get("name", ""), "sortOrder": c.get("sortOrder", 0)}
            for c in columns
        ]
        output_list(formatted, columns=["id", "name", "sortOrder"], title="Kanban Columns", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@column_group.command("create")
@click.argument("project_id")
@click.argument("name")
@click.option("--sort-order", type=int, default=None)
@click.pass_context
def column_create(ctx: click.Context, project_id: str, name: str, sort_order: int | None) -> None:
    """Create a kanban column."""
    client = get_client(ctx.obj.get("profile", "default"))
    data: dict[str, Any] = {"projectId": project_id, "name": name}
    if sort_order is not None:
        data["sortOrder"] = sort_order
    try:
        client.v2.batch_columns(add=[data])
        output_message(f"Column '{name}' created.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@column_group.command("edit")
@click.argument("column_id")
@click.option("--project", required=True, help="Project ID the column belongs to")
@click.option("--name", default=None)
@click.option("--sort-order", type=int, default=None)
@click.pass_context
def column_edit(
    ctx: click.Context, column_id: str, project: str, name: str | None, sort_order: int | None
) -> None:
    """Edit a kanban column."""
    client = get_client(ctx.obj.get("profile", "default"))
    update: dict[str, Any] = {"id": column_id, "projectId": project}
    if name:
        update["name"] = name
    if sort_order is not None:
        update["sortOrder"] = sort_order
    try:
        client.v2.batch_columns(update=[update])
        output_message(f"Column {column_id} updated.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@column_group.command("delete")
@click.argument("column_id")
@click.option("--project", required=True, help="Project ID")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def column_delete(ctx: click.Context, column_id: str, project: str, yes: bool) -> None:
    """Delete a kanban column."""
    if not yes:
        click.confirm(f"Delete column {column_id}?", abort=True)
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_columns(delete=[{"columnId": column_id, "projectId": project}])
        output_message(f"Column {column_id} deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
