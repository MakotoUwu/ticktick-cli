"""Output formatting — JSON (default, agent-friendly) or rich tables (--human).

All command output goes through these functions to ensure consistency.
JSON format: {"ok": true, "data": ...} or {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from typing import Any

import click


def _serialize(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):  # Pydantic v1
        return obj.dict()
    return str(obj)


def output_success(data: Any, ctx: click.Context | None = None) -> None:
    """Output successful result."""
    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        _print_human(data)
    else:
        result = {"ok": True, "data": data}
        print(json.dumps(result, indent=2, default=_serialize))


def output_error(message: str, ctx: click.Context | None = None) -> None:
    """Output error result."""
    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        from rich.console import Console

        console = Console(stderr=True)
        console.print(f"[bold red]Error:[/bold red] {message}")
    else:
        result = {"ok": False, "error": message}
        print(json.dumps(result, indent=2), file=sys.stderr)


def output_list(
    items: list[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
    ctx: click.Context | None = None,
) -> None:
    """Output a list of items as JSON array or rich table."""
    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        _print_table(items, columns=columns, title=title)
    else:
        result = {"ok": True, "data": items, "count": len(items)}
        print(json.dumps(result, indent=2, default=_serialize))


def output_item(
    item: dict[str, Any],
    ctx: click.Context | None = None,
) -> None:
    """Output a single item."""
    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        _print_detail(item)
    else:
        result = {"ok": True, "data": item}
        print(json.dumps(result, indent=2, default=_serialize))


def output_message(message: str, ctx: click.Context | None = None) -> None:
    """Output a simple message (e.g., 'Task completed')."""
    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        from rich.console import Console

        Console().print(f"[green]{message}[/green]")
    else:
        result = {"ok": True, "message": message}
        print(json.dumps(result, indent=2))


# ---- Rich table helpers ----


def _print_table(
    items: list[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Print items as a rich table."""
    from rich.console import Console
    from rich.table import Table

    if not items:
        Console().print("[dim]No results.[/dim]")
        return

    if columns is None:
        columns = list(items[0].keys())

    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col, overflow="fold")

    for item in items:
        row = [str(item.get(col, "")) for col in columns]
        table.add_row(*row)

    Console().print(table)


def _print_detail(item: dict[str, Any]) -> None:
    """Print a single item as key-value pairs."""
    from rich.console import Console
    from rich.table import Table

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")

    for key, value in item.items():
        table.add_row(key, str(value))

    Console().print(table)


def _print_human(data: Any) -> None:
    """Auto-detect data type and print human-readable."""
    if isinstance(data, list):
        _print_table(data)
    elif isinstance(data, dict):
        _print_detail(data)
    else:
        from rich.console import Console

        Console().print(str(data))
