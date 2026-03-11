"""Test kanban column and subtask commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestColumnList:
    def test_list_columns(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.kanban_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["column", "list", "proj1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["data"][0]["name"] == "To Do"


class TestColumnCreate:
    def test_create_column(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.kanban_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["column", "create", "proj1", "In Progress"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "In Progress" in data["message"]


class TestColumnDelete:
    def test_delete_column_with_yes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.kanban_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, [
                "column", "delete", "col1",
                "--project", "proj1", "--yes",
            ])
        assert result.exit_code == 0


class TestSubtaskSet:
    def test_set_subtask(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.set_task_parent.return_value = {}
        with patch("ticktick_cli.commands.subtask_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["subtask", "set", "task1", "--parent", "parent1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "subtask" in data["message"]


class TestSubtaskUnset:
    def test_unset_subtask(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.unset_task_parent.return_value = {}
        with patch("ticktick_cli.commands.subtask_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["subtask", "unset", "task1", "--parent", "parent1"])
        assert result.exit_code == 0


class TestSubtaskList:
    def test_list_subtasks(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.subtask_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["subtask", "list", "parent1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
