"""Config commands — get, set, list, path."""

from __future__ import annotations

import json

import click

from ticktick_cli.config import get_config_dir, load_config, save_config
from ticktick_cli.output import output_error, output_item, output_message


@click.group("config")
def config_group() -> None:
    """Manage CLI configuration."""


@config_group.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    """Set a config key to a value."""
    profile = ctx.obj.get("profile", "default")
    try:
        cfg = load_config(profile)
        # Try to parse JSON values (booleans, numbers)
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            parsed = value
        cfg[key] = parsed
        save_config(cfg, profile)
        output_message(f"Config '{key}' set to {json.dumps(parsed)}.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@config_group.command("get")
@click.argument("key")
@click.pass_context
def config_get(ctx: click.Context, key: str) -> None:
    """Get a config value by key."""
    profile = ctx.obj.get("profile", "default")
    try:
        cfg = load_config(profile)
        if key not in cfg:
            output_error(f"Key '{key}' not found in config.", ctx)
            raise SystemExit(1) from None
        output_item({"key": key, "value": cfg[key]}, ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@config_group.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    """List all config settings."""
    profile = ctx.obj.get("profile", "default")
    try:
        cfg = load_config(profile)
        output_item(cfg if cfg else {"_note": "No configuration set."}, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@config_group.command("path")
@click.pass_context
def config_path(ctx: click.Context) -> None:
    """Show the config directory path."""
    profile = ctx.obj.get("profile", "default")
    try:
        path = get_config_dir(profile)
        output_item({"config_dir": str(path)}, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
