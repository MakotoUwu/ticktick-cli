"""Short-ID prefix resolution for task commands (OLE-141)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.cli import cli

FULL_ID = "6830a1b2c3d4e5f60718293a"
OTHER_ID = "6830ffffffffffffffffffff"


def _task(task_id: str, title: str = "Demo") -> dict:
    return {
        "id": task_id,
        "title": title,
        "projectId": "proj1",
        "status": 0,
        "priority": 0,
    }


def _patch(mock_client: MagicMock):
    return patch("ticktick_cli.commands.task_cmd.get_client", return_value=mock_client)


class TestShortIdResolution:
    def test_hex_prefix_resolves_to_full_id(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_tasks.return_value = [_task(FULL_ID)]
        mock_client.v2.get_task.return_value = _task(FULL_ID)
        with _patch(mock_client):
            result = runner.invoke(cli, ["task", "show", "6830a1b2"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["data"]["id"] == FULL_ID
        mock_client.v2.get_task.assert_called_once_with(FULL_ID)

    def test_full_id_passthrough_skips_lookup(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        mock_client.v2.get_task.return_value = _task(FULL_ID)
        with _patch(mock_client):
            result = runner.invoke(cli, ["task", "show", FULL_ID])
        assert result.exit_code == 0, result.output
        mock_client.get_all_tasks.assert_not_called()
        mock_client.v2.get_task.assert_called_once_with(FULL_ID)

    def test_non_hex_id_passthrough_skips_lookup(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        # Guards the 480-test suite: existing tests use ids like "task1".
        mock_client.v2.get_task.return_value = _task("task1")
        with _patch(mock_client):
            result = runner.invoke(cli, ["task", "show", "task1"])
        assert result.exit_code == 0, result.output
        mock_client.get_all_tasks.assert_not_called()
        mock_client.v2.get_task.assert_called_once_with("task1")

    def test_ambiguous_prefix_errors(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_all_tasks.return_value = [_task(FULL_ID), _task(OTHER_ID)]
        with _patch(mock_client):
            result = runner.invoke(cli, ["task", "show", "6830"])
        assert result.exit_code == 1
        assert "ambiguous" in result.output.lower()
        mock_client.v2.get_task.assert_not_called()

    def test_no_match_errors(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_all_tasks.return_value = [_task(FULL_ID)]
        with _patch(mock_client):
            result = runner.invoke(cli, ["task", "show", "deadbeef"])
        assert result.exit_code == 1
        assert "no active task" in result.output.lower()
        mock_client.v2.get_task.assert_not_called()

    def test_batch_done_resolves_each_prefix(
        self, runner: CliRunner, mock_client: MagicMock
    ) -> None:
        a = "aaaa1111" + "0" * 16
        b = "bbbb2222" + "0" * 16
        mock_client.get_all_tasks.return_value = [_task(a), _task(b)]
        mock_client.v2.get_task.return_value = _task(a)
        with _patch(mock_client):
            result = runner.invoke(cli, ["task", "done", "aaaa1111", "bbbb2222"])
        assert result.exit_code == 0, result.output
        called_ids = [c.args[1] for c in mock_client.v1.complete_task.call_args_list]
        assert a in called_ids and b in called_ids
