"""Schema command — runtime introspection for AI agents.

``ticktick schema`` dumps every available command, its arguments, options,
types, and defaults as structured JSON.  This lets agents discover capabilities
at runtime without reading docs or ``--help`` text.
"""

from __future__ import annotations

import json
from typing import Any

import click


def _is_real_default(val: Any) -> bool:
    """Check if a default value is a real value (not a Click sentinel/missing marker)."""
    if val is None or val == ():
        return False
    # Click uses internal sentinel objects for missing defaults
    type_name = type(val).__name__
    if type_name in ("_default_text_stderr", "Sentinel", "LazyText"):
        return False
    try:
        json.dumps(val)
        return True
    except (TypeError, ValueError):
        return False


def _param_to_dict(param: click.Parameter) -> dict[str, Any]:
    """Serialize a Click parameter to a dict."""
    info: dict[str, Any] = {
        "name": param.name or "",
        "kind": "argument" if isinstance(param, click.Argument) else "option",
    }
    if isinstance(param, click.Option):
        info["flags"] = list(param.opts)
        if param.secondary_opts:
            info["flags"].extend(param.secondary_opts)
        info["is_flag"] = param.is_flag
    if param.type and param.type.name != "STRING":
        info["type"] = param.type.name
    if isinstance(param.type, click.Choice):
        info["choices"] = list(param.type.choices)
    if _is_real_default(param.default):
        info["default"] = param.default
    if param.required:
        info["required"] = True
    if param.multiple:
        info["multiple"] = True
    if isinstance(param, click.Option) and param.help:
        info["help"] = param.help
    return info


def _command_to_dict(cmd: click.BaseCommand, path: str = "") -> list[dict[str, Any]]:
    """Recursively serialize a command/group to dicts."""
    results: list[dict[str, Any]] = []
    full_path = f"{path} {cmd.name}" if path else (cmd.name or "")

    if isinstance(cmd, click.Group):
        for name in sorted(cmd.commands):
            sub = cmd.commands[name]
            results.extend(_command_to_dict(sub, full_path))
    else:
        entry: dict[str, Any] = {
            "command": full_path.strip(),
            "help": (cmd.help or "").split("\n")[0].strip(),
        }
        params = [_param_to_dict(p) for p in cmd.params if p.name not in ("help",)]
        if params:
            entry["params"] = params
        results.append(entry)

    return results


@click.command("schema")
@click.pass_context
def schema_command(ctx: click.Context) -> None:
    """Dump CLI schema as JSON — all commands, options, and types.

    Designed for AI agents to discover capabilities at runtime.
    """
    root: click.Group | None = ctx.parent.command if ctx.parent else None  # type: ignore[union-attr]
    if root is None or not isinstance(root, click.Group):
        click.echo(json.dumps({"ok": False, "error": "No root group found"}))
        return

    commands = _command_to_dict(root)

    # Also include global options from the root group
    global_opts = [
        _param_to_dict(p)
        for p in root.params
        if isinstance(p, click.Option) and p.name not in ("help",)
    ]

    result = {
        "ok": True,
        "data": {
            "name": "ticktick",
            "version": _get_version(),
            "global_options": global_opts,
            "commands": commands,
        },
    }
    click.echo(json.dumps(result, indent=2))


def _get_version() -> str:
    try:
        from ticktick_cli import __version__

        return __version__
    except ImportError:
        return "unknown"
