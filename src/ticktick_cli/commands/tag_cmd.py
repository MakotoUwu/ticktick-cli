"""Tag commands — list, create, edit, rename, merge, delete (V2 only)."""

from __future__ import annotations

from typing import Any

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_error, output_list, output_message


def _format_tag(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": t.get("name", ""),
        "label": t.get("label", t.get("name", "")),
        "color": t.get("color", ""),
        "parent": t.get("parent", ""),
        "sortType": t.get("sortType", ""),
    }


@click.group("tag")
def tag_group() -> None:
    """Manage tags (V2)."""


@tag_group.command("list")
@click.pass_context
def tag_list(ctx: click.Context) -> None:
    """List all tags."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        tags = client.get_all_tags()
        formatted = [_format_tag(t) for t in tags]
        output_list(formatted, columns=["name", "label", "color", "parent"], title="Tags", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@tag_group.command("create")
@click.argument("label")
@click.option("--color", default=None, help="Hex color")
@click.option("--parent", default=None, help="Parent tag name for nesting")
@click.pass_context
def tag_create(ctx: click.Context, label: str, color: str | None, parent: str | None) -> None:
    """Create a tag."""
    client = get_client(ctx.obj.get("profile", "default"))
    tag: dict[str, Any] = {"label": label, "name": label.lower().replace(" ", "")}
    if color:
        tag["color"] = color
    if parent:
        tag["parent"] = parent
    try:
        client.v2.batch_tags(add=[tag])
        output_message(f"Tag '{label}' created.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@tag_group.command("edit")
@click.argument("name")
@click.option("--label", default=None)
@click.option("--color", default=None)
@click.option("--parent", default=None)
@click.pass_context
def tag_edit(ctx: click.Context, name: str, label: str | None, color: str | None, parent: str | None) -> None:
    """Edit a tag's properties."""
    client = get_client(ctx.obj.get("profile", "default"))
    update: dict[str, Any] = {"name": name, "rawName": name}
    if label:
        update["label"] = label
    else:
        update["label"] = name  # Required field
    if color:
        update["color"] = color
    if parent:
        update["parent"] = parent
    try:
        client.v2.batch_tags(update=[update])
        output_message(f"Tag '{name}' updated.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@tag_group.command("rename")
@click.argument("old_name")
@click.argument("new_name")
@click.pass_context
def tag_rename(ctx: click.Context, old_name: str, new_name: str) -> None:
    """Rename a tag."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.rename_tag(old_name, new_name)
        output_message(f"Tag '{old_name}' renamed to '{new_name}'.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@tag_group.command("merge")
@click.argument("source")
@click.argument("target")
@click.pass_context
def tag_merge(ctx: click.Context, source: str, target: str) -> None:
    """Merge one tag into another (source is deleted)."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.merge_tags(source, target)
        output_message(f"Tag '{source}' merged into '{target}'.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@tag_group.command("delete")
@click.argument("name")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def tag_delete(ctx: click.Context, name: str, yes: bool) -> None:
    """Delete a tag."""
    if not yes:
        click.confirm(f"Delete tag '{name}'?", abort=True)
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.delete_tag(name)
        output_message(f"Tag '{name}' deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
