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
        mock_client.list_projects.return_value = [
            {"id": "proj1", "name": "Inbox"},
            {"id": "proj_new", "name": "My Project", "kind": "TASK", "viewMode": "list", "closed": False},
        ]
        with patch("ticktick_cli.commands.project_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["project", "create", "My Project"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "My Project" in data["message"]
        assert data["data"]["id"] == "proj_new"
        assert data["data"]["name"] == "My Project"

    def test_create_project_v2_lookup_failure_still_reports_created(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.v2.batch_projects.return_value = {}
        mock_client.list_projects.side_effect = Exception("temporary read failure")
        with patch("ticktick_cli.commands.project_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["project", "create", "My Project"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["name"] == "My Project"
        assert "id" not in data["data"]

    def test_create_project_with_options(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.batch_projects.return_value = {}
        mock_client.list_projects.return_value = [
            {"id": "proj_new", "name": "Kanban Board", "kind": "TASK", "viewMode": "kanban", "color": "#FF0000", "closed": False},
        ]
        with patch("ticktick_cli.commands.project_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, [
                "project", "create", "Kanban Board",
                "--view", "kanban",
                "--color", "#FF0000",
            ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["viewMode"] == "kanban"
        assert data["data"]["color"] == "#FF0000"

    def test_create_project_dry_run_if_not_exists_skips_client(self, runner: CliRunner) -> None:
        with patch(
            "ticktick_cli.commands.project_cmd.get_client",
            side_effect=AssertionError("get_client should not be called"),
        ):
            result = runner.invoke(cli, ["--dry-run", "project", "create", "My Project", "--if-not-exists"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


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
