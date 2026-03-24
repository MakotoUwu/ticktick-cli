"""Root CLI group — wires all command groups and global options."""

from __future__ import annotations

import json
import sys

import click

from ticktick_cli import __version__
from ticktick_cli.auth import get_client

# Import all command groups
from ticktick_cli.commands.auth_cmd import auth_group
from ticktick_cli.commands.calendar_cmd import calendar_group
from ticktick_cli.commands.config_cmd import config_group
from ticktick_cli.commands.filter_cmd import filter_group
from ticktick_cli.commands.focus_cmd import focus_group
from ticktick_cli.commands.folder_cmd import folder_group
from ticktick_cli.commands.habit_cmd import habit_group
from ticktick_cli.commands.kanban_cmd import column_group
from ticktick_cli.commands.project_cmd import project_group
from ticktick_cli.commands.schema_cmd import schema_command
from ticktick_cli.commands.subtask_cmd import subtask_group
from ticktick_cli.commands.tag_cmd import tag_group
from ticktick_cli.commands.task_cmd import task_group
from ticktick_cli.commands.template_cmd import template_group
from ticktick_cli.commands.user_cmd import user_group
from ticktick_cli.output import output_error, output_item


@click.group()
@click.option("--human", is_flag=True, help="Human-readable rich table output instead of JSON.")
@click.option("--verbose", is_flag=True, help="Enable verbose/debug output.")
@click.option("--profile", default="default", envvar="TICKTICK_PROFILE", help="Auth profile to use.")
@click.option("--fields", default=None, envvar="TICKTICK_FIELDS", help="Comma-separated list of fields to include in output (e.g., id,title,priority).")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing.")
@click.option("--output", "-o", "output_format", type=click.Choice(["json", "csv", "yaml"]), default="json", envvar="TICKTICK_OUTPUT", help="Output format (default: json).")
@click.option("--quiet", "-q", is_flag=True, envvar="TICKTICK_QUIET", help="Quiet mode — output only bare IDs, one per line. Useful for piping.")
@click.option("--offset", type=int, default=0, help="Skip first N items in list output (pagination).")
@click.option("--all", "fetch_all", is_flag=True, help="Return all items, ignoring --limit.")
@click.version_option(version=__version__, prog_name="ticktick-cli")
@click.pass_context
def cli(ctx: click.Context, human: bool, verbose: bool, profile: str, fields: str | None, dry_run: bool, output_format: str, quiet: bool, offset: int, fetch_all: bool) -> None:
    """TickTick CLI — agent-native command-line interface for TickTick.

    Auto-detects TTY: rich tables in terminal, JSON when piped.
    Use --human to force tables, --output json/csv/yaml to force a format.
    """
    ctx.ensure_object(dict)

    # TTY auto-detection: use Rich table output when stdout is a terminal,
    # unless the user explicitly requested a specific output format.
    output_source = ctx.get_parameter_source("output_format")
    human_source = ctx.get_parameter_source("human")
    explicit_output = output_source == click.core.ParameterSource.COMMANDLINE
    explicit_human = human_source == click.core.ParameterSource.COMMANDLINE

    if explicit_human:
        # --human flag explicitly passed — respect it
        resolved_human = human
    elif explicit_output:
        # --output explicitly set — respect it, no auto-human
        resolved_human = False
    elif sys.stdout.isatty():
        # TTY detected and no explicit flags — auto-enable human mode
        resolved_human = True
    else:
        # Piped / non-TTY — keep JSON default
        resolved_human = False

    ctx.obj["human"] = resolved_human
    ctx.obj["verbose"] = verbose
    ctx.obj["profile"] = profile
    ctx.obj["fields"] = [f.strip() for f in fields.split(",")] if fields else None
    ctx.obj["dry_run"] = dry_run
    ctx.obj["output_format"] = output_format
    ctx.obj["quiet"] = quiet
    ctx.obj["offset"] = offset
    ctx.obj["all"] = fetch_all


# ── Register all command groups ──────────────────────────

cli.add_command(auth_group, "auth")
cli.add_command(calendar_group, "calendar")
cli.add_command(task_group, "task")
cli.add_command(project_group, "project")
cli.add_command(folder_group, "folder")
cli.add_command(tag_group, "tag")
cli.add_command(column_group, "column")
cli.add_command(subtask_group, "subtask")
cli.add_command(habit_group, "habit")
cli.add_command(focus_group, "focus")
cli.add_command(filter_group, "filter")
cli.add_command(template_group, "template")
cli.add_command(user_group, "user")
cli.add_command(config_group, "config")
cli.add_command(schema_command, "schema")


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


@cli.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
@click.pass_context
def completion_command(ctx: click.Context, shell: str) -> None:
    """Generate shell completion script.

    Usage:

      ticktick completion bash >> ~/.bashrc

      ticktick completion zsh >> ~/.zshrc

      ticktick completion fish > ~/.config/fish/completions/ticktick.fish
    """
    import os

    env_var = "_TICKTICK_COMPLETE"
    shell_map = {"bash": "bash_source", "zsh": "zsh_source", "fish": "fish_source"}
    os.environ[env_var] = shell_map[shell]
    try:
        cli(standalone_mode=False)
    except SystemExit:
        pass
    finally:
        os.environ.pop(env_var, None)


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
    from ticktick_cli.exceptions import TickTickCLIError

    try:
        cli(standalone_mode=False)
    except SystemExit as e:
        sys.exit(e.code)
    except click.exceptions.Abort:
        sys.exit(130)
    except TickTickCLIError as e:
        payload: dict[str, object] = {"ok": False, "error": str(e), "exit_code": e.exit_code}
        click.echo(json.dumps(payload), err=True)
        sys.exit(e.exit_code)
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e), "exit_code": 1}), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
