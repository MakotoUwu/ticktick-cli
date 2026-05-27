"""Test task commands."""

from __future__ import annotations

import json
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
            "repeatFrom": "1",
            "exDate": ["2026-05-27"],
            "repeatFirstDate": "2026-05-28",
            "reminders": [{"id": "r1", "trigger": "TRIGGER:-PT30M"}],
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
        assert data["data"]["repeatFrom"] == "1"
        assert data["data"]["exDate"] == ["2026-05-27"]
        assert data["data"]["repeatFirstDate"] == "2026-05-28"
        assert data["data"]["reminders"] == [{"id": "r1", "trigger": "TRIGGER:-PT30M"}]
        assert data["data"]["commentCount"] == 3


class TestTaskAdd:
    def test_add_task_v2(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "add", "New task"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "New task" in data["message"]
        mock_client.v2.batch_tasks.assert_called_once()

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


class TestTaskMove:
    def test_move_task(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["task", "move", "task1", "--project", "proj2"])
        assert result.exit_code == 0
        mock_client.v2.move_tasks.assert_called_once()
