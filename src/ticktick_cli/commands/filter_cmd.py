"""Filter (smart list) commands — CRUD for saved filters."""

from __future__ import annotations

import json
from typing import Any

import click

from ticktick_cli.api.v2 import _generate_object_id
from ticktick_cli.auth import get_client
from ticktick_cli.models.filter import Filter
from ticktick_cli.output import (
    is_dry_run,
    output_dry_run,
    output_error,
    output_item,
    output_list,
    output_message,
)

PRIORITY_MAP = {"high": 5, "medium": 3, "low": 1, "none": 0}
PRIORITY_REVERSE = {5: "high", 3: "medium", 1: "low", 0: "none"}

DATE_OPTIONS = [
    "today", "tomorrow", "thisweek", "nextweek",
    "thismonth", "nextmonth", "overdue", "nodate", "repeat",
]


def _build_rule(
    priorities: list[str] | None = None,
    date: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Build a filter rule JSON string from CLI options."""
    conditions: list[dict[str, Any]] = []

    if priorities:
        values = [PRIORITY_MAP[p] for p in priorities]
        conditions.append({
            "or": values,
            "conditionType": 1,
            "conditionName": "priority",
        })

    if date:
        conditions.append({
            "or": [date],
            "conditionType": 1,
            "conditionName": "dueDate",
        })

    if tags:
        conditions.append({
            "or": tags,
            "conditionType": 1,
            "conditionName": "tag",
        })

    return json.dumps({"and": conditions, "version": 1, "type": 0})


@click.group("filter")
def filter_group() -> None:
    """Manage saved filters (smart lists)."""


@filter_group.command("list")
@click.pass_context
def filter_list(ctx: click.Context) -> None:
    """List saved filters."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        state = client.v2.sync()
        raw_filters = state.get("filters") or []
        filters = [Filter(**f).to_output() for f in raw_filters]
        output_list(filters, columns=["id", "name", "conditions"], title="Filters", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@filter_group.command("show")
@click.argument("filter_id")
@click.pass_context
def filter_show(ctx: click.Context, filter_id: str) -> None:
    """Show details of a saved filter."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        state = client.v2.sync()
        raw_filters = state.get("filters") or []
        match = next((f for f in raw_filters if f.get("id") == filter_id), None)
        if not match:
            output_error(f"Filter {filter_id} not found.", ctx)
            raise SystemExit(1)
        output_item(Filter(**match).to_output(), ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@filter_group.command("create")
@click.argument("name")
@click.option(
    "--priority", "-p",
    multiple=True,
    type=click.Choice(["high", "medium", "low", "none"]),
    help="Priority filter (repeatable)",
)
@click.option(
    "--date", "-d",
    type=click.Choice(DATE_OPTIONS),
    default=None,
    help="Date filter",
)
@click.option("--tag", "-t", multiple=True, help="Tag filter (repeatable)")
@click.pass_context
def filter_create(
    ctx: click.Context,
    name: str,
    priority: tuple[str, ...],
    date: str | None,
    tag: tuple[str, ...],
) -> None:
    """Create a new saved filter."""
    rule = _build_rule(
        priorities=list(priority) if priority else None,
        date=date,
        tags=list(tag) if tag else None,
    )
    filter_data = {
        "id": _generate_object_id(),
        "name": name,
        "sortOrder": -1099511627776,
        "createdTime": "",
        "modifiedTime": "",
        "sortType": "project",
        "rule": rule,
    }

    if is_dry_run(ctx):
        output_dry_run("filter.create", filter_data, ctx)
        return

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        result = client.v2.batch_filters(add=[filter_data])
        output_message(f"Filter created: {name} (id: {filter_data['id']})", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@filter_group.command("edit")
@click.argument("filter_id")
@click.option("--name", default=None, help="New filter name")
@click.option(
    "--priority", "-p",
    multiple=True,
    type=click.Choice(["high", "medium", "low", "none"]),
    help="Priority filter (repeatable)",
)
@click.option(
    "--date", "-d",
    type=click.Choice(DATE_OPTIONS),
    default=None,
    help="Date filter",
)
@click.option("--tag", "-t", multiple=True, help="Tag filter (repeatable)")
@click.pass_context
def filter_edit(
    ctx: click.Context,
    filter_id: str,
    name: str | None,
    priority: tuple[str, ...],
    date: str | None,
    tag: tuple[str, ...],
) -> None:
    """Edit an existing filter."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        # Get current filter from sync
        state = client.v2.sync()
        raw_filters = state.get("filters") or []
        match = next((f for f in raw_filters if f.get("id") == filter_id), None)
        if not match:
            output_error(f"Filter {filter_id} not found.", ctx)
            raise SystemExit(1)

        update_data: dict[str, Any] = {
            "id": filter_id,
            "name": name or match.get("name", ""),
            "sortOrder": match.get("sortOrder", 0),
            "sortType": match.get("sortType", "project"),
            "createdTime": match.get("createdTime", ""),
            "modifiedTime": match.get("modifiedTime", ""),
        }
        if match.get("etag"):
            update_data["etag"] = match["etag"]

        # Rebuild rule if any filter option provided
        if priority or date or tag:
            update_data["rule"] = _build_rule(
                priorities=list(priority) if priority else None,
                date=date,
                tags=list(tag) if tag else None,
            )
        else:
            update_data["rule"] = match.get("rule", "")

        if is_dry_run(ctx):
            output_dry_run("filter.edit", update_data, ctx)
            return

        client.v2.batch_filters(update=[update_data])
        output_message(f"Filter {filter_id} updated.", ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@filter_group.command("delete")
@click.argument("filter_id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def filter_delete(ctx: click.Context, filter_id: str, yes: bool) -> None:
    """Delete a saved filter."""
    if is_dry_run(ctx):
        output_dry_run("filter.delete", {"filter_id": filter_id}, ctx)
        return

    if not yes:
        click.confirm(f"Delete filter {filter_id}?", abort=True)

    client = get_client(ctx.obj.get("profile", "default"))
    try:
        client.v2.batch_filters(delete=[filter_id])
        output_message(f"Filter {filter_id} deleted.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
