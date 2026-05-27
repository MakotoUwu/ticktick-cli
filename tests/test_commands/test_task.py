"""Test task commands."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestTaskList:
    def test_list_tasks_json(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["data"][0]["title"] in ("Buy groceries", "Write report")

    def test_list_tasks_with_priority_filter(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list", "--priority", "high"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        # Only "Buy groceries" has priority=5 (high)
        assert all(t["priority"] == "high" for t in data["data"])

    def test_list_tasks_with_tag_filter(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list", "--tag", "shopping"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert all("shopping" in t["tags"] for t in data["data"])

    def test_list_tasks_with_limit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list", "--limit", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["data"]) <= 1

    def test_list_tasks_with_offset_and_limit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["--offset", "1", "task", "list", "--sort", "title", "--limit", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["total"] == 2
        assert data["data"][0]["title"] == "Write report"

    def test_list_tasks_with_all_ignores_limit(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["--all", "task", "list", "--limit", "1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 2


class TestTaskShow:
    def test_show_task(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "show", "task1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["id"] == "task1"
        assert data["data"]["title"] == "Buy groceries"


class TestTaskAdd:
    def test_add_task_v2(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "add", "New task"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "New task" in data["message"]
        assert data["data"]["title"] == "New task"
        assert re.fullmatch(r"[0-9a-f]{24}", data["data"]["id"])
        mock_client.v2.batch_tasks.assert_called_once()

    def test_add_task_v2_quiet_returns_id(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["-q", "task", "add", "Quiet task"])
        assert result.exit_code == 0
        assert re.fullmatch(r"[0-9a-f]{24}", result.output.strip())

    def test_add_task_with_options(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, [
                "task", "add", "Important task",
                "--priority", "high",
                "--tag", "work",
                "--tag", "urgent",
            ])
        assert result.exit_code == 0
        call_args = mock_client.v2.batch_tasks.call_args
        task_data = call_args[1]["add"][0]
        assert task_data["title"] == "Important task"
        assert task_data["priority"] == 5
        assert task_data["tags"] == ["work", "urgent"]

    def test_add_task_dry_run_if_not_exists_skips_client(self, runner: CliRunner) -> None:
        with patch(
            "ticktick_cli.commands.task_cmd.get_client",
            side_effect=AssertionError("get_client should not be called"),
        ):
            result = runner.invoke(cli, ["--dry-run", "task", "add", "New task", "--if-not-exists"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestTaskDone:
    def test_done_v1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "done", "task1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Completed 1 task(s)" in data["message"]


class TestTaskSkip:
    def test_skip_recurring_occurrence(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.get_task.return_value = {
            "id": "task1",
            "title": "Wake up",
            "projectId": "proj1",
            "status": 0,
            "repeatFlag": "RRULE:FREQ=DAILY;INTERVAL=1",
            "dueDate": "2026-05-27T04:30:00.000+0000",
            "timeZone": "Europe/Brussels",
            "exDate": [],
        }
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "skip", "task1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "Skipped recurrence 20260527" in data["message"]
        assert data["data"]["exDate"] == "20260527"
        update = mock_client.v2.skip_task_recurrence.call_args.args[0]
        assert update["id"] == "task1"
        assert update["projectId"] == "proj1"
        assert update["repeatFlag"] == "RRULE:FREQ=DAILY;INTERVAL=1"
        assert update["dueDate"] == "2026-05-27T04:30:00.000+0000"
        assert update["timeZone"] == "Europe/Brussels"
        assert update["exDate"] == ["20260527"]

    def test_skip_all_day_occurrence_preserves_calendar_date(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.v2.get_task.return_value = {
            "id": "task1",
            "title": "All-day recurring task",
            "projectId": "proj1",
            "status": 0,
            "repeatFlag": "RRULE:FREQ=DAILY;INTERVAL=1",
            "dueDate": "2026-05-27T00:00:00.000+0000",
            "timeZone": "America/New_York",
            "isAllDay": True,
            "exDate": [],
        }
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "skip", "task1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["exDate"] == "20260527"
        update = mock_client.v2.skip_task_recurrence.call_args.args[0]
        assert update["exDate"] == ["20260527"]

    def test_skip_dry_run_shows_payload(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.get_task.return_value = {
            "id": "task1",
            "title": "Wake up",
            "projectId": "proj1",
            "repeatFlag": "RRULE:FREQ=DAILY;INTERVAL=1",
            "dueDate": "2026-05-27T04:30:00.000+0000",
            "exDate": ["20260526"],
        }
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["--dry-run", "task", "skip", "task1", "--date", "2026-05-27"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.skip"
        assert data["details"]["payload"]["exDate"] == ["20260526", "20260527"]
        assert data["details"]["payload"]["repeatFlag"] == "RRULE:FREQ=DAILY;INTERVAL=1"
        mock_client.v2.skip_task_recurrence.assert_not_called()

    def test_skip_rejects_non_recurring_task(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.get_task.return_value = {
            "id": "task1",
            "title": "One-off",
            "projectId": "proj1",
            "dueDate": "2026-05-27T04:30:00.000+0000",
            "exDate": [],
        }
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "skip", "task1"])
        assert result.exit_code == 1
        assert "not recurring" in result.stderr
        mock_client.v2.skip_task_recurrence.assert_not_called()


class TestTaskDelete:
    def test_delete_with_yes_flag(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "delete", "task1", "--yes"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Deleted 1 task(s)" in data["message"]


class TestTaskSearch:
    def test_search_tasks(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "search", "groceries"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert any("groceries" in t["title"].lower() for t in data["data"])


class TestTaskMove:
    def test_move_task(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "move", "task1", "--project", "proj2"])
        assert result.exit_code == 0
        mock_client.v2.move_tasks.assert_called_once()

    def test_move_dry_run_skips_client(self, runner: CliRunner) -> None:
        with patch(
            "ticktick_cli.commands.task_cmd.get_client",
            side_effect=AssertionError("get_client should not be called"),
        ):
            result = runner.invoke(
                cli,
                ["--dry-run", "task", "move", "task1", "--project", "proj2"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.move"
        assert data["details"] == {"task_id": "task1", "project": "proj2"}
