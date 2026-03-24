"""Test habit commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestHabitList:
    def test_list_habits(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 1
        assert data["data"][0]["name"] == "Exercise"
        assert data["data"][0]["status"] == "active"


class TestHabitShow:
    def test_show_habit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "show", "habit1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["name"] == "Exercise"

    def test_show_habit_not_found(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "show", "nonexistent"])
        assert result.exit_code != 0


class TestHabitCreate:
    def test_create_boolean_habit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "create", "Meditate"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Meditate" in data["message"]
        mock_client.v2.batch_habits.assert_called_once()

    def test_create_numeric_habit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, [
                "habit", "create", "Run",
                "--type", "numeric",
                "--goal", "5.0",
                "--unit", "km",
            ])
        assert result.exit_code == 0
        call_args = mock_client.v2.batch_habits.call_args
        habit_data = call_args[1]["add"][0]
        assert habit_data["name"] == "Run"
        assert habit_data["type"] == "Real"
        assert habit_data["goal"] == 5.0
        assert habit_data["unit"] == "km"

    def test_create_habit_dry_run_if_not_exists_skips_client(self, runner: CliRunner) -> None:
        with patch(
            "ticktick_cli.commands.habit_cmd.get_client",
            side_effect=AssertionError("get_client should not be called"),
        ):
            result = runner.invoke(cli, ["--dry-run", "habit", "create", "Meditate", "--if-not-exists"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestHabitCheckin:
    def test_checkin_habit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "checkin", "habit1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Checked in" in data["message"]
        mock_client.v2.batch_habit_checkins.assert_called_once()

    def test_checkin_with_date_and_value(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, [
                "habit", "checkin", "habit1",
                "--date", "20260309",
                "--value", "3.5",
            ])
        assert result.exit_code == 0
        call_args = mock_client.v2.batch_habit_checkins.call_args
        checkin_data = call_args[1]["add"][0]
        assert checkin_data["habitId"] == "habit1"
        assert checkin_data["checkinStamp"] == 20260309
        assert checkin_data["value"] == 3.5


class TestHabitHistory:
    def test_habit_history(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "history", "habit1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2


class TestHabitArchive:
    def test_archive_habit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "archive", "habit1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "archived" in data["message"]

    def test_unarchive_habit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "unarchive", "habit1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "unarchived" in data["message"]


class TestHabitDelete:
    def test_delete_habit_with_yes(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.habit_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["habit", "delete", "habit1", "--yes"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "deleted" in data["message"]
