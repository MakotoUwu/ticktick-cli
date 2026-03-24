"""Template commands — manage task templates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import click

from ticktick_cli.api.v2 import _generate_object_id
from ticktick_cli.auth import get_client
from ticktick_cli.models.template import TaskTemplate
from ticktick_cli.output import (
    is_dry_run,
    output_dry_run,
    output_error,
    output_existing_item,
    output_item,
    output_list,
    output_message,
)


@click.group("template")
def template_group() -> None:
    """Manage task templates."""


@template_group.command("list")
@click.pass_context
def template_list(ctx: click.Context) -> None:
    """List all task templates."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        result = client.v2.get_templates()
        raw = result.get("taskTemplates", []) if isinstance(result, dict) else []
        templates = [TaskTemplate(**t).to_output() for t in raw]
        output_list(templates, columns=["id", "title", "tags"], title="Templates", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@template_group.command("show")
@click.argument("template_id")
@click.pass_context
def template_show(ctx: click.Context, template_id: str) -> None:
    """Show details of a task template."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        result = client.v2.get_templates()
        raw = result.get("taskTemplates", []) if isinstance(result, dict) else []
        match = next((t for t in raw if t.get("id") == template_id), None)
        if not match:
            output_error(f"Template {template_id} not found.", ctx)
            raise SystemExit(1)
        output_item(TaskTemplate(**match).to_output(), ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@template_group.command("create")
@click.argument("title")
@click.option("--content", "-c", default=None, help="Template body text")
@click.option("--items", default=None, help="Checklist items (comma-separated)")
@click.option("--tag", "-t", multiple=True, help="Tags (repeatable)")
@click.option("--if-not-exists", "if_not_exists", is_flag=True, help="Skip creation if a template with the same title exists")
@click.pass_context
def template_create(
    ctx: click.Context,
    title: str,
    content: str | None,
    items: str | None,
    tag: tuple[str, ...],
    if_not_exists: bool,
) -> None:
    """Create a new task template."""
    template_data: dict[str, Any] = {
        "id": _generate_object_id(),
        "createdTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
        "title": title,
        "tags": list(tag),
    }
    if content:
        template_data["content"] = content
    if items:
        template_data["items"] = [i.strip() for i in items.split(",")]

    if is_dry_run(ctx):
        output_dry_run("template.create", template_data, ctx)
        return

    if if_not_exists:
        try:
            client = get_client(ctx.obj.get("profile", "default"))
            result = client.v2.get_templates()
            raw = result.get("taskTemplates", []) if isinstance(result, dict) else []
            for t in raw:
                if t.get("title", "").lower() == title.lower():
                    output_existing_item(TaskTemplate(**t).to_output(), ctx)
                    return
        except Exception as e:
            output_error(str(e), ctx)
            raise SystemExit(1) from None

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_templates(add=[template_data])
        output_message(f"Template created: {title} (id: {template_data['id']})", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@template_group.command("delete")
@click.argument("template_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def template_delete(ctx: click.Context, template_id: str, yes: bool) -> None:
    """Delete a task template."""
    if is_dry_run(ctx):
        output_dry_run("template.delete", {"template_id": template_id}, ctx)
        return

    if not yes:
        click.confirm(f"Delete template {template_id}?", abort=True)

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_templates(delete=[template_id])
        output_message(f"Template {template_id} deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
