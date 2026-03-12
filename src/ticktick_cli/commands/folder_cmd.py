"""Project folder commands — list, create, rename, delete."""

from __future__ import annotations

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import (
    is_dry_run,
    output_dry_run,
    output_error,
    output_list,
    output_message,
)


@click.group("folder")
def folder_group() -> None:
    """Manage project folders/groups (V2)."""


@folder_group.command("list")
@click.pass_context
def folder_list(ctx: click.Context) -> None:
    """List all project folders."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        groups = client.get_all_project_groups()
        formatted = [{"id": g.get("id", ""), "name": g.get("name", "")} for g in groups]
        output_list(formatted, columns=["id", "name"], title="Folders", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@folder_group.command("create")
@click.argument("name")
@click.pass_context
def folder_create(ctx: click.Context, name: str) -> None:
    """Create a project folder."""
    if is_dry_run(ctx):
        output_dry_run("folder.create", {"name": name}, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_project_groups(add=[{"name": name, "listType": "group"}])
        output_message(f"Folder '{name}' created.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@folder_group.command("rename")
@click.argument("folder_id")
@click.argument("new_name")
@click.pass_context
def folder_rename(ctx: click.Context, folder_id: str, new_name: str) -> None:
    """Rename a project folder."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_project_groups(
            update=[{"id": folder_id, "name": new_name, "listType": "group"}]
        )
        output_message(f"Folder {folder_id} renamed to '{new_name}'.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@folder_group.command("delete")
@click.argument("folder_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def folder_delete(ctx: click.Context, folder_id: str, yes: bool) -> None:
    """Delete a project folder."""
    if is_dry_run(ctx):
        output_dry_run("folder.delete", {"folder_id": folder_id}, ctx)
        return

    if not yes:
        click.confirm(f"Delete folder {folder_id}?", abort=True)
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_project_groups(delete=[folder_id])
        output_message(f"Folder {folder_id} deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
