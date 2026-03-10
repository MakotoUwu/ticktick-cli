"""Test focus and user commands."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestFocusHeatmap:
    def test_focus_heatmap(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.focus_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["focus", "heatmap", "--days", "7"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        # Real API returns [{duration, day, timezone}, ...] — filtered to non-zero
        assert len(data["data"]) == 2
        assert data["data"][0]["date"] == "20260301"
        assert data["data"][0]["minutes"] == 60


class TestFocusByTag:
    def test_focus_by_tag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.focus_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["focus", "by-tag", "--days", "30"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        # Real API returns {projectDurations, tagDurations, taskDurations}
        types = {row["type"] for row in data["data"]}
        assert "project" in types
        assert "tag" in types


class TestUserProfile:
    def test_user_profile(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.user_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "profile"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["username"] == "testuser"
        assert data["data"]["email"] == "test@example.com"


class TestUserStatus:
    def test_user_status(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.user_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "proLevel" in data["data"]


class TestUserStats:
    def test_user_stats(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.user_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "stats"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True


class TestUserPreferences:
    def test_user_preferences(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.user_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "preferences"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "timeZone" in data["data"]
