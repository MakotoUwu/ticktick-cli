"""Test the root CLI group and global options."""

from __future__ import annotations

import json
from unittest.mock import patch

from click.testing import CliRunner

from ticktick_cli.cli import cli


def test_version_flag(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_version_command(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["data"]["version"] == "0.1.0"


def test_version_human(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--human", "version"])
    assert result.exit_code == 0
    assert "ticktick-cli v0.1.0" in result.output


def test_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "TickTick CLI" in result.output
    assert "task" in result.output
    assert "habit" in result.output
    assert "project" in result.output
    assert "tag" in result.output
    assert "focus" in result.output
    assert "user" in result.output
    assert "config" in result.output
    assert "sync" in result.output


def test_all_command_groups_registered(runner: CliRunner) -> None:
    """All 11 groups + 2 standalone commands are registered."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    expected_groups = [
        "auth", "task", "project", "folder", "tag",
        "column", "subtask", "habit", "focus", "user",
        "config", "sync", "version",
    ]
    for name in expected_groups:
        assert name in result.output, f"'{name}' not found in CLI help"


def test_task_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["task", "--help"])
    assert result.exit_code == 0
    expected = [
        "add", "list", "show", "edit", "done", "abandon",
        "delete", "move", "search", "today", "overdue",
        "completed", "trash", "pin", "unpin", "batch-add",
    ]
    for cmd in expected:
        assert cmd in result.output, f"task subcommand '{cmd}' not found"


def test_habit_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["habit", "--help"])
    assert result.exit_code == 0
    expected = ["list", "show", "create", "edit", "delete", "checkin", "history", "archive", "unarchive"]
    for cmd in expected:
        assert cmd in result.output, f"habit subcommand '{cmd}' not found"


def test_project_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["project", "--help"])
    assert result.exit_code == 0
    expected = ["list", "create", "show", "edit", "delete"]
    for cmd in expected:
        assert cmd in result.output


def test_tag_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["tag", "--help"])
    assert result.exit_code == 0
    expected = ["list", "create", "edit", "rename", "merge", "delete"]
    for cmd in expected:
        assert cmd in result.output


def test_focus_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["focus", "--help"])
    assert result.exit_code == 0
    assert "heatmap" in result.output
    assert "by-tag" in result.output


def test_user_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["user", "--help"])
    assert result.exit_code == 0
    expected = ["profile", "status", "stats", "preferences"]
    for cmd in expected:
        assert cmd in result.output


def test_config_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["config", "--help"])
    assert result.exit_code == 0
    expected = ["set", "get", "list", "path"]
    for cmd in expected:
        assert cmd in result.output


def test_column_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["column", "--help"])
    assert result.exit_code == 0
    expected = ["list", "create", "edit", "delete"]
    for cmd in expected:
        assert cmd in result.output


def test_subtask_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["subtask", "--help"])
    assert result.exit_code == 0
    expected = ["set", "unset", "list"]
    for cmd in expected:
        assert cmd in result.output


def test_folder_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["folder", "--help"])
    assert result.exit_code == 0
    expected = ["list", "create", "rename", "delete"]
    for cmd in expected:
        assert cmd in result.output


def test_auth_subcommands(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["auth", "--help"])
    assert result.exit_code == 0
    expected = ["login", "login-v2", "logout", "status"]
    for cmd in expected:
        assert cmd in result.output


def test_global_offset_and_all_flags(runner: CliRunner) -> None:
    """--offset and --all appear in help."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "--offset" in result.output
    assert "--all" in result.output


def test_env_var_output(runner: CliRunner) -> None:
    """TICKTICK_OUTPUT sets default output format."""
    result = runner.invoke(cli, ["version"], env={"TICKTICK_OUTPUT": "json"})
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True


def test_env_var_output_respected_in_tty(runner: CliRunner, mock_client) -> None:
    """TICKTICK_OUTPUT should disable auto-human output in TTY sessions."""
    with (
        patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client),
        patch("sys.stdout.isatty", return_value=True),
    ):
        result = runner.invoke(cli, ["task", "list"], env={"TICKTICK_OUTPUT": "yaml"})
    assert result.exit_code == 0
    assert result.output.lstrip().startswith("- id:")


def test_env_var_profile(runner: CliRunner) -> None:
    """TICKTICK_PROFILE is accepted as env var."""
    result = runner.invoke(cli, ["--help"], env={"TICKTICK_PROFILE": "work"})
    assert result.exit_code == 0
