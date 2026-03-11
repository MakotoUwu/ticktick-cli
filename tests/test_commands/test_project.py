"""Test project and folder commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestProjectList:
    def test_list_projects(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.project_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["project", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2


class TestProjectCreate:
    def test_create_project_v2(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.batch_projects.return_value = {}
        with patch("ticktick_cli.commands.project_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["project", "create", "My Project"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "My Project" in data["message"]

    def test_create_project_with_options(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.batch_projects.return_value = {}
        with patch("ticktick_cli.commands.project_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, [
                "project", "create", "Kanban Board",
                "--view", "kanban",
                "--color", "#FF0000",
            ])
        assert result.exit_code == 0


class TestProjectDelete:
    def test_delete_with_yes_flag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.batch_projects.return_value = {}
        with patch("ticktick_cli.commands.project_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["project", "delete", "proj1", "--yes"])
        assert result.exit_code == 0


class TestFolderList:
    def test_list_folders(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["folder", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
