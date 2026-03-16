"""Tests for user commands — profile, status, stats, preferences."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.commands.user_cmd import user_group

# ── Helpers ───────────────────────────────────────────────────


def _make_ctx(**overrides: Any) -> dict[str, Any]:
    defaults = {
        "human": False,
        "verbose": False,
        "profile": "default",
        "fields": None,
        "dry_run": False,
        "output_format": "json",
    }
    defaults.update(overrides)
    return defaults


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.v2 = MagicMock()
    client.has_v2 = True
    client.has_v1 = False
    return client


# ── Profile ───────────────────────────────────────────────────


class TestUserProfile:
    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_profile_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_profile.return_value = {
            "username": "alice",
            "name": "Alice A.",
            "email": "alice@example.com",
            "timeZone": "America/New_York",
            "inboxId": "inbox_abc",
            "createdTime": "2024-01-01T00:00:00.000+0000",
        }

        runner = CliRunner()
        result = runner.invoke(user_group, ["profile"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["username"] == "alice"
        assert data["data"]["name"] == "Alice A."
        assert data["data"]["email"] == "alice@example.com"
        assert data["data"]["timeZone"] == "America/New_York"
        assert data["data"]["inboxId"] == "inbox_abc"
        assert data["data"]["createdTime"] == "2024-01-01T00:00:00.000+0000"

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_profile_missing_fields(self, mock_get: MagicMock) -> None:
        """Profile should handle missing optional fields gracefully."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_profile.return_value = {"username": "bob"}

        runner = CliRunner()
        result = runner.invoke(user_group, ["profile"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["username"] == "bob"
        assert data["data"]["name"] == ""
        # email falls back to username when missing
        assert data["data"]["email"] == "bob"

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_profile_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_profile.side_effect = Exception("Unauthorized")

        runner = CliRunner()
        result = runner.invoke(user_group, ["profile"], obj=_make_ctx())
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_profile_json_format(self, mock_get: MagicMock) -> None:
        """Verify output conforms to the standard JSON envelope."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_profile.return_value = {
            "username": "u",
            "name": "N",
        }

        runner = CliRunner()
        result = runner.invoke(user_group, ["profile"], obj=_make_ctx())
        data = json.loads(result.output)
        assert "ok" in data
        assert "data" in data
        assert isinstance(data["data"], dict)


# ── Status ────────────────────────────────────────────────────


class TestUserStatus:
    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_status_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_status.return_value = {
            "proLevel": 2,
            "proExpireDate": "2027-01-01",
            "subscribeType": "yearly",
            "freeTrial": False,
        }

        runner = CliRunner()
        result = runner.invoke(user_group, ["status"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["proLevel"] == 2
        assert data["data"]["subscribeType"] == "yearly"
        assert data["data"]["freeTrial"] is False

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_status_free_user(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_status.return_value = {
            "proLevel": 0,
            "proExpireDate": "",
            "subscribeType": "",
            "freeTrial": True,
        }

        runner = CliRunner()
        result = runner.invoke(user_group, ["status"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["proLevel"] == 0
        assert data["data"]["freeTrial"] is True

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_status_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_status.side_effect = Exception("Network error")

        runner = CliRunner()
        result = runner.invoke(user_group, ["status"], obj=_make_ctx())
        assert result.exit_code == 1


# ── Stats ─────────────────────────────────────────────────────


class TestUserStats:
    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_stats_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_statistics.return_value = {
            "completedCount": 250,
            "currentStreak": 10,
            "maxStreak": 42,
        }

        runner = CliRunner()
        result = runner.invoke(user_group, ["stats"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["completedCount"] == 250
        assert data["data"]["currentStreak"] == 10
        assert data["data"]["maxStreak"] == 42

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_stats_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_statistics.side_effect = Exception("Server error")

        runner = CliRunner()
        result = runner.invoke(user_group, ["stats"], obj=_make_ctx())
        assert result.exit_code == 1


# ── Preferences ───────────────────────────────────────────────


class TestUserPreferences:
    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_preferences_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_preferences.return_value = {
            "timeZone": "Europe/Berlin",
            "startOfWeek": 1,
            "dateFormat": "YYYY-MM-DD",
            "timeFormat": "24h",
        }

        runner = CliRunner()
        result = runner.invoke(user_group, ["preferences"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["timeZone"] == "Europe/Berlin"
        assert data["data"]["startOfWeek"] == 1

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_preferences_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_preferences.side_effect = Exception("Token expired")

        runner = CliRunner()
        result = runner.invoke(user_group, ["preferences"], obj=_make_ctx())
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.user_cmd.get_client")
    def test_preferences_json_envelope(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_user_preferences.return_value = {"timeZone": "UTC"}

        runner = CliRunner()
        result = runner.invoke(user_group, ["preferences"], obj=_make_ctx())
        data = json.loads(result.output)
        assert data["ok"] is True
        assert isinstance(data["data"], dict)
