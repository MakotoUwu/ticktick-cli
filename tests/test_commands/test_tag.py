"""Test tag commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestTagList:
    def test_list_tags(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.tag_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["tag", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2


class TestTagCreate:
    def test_create_tag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.tag_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["tag", "create", "new-tag"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "new-tag" in data["message"]

    def test_create_tag_dry_run_if_not_exists_skips_client(self, runner: CliRunner) -> None:
        with patch(
            "ticktick_cli.commands.tag_cmd.get_client",
            side_effect=AssertionError("get_client should not be called"),
        ):
            result = runner.invoke(cli, ["--dry-run", "tag", "create", "new-tag", "--if-not-exists"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestTagRename:
    def test_rename_tag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.tag_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["tag", "rename", "old-name", "new-name"])
        assert result.exit_code == 0
        mock_client.v2.rename_tag.assert_called_once_with("old-name", "new-name")


class TestTagMerge:
    def test_merge_tags(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.tag_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["tag", "merge", "source", "target"])
        assert result.exit_code == 0
        mock_client.v2.merge_tags.assert_called_once_with("source", "target")


class TestTagDelete:
    def test_delete_tag_with_yes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.tag_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["tag", "delete", "old-tag", "--yes"])
        assert result.exit_code == 0
        mock_client.v2.delete_tag.assert_called_once_with("old-tag")
