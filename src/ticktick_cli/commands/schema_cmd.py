"""Schema command — runtime introspection for AI agents.

``ticktick schema`` dumps every available command, its arguments, options,
types, and defaults as structured JSON.  This lets agents discover capabilities
at runtime without reading docs or ``--help`` text.
"""

from __future__ import annotations

import json
from typing import Any

import click

_NO_AUTH_COMMANDS = {
    "auth login",
    "auth login-v2",
    "auth logout",
    "auth status",
    "completion",
    "config get",
    "config list",
    "config path",
    "config set",
    "schema",
    "version",
}

_EITHER_API_COMMANDS = {
    "project create",
    "project delete",
    "project list",
    "project show",
    "project edit",
    "task add",
    "task delete",
    "task done",
    "task edit",
    "task list",
    "task show",
}

_MUTATING_COMMANDS = {
    "auth login",
    "auth login-v2",
    "auth logout",
    "column create",
    "column delete",
    "column edit",
    "config set",
    "filter create",
    "filter delete",
    "filter edit",
    "focus delete",
    "focus link",
    "focus log",
    "focus start",
    "focus stop",
    "folder create",
    "folder delete",
    "folder rename",
    "habit archive",
    "habit checkin",
    "habit create",
    "habit delete",
    "habit edit",
    "habit unarchive",
    "project create",
    "project delete",
    "project edit",
    "subtask set",
    "subtask unset",
    "tag create",
    "tag delete",
    "tag edit",
    "tag merge",
    "tag rename",
    "task abandon",
    "task add",
    "task attachment add",
    "task batch-add",
    "task comment add",
    "task comment delete",
    "task convert",
    "task delete",
    "task done",
    "task duplicate",
    "task edit",
    "task move",
    "task pin",
    "task skip",
    "task unpin",
    "template create",
    "template delete",
}

_DESTRUCTIVE_COMMANDS = {
    "auth logout",
    "column delete",
    "filter delete",
    "focus delete",
    "folder delete",
    "habit delete",
    "project delete",
    "tag delete",
    "tag merge",
    "task comment delete",
    "task delete",
    "template delete",
}

_DRY_RUN_COMMANDS = {
    "filter create",
    "filter delete",
    "filter edit",
    "focus delete",
    "focus link",
    "focus log",
    "focus start",
    "focus stop",
    "folder create",
    "folder delete",
    "habit create",
    "habit delete",
    "project create",
    "project delete",
    "tag create",
    "tag delete",
    "task abandon",
    "task add",
    "task attachment add",
    "task batch-add",
    "task comment add",
    "task comment delete",
    "task convert",
    "task delete",
    "task done",
    "task duplicate",
    "task edit",
    "task move",
    "task pin",
    "task skip",
    "task unpin",
    "template create",
    "template delete",
}


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


def _normalize_command(command: str) -> str:
    """Drop the Click root name from schema command paths."""
    return command.removeprefix("cli ").strip()


def _command_metadata(command: str, params: list[dict[str, Any]]) -> dict[str, Any]:
    """Return agent-facing behavior metadata for a leaf command."""
    normalized = _normalize_command(command)
    mutates = normalized in _MUTATING_COMMANDS
    destructive = normalized in _DESTRUCTIVE_COMMANDS
    supports_dry_run = normalized in _DRY_RUN_COMMANDS
    has_yes_flag = any(p.get("name") == "yes" for p in params)

    if normalized in _NO_AUTH_COMMANDS:
        auth_api = "none"
    elif normalized in _EITHER_API_COMMANDS:
        auth_api = "either"
    elif normalized.startswith(("auth ", "config ", "completion", "schema", "version")):
        auth_api = "none"
    else:
        auth_api = "v2"

    metadata: dict[str, Any] = {
        "agent": {
            "mutates": mutates,
            "destructive": destructive,
            "supports_dry_run": supports_dry_run,
            "requires_confirmation": destructive and has_yes_flag,
            "auth_api": auth_api,
            "requires_auth": auth_api != "none",
        }
    }
    if supports_dry_run:
        metadata["agent"]["dry_run_semantics"] = "preview without writes"
    return metadata


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
        entry.update(_command_metadata(entry["command"], params))
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
