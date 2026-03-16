"""Tests for subtask commands — set, unset, list."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.commands.subtask_cmd import subtask_group

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


# ── Subtask Set ──────────────────────────────────────────────


class TestSubtaskSet:
    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_set_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "child1", "projectId": "proj1"}
        client.v2.set_task_parent.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            subtask_group,
            ["set", "child1", "--parent", "parent1"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "subtask" in data["message"]
        assert "parent1" in data["message"]
        client.v2.get_task.assert_called_once_with("child1")
        client.v2.set_task_parent.assert_called_once_with("child1", "proj1", "parent1")

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_set_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.side_effect = Exception("Task not found")

        runner = CliRunner()
        result = runner.invoke(
            subtask_group,
            ["set", "bad_task", "--parent", "parent1"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 1

    def test_set_requires_parent(self) -> None:
        """--parent is required."""
        runner = CliRunner()
        result = runner.invoke(
            subtask_group,
            ["set", "child1"],
            obj=_make_ctx(),
        )
        assert result.exit_code != 0

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_set_json_envelope(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "p1"}
        client.v2.set_task_parent.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            subtask_group,
            ["set", "t1", "--parent", "p2"],
            obj=_make_ctx(),
        )
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "message" in data


# ── Subtask Unset ────────────────────────────────────────────


class TestSubtaskUnset:
    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_unset_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "child1", "projectId": "proj1"}
        client.v2.unset_task_parent.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            subtask_group,
            ["unset", "child1", "--parent", "parent1"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "removed" in data["message"]
        assert "parent1" in data["message"]
        client.v2.get_task.assert_called_once_with("child1")
        client.v2.unset_task_parent.assert_called_once_with("child1", "proj1", "parent1")

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_unset_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "child1", "projectId": "proj1"}
        client.v2.unset_task_parent.side_effect = Exception("Not a subtask")

        runner = CliRunner()
        result = runner.invoke(
            subtask_group,
            ["unset", "child1", "--parent", "parent1"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 1

    def test_unset_requires_parent(self) -> None:
        """--parent is required."""
        runner = CliRunner()
        result = runner.invoke(
            subtask_group,
            ["unset", "child1"],
            obj=_make_ctx(),
        )
        assert result.exit_code != 0


# ── Subtask List ─────────────────────────────────────────────


class TestSubtaskList:
    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_list_with_subtasks(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.get_all_tasks.return_value = [
            {"id": "t1", "title": "Subtask 1", "parentId": "parent1", "status": 0, "priority": 3},
            {"id": "t2", "title": "Subtask 2", "parentId": "parent1", "status": 2, "priority": 5},
            {"id": "t3", "title": "Other task", "parentId": "parent2", "status": 0, "priority": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(subtask_group, ["list", "parent1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["data"][0]["title"] == "Subtask 1"
        assert data["data"][0]["status"] == "active"
        assert data["data"][1]["title"] == "Subtask 2"
        assert data["data"][1]["status"] == "completed"

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_list_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.get_all_tasks.return_value = [
            {"id": "t1", "title": "Other task", "parentId": "other_parent"},
        ]

        runner = CliRunner()
        result = runner.invoke(subtask_group, ["list", "parent1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_list_no_parent_id(self, mock_get: MagicMock) -> None:
        """Tasks without parentId should not match."""
        client = _mock_client()
        mock_get.return_value = client
        client.get_all_tasks.return_value = [
            {"id": "t1", "title": "Top-level", "status": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(subtask_group, ["list", "parent1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_list_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.get_all_tasks.side_effect = Exception("Auth failure")

        runner = CliRunner()
        result = runner.invoke(subtask_group, ["list", "parent1"], obj=_make_ctx())
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_list_json_format(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.get_all_tasks.return_value = [
            {"id": "s1", "title": "Sub", "parentId": "p1", "status": 0, "priority": 1},
        ]

        runner = CliRunner()
        result = runner.invoke(subtask_group, ["list", "p1"], obj=_make_ctx())
        data = json.loads(result.output)
        item = data["data"][0]
        assert "id" in item
        assert "title" in item
        assert "status" in item
        assert "priority" in item

    @patch("ticktick_cli.commands.subtask_cmd.get_client")
    def test_list_priority_default(self, mock_get: MagicMock) -> None:
        """Tasks missing priority should default to 0."""
        client = _mock_client()
        mock_get.return_value = client
        client.get_all_tasks.return_value = [
            {"id": "s1", "title": "No Priority", "parentId": "p1"},
        ]

        runner = CliRunner()
        result = runner.invoke(subtask_group, ["list", "p1"], obj=_make_ctx())
        data = json.loads(result.output)
        assert data["data"][0]["priority"] == 0
