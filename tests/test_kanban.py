"""Tests for kanban column commands — list, create, edit, delete."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.commands.kanban_cmd import column_group

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


# ── Column List ──────────────────────────────────────────────


class TestColumnList:
    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_list_columns(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_columns.return_value = [
            {"id": "col1", "name": "To Do", "sortOrder": 0},
            {"id": "col2", "name": "In Progress", "sortOrder": 1},
            {"id": "col3", "name": "Done", "sortOrder": 2},
        ]

        runner = CliRunner()
        result = runner.invoke(column_group, ["list", "proj1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 3
        assert data["data"][0]["name"] == "To Do"
        assert data["data"][1]["name"] == "In Progress"
        assert data["data"][2]["id"] == "col3"
        client.v2.get_columns.assert_called_once_with("proj1")

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_list_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_columns.return_value = []

        runner = CliRunner()
        result = runner.invoke(column_group, ["list", "proj1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_list_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_columns.side_effect = Exception("Project not found")

        runner = CliRunner()
        result = runner.invoke(column_group, ["list", "bad_proj"], obj=_make_ctx())
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_list_json_format(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_columns.return_value = [
            {"id": "c1", "name": "Col", "sortOrder": 0},
        ]

        runner = CliRunner()
        result = runner.invoke(column_group, ["list", "p1"], obj=_make_ctx())
        data = json.loads(result.output)
        assert "ok" in data
        assert "data" in data
        assert "count" in data
        item = data["data"][0]
        assert "id" in item
        assert "name" in item
        assert "sortOrder" in item

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_list_missing_fields(self, mock_get: MagicMock) -> None:
        """Columns with missing fields should use defaults."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_columns.return_value = [{"id": "c1"}]

        runner = CliRunner()
        result = runner.invoke(column_group, ["list", "p1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"][0]["name"] == ""
        assert data["data"][0]["sortOrder"] == 0


# ── Column Create ────────────────────────────────────────────


class TestColumnCreate:
    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_create_simple(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.return_value = {}

        runner = CliRunner()
        result = runner.invoke(column_group, ["create", "proj1", "Review"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Review" in data["message"]
        client.v2.batch_columns.assert_called_once()
        call_args = client.v2.batch_columns.call_args[1]
        added = call_args["add"][0]
        assert added["projectId"] == "proj1"
        assert added["name"] == "Review"

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_create_with_sort_order(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["create", "proj1", "Testing", "--sort-order", "5"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_columns.call_args[1]
        added = call_args["add"][0]
        assert added["sortOrder"] == 5

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_create_without_sort_order(self, mock_get: MagicMock) -> None:
        """sortOrder should not be in the payload if not specified."""
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.return_value = {}

        runner = CliRunner()
        result = runner.invoke(column_group, ["create", "proj1", "Backlog"], obj=_make_ctx())
        assert result.exit_code == 0
        call_args = client.v2.batch_columns.call_args[1]
        added = call_args["add"][0]
        assert "sortOrder" not in added

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_create_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.side_effect = Exception("Permission denied")

        runner = CliRunner()
        result = runner.invoke(column_group, ["create", "proj1", "Test"], obj=_make_ctx())
        assert result.exit_code == 1


# ── Column Edit ──────────────────────────────────────────────


class TestColumnEdit:
    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_edit_name(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["edit", "col1", "--project", "proj1", "--name", "New Name"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "updated" in data["message"]
        call_args = client.v2.batch_columns.call_args[1]
        updated = call_args["update"][0]
        assert updated["id"] == "col1"
        assert updated["projectId"] == "proj1"
        assert updated["name"] == "New Name"

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_edit_sort_order(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["edit", "col1", "--project", "proj1", "--sort-order", "10"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_columns.call_args[1]
        updated = call_args["update"][0]
        assert updated["sortOrder"] == 10

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_edit_both_fields(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["edit", "col1", "--project", "proj1", "--name", "Renamed", "--sort-order", "3"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_columns.call_args[1]
        updated = call_args["update"][0]
        assert updated["name"] == "Renamed"
        assert updated["sortOrder"] == 3

    def test_edit_requires_project(self) -> None:
        """--project is required for edit."""
        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["edit", "col1", "--name", "X"],
            obj=_make_ctx(),
        )
        assert result.exit_code != 0

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_edit_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.side_effect = Exception("Column not found")

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["edit", "bad_col", "--project", "proj1", "--name", "X"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 1


# ── Column Delete ────────────────────────────────────────────


class TestColumnDelete:
    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_delete_with_yes(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["delete", "col1", "--project", "proj1", "--yes"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "deleted" in data["message"]
        client.v2.batch_columns.assert_called_once_with(
            delete=[{"columnId": "col1", "projectId": "proj1"}]
        )

    def test_delete_requires_project(self) -> None:
        """--project is required for delete."""
        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["delete", "col1", "--yes"],
            obj=_make_ctx(),
        )
        assert result.exit_code != 0

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_delete_api_error(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_columns.side_effect = Exception("Not found")

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["delete", "col1", "--project", "proj1", "--yes"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 1

    @patch("ticktick_cli.commands.kanban_cmd.get_client")
    def test_delete_confirmation_abort(self, mock_get: MagicMock) -> None:
        """Without --yes, delete should prompt and abort if user says no."""
        client = _mock_client()
        mock_get.return_value = client

        runner = CliRunner()
        result = runner.invoke(
            column_group,
            ["delete", "col1", "--project", "proj1"],
            obj=_make_ctx(),
            input="n\n",
        )
        assert result.exit_code != 0
        client.v2.batch_columns.assert_not_called()
