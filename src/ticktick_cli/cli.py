"""Root CLI group — wires all command groups and global options."""

from __future__ import annotations

import json
import sys

import click

from ticktick_cli import __version__
from ticktick_cli.auth import get_client

# Import all command groups
from ticktick_cli.commands.auth_cmd import auth_group
from ticktick_cli.commands.config_cmd import config_group
from ticktick_cli.commands.focus_cmd import focus_group
from ticktick_cli.commands.folder_cmd import folder_group
from ticktick_cli.commands.habit_cmd import habit_group
from ticktick_cli.commands.kanban_cmd import column_group
from ticktick_cli.commands.project_cmd import project_group
from ticktick_cli.commands.subtask_cmd import subtask_group
from ticktick_cli.commands.tag_cmd import tag_group
from ticktick_cli.commands.task_cmd import task_group
from ticktick_cli.commands.user_cmd import user_group
from ticktick_cli.output import output_error, output_item


@click.group()
@click.option("--human", is_flag=True, help="Human-readable rich table output instead of JSON.")
@click.option("--verbose", is_flag=True, help="Enable verbose/debug output.")
@click.option("--profile", default="default", help="Auth profile to use.")
@click.version_option(version=__version__, prog_name="ticktick-cli")
@click.pass_context
def cli(ctx: click.Context, human: bool, verbose: bool, profile: str) -> None:
    """TickTick CLI — agent-native command-line interface for TickTick.

    JSON output by default. Use --human for rich tables.
    """
    ctx.ensure_object(dict)
    ctx.obj["human"] = human
    ctx.obj["verbose"] = verbose
    ctx.obj["profile"] = profile


# ── Register all command groups ──────────────────────────

cli.add_command(auth_group, "auth")
cli.add_command(task_group, "task")
cli.add_command(project_group, "project")
cli.add_command(folder_group, "folder")
cli.add_command(tag_group, "tag")
cli.add_command(column_group, "column")
cli.add_command(subtask_group, "subtask")
cli.add_command(habit_group, "habit")
cli.add_command(focus_group, "focus")
cli.add_command(user_group, "user")
cli.add_command(config_group, "config")


# ── Standalone commands ──────────────────────────────────

@cli.command("sync")
@click.pass_context
def sync_command(ctx: click.Context) -> None:
    """Full account state sync (V2). Dumps the complete account state."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        state = client.v2.sync()
        # Summarize rather than dumping everything
        summary = {
            "projects": len(state.get("projectProfiles", [])),
            "tasks": len(state.get("syncTaskBean", {}).get("update", [])),
            "tags": len(state.get("tags", [])),
            "projectGroups": len(state.get("projectGroups", [])),
            "filters": len(state.get("filters", [])),
        }
        if ctx.obj.get("verbose"):
            output_item(state, ctx)
        else:
            output_item(summary, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@cli.command("version")
@click.pass_context
def version_command(ctx: click.Context) -> None:
    """Show version information."""
    human = ctx.obj.get("human", False)
    if human:
        click.echo(f"ticktick-cli v{__version__}")
    else:
        click.echo(json.dumps({"ok": True, "data": {"version": __version__}}))


def main() -> None:
    """Entry point."""
    try:
        cli(standalone_mode=False)
    except SystemExit as e:
        sys.exit(e.code)
    except click.exceptions.Abort:
        sys.exit(130)
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
