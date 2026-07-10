"""Test task commands."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli
from ticktick_cli.exceptions import RateLimitError


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

    def test_list_tasks_with_sort_order(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_all_tasks.return_value = [
            {
                "id": "task-second",
                "title": "Second",
                "projectId": "proj1",
                "status": 0,
                "priority": 0,
                "sortOrder": 200,
            },
            {
                "id": "task-first",
                "title": "First",
                "projectId": "proj1",
                "status": 0,
                "priority": 0,
                "sortOrder": 100,
            },
        ]

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list", "--sort", "sortOrder"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"][0]["title"] == "First"
        assert data["data"][0]["sortOrder"] == 100
        assert data["data"][1]["title"] == "Second"
        assert data["data"][1]["sortOrder"] == 200

    def test_list_tasks_with_folder_id_uses_v1_project_data(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.v1.list_projects.return_value = [
            {"id": "proj1", "name": "To do", "groupId": "folder1"},
            {"id": "proj2", "name": "Routine", "groupId": "other-folder"},
        ]
        mock_client.v1.get_project_with_data.return_value = {
            "columns": [{"id": "col1", "name": "Top 3"}],
            "tasks": [
                {
                    "id": "task1",
                    "title": "Check email",
                    "status": 0,
                    "priority": 0,
                    "columnId": "col1",
                }
            ]
        }

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list", "--folder-id", "folder1"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["data"][0]["title"] == "Check email"
        assert data["data"][0]["projectId"] == "proj1"
        assert data["data"][0]["projectName"] == "To do"
        assert data["data"][0]["groupId"] == "folder1"
        assert data["data"][0]["columnId"] == "col1"
        assert data["data"][0]["columnName"] == "Top 3"
        mock_client.get_all_tasks.assert_not_called()

    def test_list_tasks_with_folder_name_resolves_group(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_project_groups.return_value = [
            {"id": "folder1", "name": "North Star"},
        ]
        mock_client.v1.list_projects.return_value = [
            {"id": "proj1", "name": "Agents", "groupId": "folder1"},
        ]
        mock_client.v1.get_project_with_data.return_value = {
            "project": {"id": "proj1", "name": "Agents", "groupId": "folder1"},
            "tasks": [
                {
                    "id": "task-agent",
                    "title": "Create speaker agent",
                    "projectId": "proj1",
                    "status": 0,
                    "priority": 0,
                }
            ],
        }

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list", "--folder", "North Star"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["data"][0]["title"] == "Create speaker agent"
        mock_client.get_all_project_groups.assert_called_once()
        mock_client.get_all_tasks.assert_not_called()

    def test_list_tasks_with_folder_name_reports_v2_lookup_failure(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_project_groups.side_effect = Exception("API rate limit exceeded")

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "list", "--folder", "North Star"])

        assert result.exit_code == 1
        data = json.loads(result.stderr)
        assert data["ok"] is False
        assert "Use --folder-id" in data["error"]


class TestTaskShow:
    def test_show_task(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "show", "task1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["id"] == "task1"
        assert data["data"]["title"] == "Buy groceries"

    def test_show_task_includes_v2_metadata(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.v2.get_task.return_value = {
            "id": "task1",
            "title": "Detailed task",
            "projectId": "proj1",
            "status": 0,
            "priority": 0,
            "assignee": 123,
            "kind": "TEXT",
            "desc": "Longer description",
            "isFloating": True,
            "timeZone": "Europe/Brussels",
            "progress": 25,
            "sortOrder": 10,
            "repeatFrom": 1,
            "exDate": ["2026-05-27"],
            "repeatFirstDate": "2026-05-28",
            "reminders": ["TRIGGER:-PT30M"],
            "commentCount": 3,
        }

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "show", "task1"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["assignee"] == 123
        assert data["data"]["kind"] == "TEXT"
        assert data["data"]["desc"] == "Longer description"
        assert data["data"]["isFloating"] is True
        assert data["data"]["timeZone"] == "Europe/Brussels"
        assert data["data"]["progress"] == 25
        assert data["data"]["sortOrder"] == 10
        assert data["data"]["repeatFrom"] == 1
        assert data["data"]["exDate"] == ["2026-05-27"]
        assert data["data"]["repeatFirstDate"] == "2026-05-28"
        assert data["data"]["reminders"] == ["TRIGGER:-PT30M"]
        assert data["data"]["commentCount"] == 3


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

    def test_done_falls_back_to_v1_when_v2_lookup_is_rate_limited(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.v2.get_task.side_effect = RateLimitError("API rate limit exceeded (429).")
        mock_client.v1.get_project_with_data.side_effect = [
            {"project": {"id": "proj1", "name": "Inbox"}, "tasks": []},
            {"project": {"id": "proj2", "name": "Work"}, "tasks": [{"id": "task1"}]},
        ]

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "done", "task1"])

        assert result.exit_code == 0
        mock_client.v1.complete_task.assert_called_once_with("proj2", "task1")


class TestTaskAbandon:
    def test_abandon_falls_back_to_v1_when_v2_lookup_is_rate_limited(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.v2.get_task.side_effect = RateLimitError("API rate limit exceeded (429).")
        mock_client.v1.get_project_with_data.side_effect = [
            {"project": {"id": "proj1", "name": "Inbox"}, "tasks": []},
            {"project": {"id": "proj2", "name": "Work"}, "tasks": [{"id": "task1"}]},
        ]

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "abandon", "task1"])

        assert result.exit_code == 0
        mock_client.v2.batch_tasks.assert_called_once_with(
            update=[{"id": "task1", "projectId": "proj2", "status": -1}]
        )


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

    def test_search_tasks_with_filters(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_all_tasks.return_value = [
            {
                "id": "task1",
                "title": "Write report",
                "projectId": "proj1",
                "status": 0,
                "priority": 5,
                "tags": ["work"],
                "content": "",
            },
            {
                "id": "task2",
                "title": "Write report draft",
                "projectId": "proj2",
                "status": 0,
                "priority": 3,
                "tags": ["work"],
                "content": "",
            },
            {
                "id": "task3",
                "title": "Write report notes",
                "projectId": "proj1",
                "status": 0,
                "priority": 5,
                "tags": ["personal"],
                "content": "",
            },
        ]

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(
                cli,
                [
                    "task",
                    "search",
                    "report",
                    "--project",
                    "Inbox",
                    "--tag",
                    "work",
                    "--priority",
                    "high",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert [task["id"] for task in data["data"]] == ["task1"]

    def test_search_preserves_rate_limit_error(
        self,
        runner: CliRunner,
        mock_client: MagicMock,
    ) -> None:
        mock_client.get_all_tasks.side_effect = RateLimitError(
            "API rate limit exceeded (429). Retry after 30s.",
            status_code=429,
            retry_after_seconds=30,
        )

        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "search", "Louis"])

        assert result.exit_code == 5
        data = json.loads(result.stderr)
        assert data["ok"] is False
        assert data["error_type"] == "RateLimitError"
        assert data["status_code"] == 429
        assert data["retry_after_seconds"] == 30


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
