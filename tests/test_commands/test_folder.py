"""Test folder commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestFolderList:
    def test_folder_list(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_all_project_groups.return_value = [
            {"id": "grp1", "name": "Work"},
            {"id": "grp2", "name": "Personal"},
        ]
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["folder", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["data"][0]["name"] == "Work"
        assert data["data"][1]["name"] == "Personal"

    def test_folder_list_empty(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_all_project_groups.return_value = []
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["folder", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0


class TestFolderCreate:
    def test_folder_create(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["folder", "create", "New Folder"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "created" in data["message"]
        mock_client.v2.batch_project_groups.assert_called_once()
        call_args = mock_client.v2.batch_project_groups.call_args
        assert call_args.kwargs["add"][0]["name"] == "New Folder"

    def test_folder_create_dry_run(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["--dry-run", "folder", "create", "Test Folder"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "folder.create"
        mock_client.v2.batch_project_groups.assert_not_called()


class TestFolderRename:
    def test_folder_rename(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["folder", "rename", "grp1", "Renamed Folder"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "renamed" in data["message"]
        call_args = mock_client.v2.batch_project_groups.call_args
        assert call_args.kwargs["update"][0]["name"] == "Renamed Folder"


class TestFolderDelete:
    def test_folder_delete_with_yes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["folder", "delete", "grp1", "--yes"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "deleted" in data["message"]
        mock_client.v2.batch_project_groups.assert_called_once()

    def test_folder_delete_aborts_without_yes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["folder", "delete", "grp1"], input="n\n")
        assert result.exit_code != 0
        mock_client.v2.batch_project_groups.assert_not_called()

    def test_folder_delete_dry_run(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.folder_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["--dry-run", "folder", "delete", "grp1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        mock_client.v2.batch_project_groups.assert_not_called()
