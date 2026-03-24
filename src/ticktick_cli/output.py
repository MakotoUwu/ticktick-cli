"""Output formatting — JSON (default), CSV, YAML, or rich tables (--human).

All command output goes through these functions to ensure consistency.
JSON format: {"ok": true, "data": ...} or {"ok": false, "error": "..."}
"""

from __future__ import annotations

import csv
import io
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


def _apply_fields_filter(data: Any, fields: list[str] | None) -> Any:
    """Filter dict/list-of-dicts to only include specified fields."""
    if not fields:
        return data
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in fields}
    if isinstance(data, list):
        return [{k: v for k, v in item.items() if k in fields} for item in data if isinstance(item, dict)]
    return data


def _get_fields(ctx: click.Context | None) -> list[str] | None:
    """Extract --fields list from context."""
    if ctx and ctx.obj:
        return ctx.obj.get("fields")
    return None


def _get_output_format(ctx: click.Context | None) -> str:
    """Extract --output format from context (json, csv, yaml)."""
    if ctx and ctx.obj:
        return ctx.obj.get("output_format", "json")
    return "json"


def _is_quiet(ctx: click.Context | None) -> bool:
    """Check if --quiet flag is active."""
    return bool(ctx and ctx.obj and ctx.obj.get("quiet"))


def _extract_id(item: dict[str, Any]) -> str:
    """Extract the ID (or first field) from an item dict."""
    if "id" in item:
        return str(item["id"])
    # Fall back to the first value in the dict
    if item:
        return str(next(iter(item.values())))
    return ""


def _to_csv(items: list[dict[str, Any]]) -> str:
    """Convert list of dicts to CSV string."""
    if not items:
        return ""
    buf = io.StringIO(newline="")
    cols = list(items[0].keys())
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in items:
        # Flatten lists/dicts for CSV
        row = {}
        for k, v in item.items():
            if isinstance(v, (list, dict)):
                row[k] = json.dumps(v, default=_serialize)
            else:
                row[k] = v
        writer.writerow(row)
    return buf.getvalue()


def _to_yaml(data: Any) -> str:
    """Convert data to YAML-like format (no external dependency)."""
    # Simple YAML serializer — handles the typical CLI output shapes
    lines: list[str] = []
    _yaml_dump(data, lines, indent=0)
    return "\n".join(lines) + "\n"


def _yaml_dump(obj: Any, lines: list[str], indent: int) -> None:
    """Recursive YAML dumper."""
    prefix = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{prefix}{k}:")
                _yaml_dump(v, lines, indent + 1)
            else:
                lines.append(f"{prefix}{k}: {_yaml_scalar(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    p = f"{prefix}- " if first else f"{prefix}  "
                    first = False
                    if isinstance(v, (dict, list)):
                        lines.append(f"{p}{k}:")
                        _yaml_dump(v, lines, indent + 2)
                    else:
                        lines.append(f"{p}{k}: {_yaml_scalar(v)}")
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(obj)}")


def _yaml_scalar(v: Any) -> str:
    """Format a scalar value for YAML."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    s = str(v)
    # Quote if contains special chars
    if any(c in s for c in (":", "#", "[", "]", "{", "}", ",", "&", "*", "?", "|", ">", "'", '"')):
        return f'"{s}"'
    return s


def output_success(data: Any, ctx: click.Context | None = None) -> None:
    """Output successful result."""
    if _is_quiet(ctx):
        # In quiet mode, print only IDs
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    print(_extract_id(item))
                else:
                    print(str(item))
        elif isinstance(data, dict):
            print(_extract_id(data))
        return

    human = ctx.obj.get("human", False) if ctx and ctx.obj else False
    fmt = _get_output_format(ctx)
    data = _apply_fields_filter(data, _get_fields(ctx))

    if human:
        _print_human(data)
    elif fmt == "csv":
        items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
        print(_to_csv(items), end="")
    elif fmt == "yaml":
        print(_to_yaml(data), end="")
    else:
        result = {"ok": True, "data": data}
        print(json.dumps(result, indent=2, default=_serialize))


def output_error(message: str, ctx: click.Context | None = None, *, exit_code: int = 1) -> None:
    """Output error result.

    Parameters
    ----------
    message:   Human-readable error description.
    ctx:       Click context (controls --human flag).
    exit_code: Semantic exit code included in the JSON envelope.
    """
    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        from rich.console import Console

        console = Console(stderr=True)
        console.print(f"[bold red]Error:[/bold red] {message}")
    else:
        result: dict[str, object] = {"ok": False, "error": message, "exit_code": exit_code}
        print(json.dumps(result, indent=2), file=sys.stderr)


def _get_pagination(ctx: click.Context | None) -> tuple[int, bool]:
    """Extract --offset and --all from context."""
    if ctx and ctx.obj:
        return ctx.obj.get("offset", 0), ctx.obj.get("all", False)
    return 0, False


def output_list(
    items: list[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
    ctx: click.Context | None = None,
    limit: int | None = None,
) -> None:
    """Output a list of items as JSON array or rich table."""
    total = len(items)
    offset, fetch_all = _get_pagination(ctx)

    if not fetch_all:
        end = offset + limit if limit is not None else None
        items = items[offset:end]

    if _is_quiet(ctx):
        for item in items:
            if isinstance(item, dict):
                print(_extract_id(item))
            else:
                print(str(item))
        return

    human = ctx.obj.get("human", False) if ctx and ctx.obj else False
    fmt = _get_output_format(ctx)
    fields = _get_fields(ctx)
    if fields:
        items = _apply_fields_filter(items, fields)
        columns = fields  # Override table columns to match

    if human:
        _print_table(items, columns=columns, title=title)
    elif fmt == "csv":
        print(_to_csv(items), end="")
    elif fmt == "yaml":
        print(_to_yaml(items), end="")
    else:
        if fetch_all:
            result: dict[str, Any] = {"ok": True, "data": items, "count": len(items)}
        else:
            count = len(items)
            has_more = offset + count < total
            result = {
                "ok": True,
                "data": items,
                "count": count,
                "total": total,
                "offset": offset,
                "has_more": has_more,
            }
        print(json.dumps(result, indent=2, default=_serialize))


def output_item(
    item: dict[str, Any],
    ctx: click.Context | None = None,
) -> None:
    """Output a single item."""
    if _is_quiet(ctx):
        print(_extract_id(item))
        return

    human = ctx.obj.get("human", False) if ctx and ctx.obj else False
    fmt = _get_output_format(ctx)
    item = _apply_fields_filter(item, _get_fields(ctx))

    if human:
        _print_detail(item)
    elif fmt == "csv":
        print(_to_csv([item]), end="")
    elif fmt == "yaml":
        print(_to_yaml(item), end="")
    else:
        result = {"ok": True, "data": item}
        print(json.dumps(result, indent=2, default=_serialize))


def output_existing_item(
    item: dict[str, Any],
    ctx: click.Context | None = None,
) -> None:
    """Output an existing item for --if-not-exists (already_exists=true)."""
    if _is_quiet(ctx):
        print(_extract_id(item))
        return

    human = ctx.obj.get("human", False) if ctx and ctx.obj else False
    fmt = _get_output_format(ctx)
    item = _apply_fields_filter(item, _get_fields(ctx))

    if human:
        from rich.console import Console

        Console().print("[yellow]Already exists:[/yellow]")
        _print_detail(item)
    elif fmt == "csv":
        print(_to_csv([item]), end="")
    elif fmt == "yaml":
        print(_to_yaml(item), end="")
    else:
        result = {"ok": True, "data": item, "already_exists": True}
        print(json.dumps(result, indent=2, default=_serialize))


def output_message(message: str, ctx: click.Context | None = None) -> None:
    """Output a simple message (e.g., 'Task completed')."""
    if _is_quiet(ctx):
        return  # Silent success in quiet mode

    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        from rich.console import Console

        Console().print(f"[green]{message}[/green]")
    else:
        result = {"ok": True, "message": message}
        print(json.dumps(result, indent=2))


def is_dry_run(ctx: click.Context | None) -> bool:
    """Check if --dry-run flag is active."""
    return bool(ctx and ctx.obj and ctx.obj.get("dry_run"))


def output_dry_run(action: str, details: dict[str, Any] | None = None, ctx: click.Context | None = None) -> None:
    """Output what would be done in dry-run mode."""
    human = ctx.obj.get("human", False) if ctx and ctx.obj else False

    if human:
        from rich.console import Console

        console = Console()
        console.print(f"[yellow][DRY RUN][/yellow] {action}")
        if details:
            for k, v in details.items():
                console.print(f"  {k}: {v}")
    else:
        result: dict[str, Any] = {"ok": True, "dry_run": True, "action": action}
        if details:
            result["details"] = details
        print(json.dumps(result, indent=2, default=_serialize))


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
