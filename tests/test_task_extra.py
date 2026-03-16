"""Tests for untested task subcommands — edit, abandon, pin, unpin, today,
overdue, completed, trash, batch-add."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.commands.task_cmd import task_group

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


# ── Task Edit ────────────────────────────────────────────────


class TestTaskEdit:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_title(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--title", "Updated Title"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "updated" in data["message"]
        call_args = client.v2.batch_tasks.call_args[1]
        updated = call_args["update"][0]
        assert updated["id"] == "t1"
        assert updated["title"] == "Updated Title"
        assert updated["projectId"] == "proj1"

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_priority(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--priority", "high"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_tasks.call_args[1]
        updated = call_args["update"][0]
        assert updated["priority"] == 5  # high maps to 5

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_content(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--content", "New notes here"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_tasks.call_args[1]
        assert call_args["update"][0]["content"] == "New notes here"

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_tags(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "-t", "work", "-t", "urgent"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_tasks.call_args[1]
        assert call_args["update"][0]["tags"] == ["work", "urgent"]

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_column(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--column", "col_abc"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_tasks.call_args[1]
        assert call_args["update"][0]["columnId"] == "col_abc"

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_multiple_fields(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--title", "New", "--priority", "low", "--content", "Body"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_tasks.call_args[1]
        updated = call_args["update"][0]
        assert updated["title"] == "New"
        assert updated["priority"] == 1  # low maps to 1
        assert updated["content"] == "Body"

    def test_edit_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--title", "Dry Title"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.edit"
        assert data["details"]["title"] == "Dry Title"

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.side_effect = Exception("Server error")

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--title", "Fail"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_edit_fetches_project_id(self, mock_get: MagicMock) -> None:
        """When no --project is given, edit should fetch the task to get projectId."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "auto_proj"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["edit", "t1", "--title", "X"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        client.v2.get_task.assert_called_once_with("t1")
        call_args = client.v2.batch_tasks.call_args[1]
        assert call_args["update"][0]["projectId"] == "auto_proj"


# ── Task Abandon ─────────────────────────────────────────────


class TestTaskAbandon:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_abandon_single(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(task_group, ["abandon", "t1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Abandoned 1 task(s)" in data["message"]
        call_args = client.v2.batch_tasks.call_args[1]
        updated = call_args["update"][0]
        assert updated["status"] == -1  # -1 = won't do

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_abandon_multiple(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.side_effect = [
            {"id": "t1", "projectId": "proj1"},
            {"id": "t2", "projectId": "proj2"},
        ]
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(task_group, ["abandon", "t1", "t2"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Abandoned 2 task(s)" in data["message"]
        call_args = client.v2.batch_tasks.call_args[1]
        assert len(call_args["update"]) == 2
        assert all(u["status"] == -1 for u in call_args["update"])

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_abandon_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.side_effect = Exception("Task not found")

        runner = CliRunner()
        result = runner.invoke(task_group, ["abandon", "bad_id"], obj=_make_ctx())
        assert result.exit_code == 1


# ── Task Pin ─────────────────────────────────────────────────


class TestTaskPin:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_pin_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(task_group, ["pin", "t1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "pinned" in data["message"]
        call_args = client.v2.batch_tasks.call_args[1]
        updated = call_args["update"][0]
        assert updated["id"] == "t1"
        assert updated["projectId"] == "proj1"
        assert updated["pinnedTime"] is not None
        assert "T" in updated["pinnedTime"]  # ISO format check

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_pin_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.side_effect = Exception("Not found")

        runner = CliRunner()
        result = runner.invoke(task_group, ["pin", "bad_id"], obj=_make_ctx())
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_pin_sets_current_time(self, mock_get: MagicMock) -> None:
        """pinnedTime should be close to the current time."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(task_group, ["pin", "t1"], obj=_make_ctx())
        assert result.exit_code == 0
        call_args = client.v2.batch_tasks.call_args[1]
        pinned_time = call_args["update"][0]["pinnedTime"]
        # Verify it's a parseable datetime string
        assert len(pinned_time) > 10
        assert "+0000" in pinned_time


# ── Task Unpin ───────────────────────────────────────────────


class TestTaskUnpin:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_unpin_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "proj1"}
        client.v2.batch_tasks.return_value = {}

        runner = CliRunner()
        result = runner.invoke(task_group, ["unpin", "t1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "unpinned" in data["message"]
        call_args = client.v2.batch_tasks.call_args[1]
        updated = call_args["update"][0]
        assert updated["id"] == "t1"
        assert updated["pinnedTime"] is None

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_unpin_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.side_effect = Exception("Task not found")

        runner = CliRunner()
        result = runner.invoke(task_group, ["unpin", "bad_id"], obj=_make_ctx())
        assert result.exit_code == 1


# ── Task Today ───────────────────────────────────────────────


class TestTaskToday:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_today_lists_due_today(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        today_str = datetime.now().strftime("%Y-%m-%d")
        client.get_all_tasks.return_value = [
            {"id": "t1", "title": "Due today", "dueDate": f"{today_str}T00:00:00.000+0000", "status": 0, "priority": 0},
            {"id": "t2", "title": "Due tomorrow", "dueDate": "2099-12-31T00:00:00.000+0000", "status": 0, "priority": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["today"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        # Only the task due today should appear
        titles = [t["title"] for t in data["data"]]
        assert "Due today" in titles
        assert "Due tomorrow" not in titles

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_today_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.get_all_tasks.return_value = [
            {"id": "t1", "title": "No due", "status": 0, "priority": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["today"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0


# ── Task Overdue ─────────────────────────────────────────────


class TestTaskOverdue:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_overdue_lists_past_due(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        client.get_all_tasks.return_value = [
            {"id": "t1", "title": "Overdue task", "dueDate": f"{yesterday}T00:00:00.000+0000", "status": 0, "priority": 0},
            {"id": "t2", "title": "Future task", "dueDate": f"{tomorrow}T00:00:00.000+0000", "status": 0, "priority": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["overdue"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        titles = [t["title"] for t in data["data"]]
        assert "Overdue task" in titles
        assert "Future task" not in titles

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_overdue_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        client.get_all_tasks.return_value = [
            {"id": "t1", "title": "Future", "dueDate": f"{future}T00:00:00.000+0000", "status": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["overdue"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0


# ── Task Completed ───────────────────────────────────────────


class TestTaskCompleted:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_completed_default_range(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_completed_tasks.return_value = [
            {"id": "t1", "title": "Done task", "status": 2, "priority": 3, "dueDate": "2026-03-01"},
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["completed"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 1
        assert data["data"][0]["title"] == "Done task"
        # Verify API was called
        client.v2.get_completed_tasks.assert_called_once()

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_completed_with_date_range(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_completed_tasks.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["completed", "--from", "2026-01-01", "--to", "2026-03-01"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0
        call_args = client.v2.get_completed_tasks.call_args
        fd = call_args[0][0]
        td = call_args[0][1]
        assert fd.year == 2026 and fd.month == 1 and fd.day == 1
        assert td.year == 2026 and td.month == 3 and td.day == 1

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_completed_with_limit(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_completed_tasks.return_value = [
            {"id": f"t{i}", "title": f"Task {i}", "status": 2, "priority": 0}
            for i in range(10)
        ]

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["completed", "--limit", "5"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.get_completed_tasks.call_args
        assert call_args[1]["limit"] == 5

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_completed_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_completed_tasks.side_effect = Exception("API Error")

        runner = CliRunner()
        result = runner.invoke(task_group, ["completed"], obj=_make_ctx())
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_completed_json_format(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_completed_tasks.return_value = [
            {"id": "c1", "title": "Complete", "status": 2, "priority": 5, "dueDate": "2026-02-15"},
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["completed"], obj=_make_ctx())
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "count" in data
        item = data["data"][0]
        assert "id" in item
        assert "title" in item
        assert "priority" in item


# ── Task Trash ───────────────────────────────────────────────


class TestTaskTrash:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_trash_with_dict_response(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_deleted_tasks.return_value = {
            "tasks": [
                {"id": "d1", "title": "Deleted task 1", "status": 0, "priority": 0},
                {"id": "d2", "title": "Deleted task 2", "status": 0, "priority": 3},
            ]
        }

        runner = CliRunner()
        result = runner.invoke(task_group, ["trash"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["data"][0]["title"] == "Deleted task 1"

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_trash_with_list_response(self, mock_get: MagicMock) -> None:
        """API might return a list directly instead of a dict."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_deleted_tasks.return_value = [
            {"id": "d1", "title": "Trashed", "status": 0, "priority": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["trash"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_trash_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_deleted_tasks.return_value = {"tasks": []}

        runner = CliRunner()
        result = runner.invoke(task_group, ["trash"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_trash_with_limit(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_deleted_tasks.return_value = {
            "tasks": [
                {"id": f"d{i}", "title": f"Del {i}", "status": 0, "priority": 0}
                for i in range(20)
            ]
        }

        runner = CliRunner()
        result = runner.invoke(task_group, ["trash", "--limit", "5"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 5
        client.v2.get_deleted_tasks.assert_called_once_with(limit=5)

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_trash_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_deleted_tasks.side_effect = Exception("Auth failed")

        runner = CliRunner()
        result = runner.invoke(task_group, ["trash"], obj=_make_ctx())
        assert result.exit_code == 1


# ── Task Batch-Add ───────────────────────────────────────────


class TestTaskBatchAdd:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_batch_add_list(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_tasks.return_value = {}

        tasks = [
            {"title": "Task A", "priority": 5},
            {"title": "Task B", "priority": 0},
            {"title": "Task C", "priority": 3},
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(tasks, f)
            tmppath = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                task_group,
                ["batch-add", "--file", tmppath],
                obj=_make_ctx(),
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "Created 3 task(s)" in data["message"]
            call_args = client.v2.batch_tasks.call_args[1]
            assert len(call_args["add"]) == 3
        finally:
            os.unlink(tmppath)

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_batch_add_single_object(self, mock_get: MagicMock) -> None:
        """A single JSON object should be wrapped in a list."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_tasks.return_value = {}

        task = {"title": "Single task"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(task, f)
            tmppath = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                task_group,
                ["batch-add", "--file", tmppath],
                obj=_make_ctx(),
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "Created 1 task(s)" in data["message"]
            call_args = client.v2.batch_tasks.call_args[1]
            assert len(call_args["add"]) == 1
            assert call_args["add"][0]["title"] == "Single task"
        finally:
            os.unlink(tmppath)

    def test_batch_add_file_not_found(self) -> None:
        """Non-existent file should fail."""
        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["batch-add", "--file", "/tmp/nonexistent_file_12345.json"],
            obj=_make_ctx(),
        )
        assert result.exit_code != 0

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_batch_add_invalid_json(self, mock_get: MagicMock) -> None:
        """Invalid JSON should raise an error."""
        client = _mock_client()
        mock_get.return_value = client

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("not valid json{{{")
            tmppath = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                task_group,
                ["batch-add", "--file", tmppath],
                obj=_make_ctx(),
            )
            assert result.exit_code == 1
        finally:
            os.unlink(tmppath)

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_batch_add_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_tasks.side_effect = Exception("Rate limit exceeded")

        tasks = [{"title": "Fail"}]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(tasks, f)
            tmppath = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                task_group,
                ["batch-add", "--file", tmppath],
                obj=_make_ctx(),
            )
            assert result.exit_code == 1
        finally:
            os.unlink(tmppath)
