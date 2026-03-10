"""Project commands — list, create, show, edit, delete."""

from __future__ import annotations

from typing import Any

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_list, output_item, output_message, output_error


def _format_project(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": p.get("id", ""),
        "name": p.get("name", ""),
        "color": p.get("color", ""),
        "kind": p.get("kind", "TASK"),
        "viewMode": p.get("viewMode", "list"),
        "groupId": p.get("groupId", ""),
        "closed": p.get("closed", False),
    }


@click.group("project")
def project_group() -> None:
    """Manage projects (lists)."""


@project_group.command("list")
@click.option("--include-archived", is_flag=True, help="Include archived projects")
@click.pass_context
def project_list(ctx: click.Context, include_archived: bool) -> None:
    """List all projects."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        projects = client.list_projects()
        if not include_archived:
            projects = [p for p in projects if not p.get("closed")]
        formatted = [_format_project(p) for p in projects]
        output_list(formatted, columns=["id", "name", "color", "kind", "viewMode"], title="Projects", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@project_group.command("create")
@click.argument("name")
@click.option("--color", default=None, help="Hex color (e.g., #F18181)")
@click.option("--kind", type=click.Choice(["TASK", "NOTE"]), default="TASK")
@click.option("--view", type=click.Choice(["list", "kanban", "timeline"]), default="list")
@click.option("--folder", default=None, help="Parent folder ID")
@click.pass_context
def project_create(
    ctx: click.Context, name: str, color: str | None, kind: str, view: str, folder: str | None
) -> None:
    """Create a new project."""
    client = get_client(ctx.obj.get("profile", "default"))
    data: dict[str, Any] = {"name": name, "kind": kind, "viewMode": view}
    if color:
        data["color"] = color
    if folder:
        data["groupId"] = folder
    try:
        if client.has_v2:
            result = client.v2.batch_projects(add=[data])
        else:
            result = client.v1.create_project(data)
        output_message(f"Project '{name}' created.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@project_group.command("show")
@click.argument("identifier")
@click.pass_context
def project_show(ctx: click.Context, identifier: str) -> None:
    """Show project details with tasks (V1: includes tasks + columns)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        pid = _resolve_project(client, identifier)
        if client.has_v1:
            data = client.v1.get_project_with_data(pid)
            output_item({
                **_format_project(data.get("project", data)),
                "task_count": len(data.get("tasks", [])),
                "column_count": len(data.get("columns", [])),
            }, ctx)
        else:
            projects = client.list_projects()
            proj = next((p for p in projects if p["id"] == pid), None)
            if proj:
                output_item(_format_project(proj), ctx)
            else:
                output_error(f"Project {identifier} not found.", ctx)
                raise SystemExit(1)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@project_group.command("edit")
@click.argument("identifier")
@click.option("--name", default=None)
@click.option("--color", default=None)
@click.option("--folder", default=None, help="Folder ID (use 'none' to ungroup)")
@click.pass_context
def project_edit(ctx: click.Context, identifier: str, name: str | None, color: str | None, folder: str | None) -> None:
    """Edit a project's properties."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        pid = _resolve_project(client, identifier)
        update: dict[str, Any] = {"id": pid}
        if name:
            update["name"] = name
        if color:
            update["color"] = color
        if folder:
            update["groupId"] = "NONE" if folder.lower() == "none" else folder
        if client.has_v2:
            # V2 update requires name
            if "name" not in update:
                projects = client.list_projects()
                proj = next((p for p in projects if p["id"] == pid), {})
                update["name"] = proj.get("name", "")
            client.v2.batch_projects(update=[update])
        else:
            client.v1.update_project(pid, update)
        output_message(f"Project {identifier} updated.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@project_group.command("delete")
@click.argument("identifier")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def project_delete(ctx: click.Context, identifier: str, yes: bool) -> None:
    """Delete a project and all its tasks."""
    if not yes:
        click.confirm(f"Delete project '{identifier}' and all its tasks?", abort=True)
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        pid = _resolve_project(client, identifier)
        if client.has_v2:
            client.v2.batch_projects(delete=[pid])
        else:
            client.v1.delete_project(pid)
        output_message(f"Project '{identifier}' deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


def _resolve_project(client: Any, name_or_id: str) -> str:
    """Resolve project name to ID."""
    if len(name_or_id) == 24 and name_or_id.isalnum():
        return name_or_id
    projects = client.list_projects()
    for proj in projects:
        if proj.get("name", "").lower() == name_or_id.lower():
            return proj["id"]
    return name_or_id
