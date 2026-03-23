"""Tests for focus/pomodoro commands and models."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ticktick_cli.commands.focus_cmd import (
    _fmt_utc,
    _parse_time,
    focus_group,
)
from ticktick_cli.models.pomodoro import (
    FocusOperation,
    Pomodoro,
    PomodoroStatus,
    PomodoroTask,
)

# ── Pomodoro model tests ─────────────────────────────────────


class TestPomodoroModel:
    def test_create_from_api(self) -> None:
        data = {
            "id": "abc123def456789012345678",
            "startTime": "2026-03-12T13:00:00.000+0000",
            "endTime": "2026-03-12T13:30:00.000+0000",
            "pauseDuration": 0,
            "status": 1,
            "note": "test note",
            "tasks": [
                {
                    "tags": ["work"],
                    "projectName": "MyProject",
                    "startTime": "2026-03-12T13:00:00.000+0000",
                    "endTime": "2026-03-12T13:30:00.000+0000",
                }
            ],
            "added": True,
        }
        p = Pomodoro(**data)
        assert p.id == "abc123def456789012345678"
        assert p.status == PomodoroStatus.COMPLETED
        assert p.pause_duration == 0
        assert p.note == "test note"
        assert len(p.tasks) == 1
        assert p.tasks[0].project_name == "MyProject"
        assert p.tasks[0].tags == ["work"]

    def test_defaults(self) -> None:
        p = Pomodoro()
        assert p.id == ""
        assert p.status == PomodoroStatus.COMPLETED
        assert p.tasks == []
        assert p.added is True

    def test_to_output(self) -> None:
        p = Pomodoro(
            id="abc",
            startTime="2026-03-12T13:00:00.000+0000",
            endTime="2026-03-12T13:30:00.000+0000",
            note="focus!",
            tasks=[PomodoroTask()],
        )
        out = p.to_output()
        assert out["id"] == "abc"
        assert out["tasks"] == 1
        assert out["note"] == "focus!"

    def test_extra_fields_allowed(self) -> None:
        p = Pomodoro(id="x", unknownField="hello")
        assert p.id == "x"


class TestPomodoroTaskModel:
    def test_alias(self) -> None:
        t = PomodoroTask(projectName="P1", startTime="t1", endTime="t2")
        assert t.project_name == "P1"
        assert t.start_time == "t1"

    def test_defaults(self) -> None:
        t = PomodoroTask()
        assert t.tags == []
        assert t.project_name == ""


class TestFocusOperationModel:
    def test_create(self) -> None:
        op = FocusOperation(
            id="op1",
            oId="session1",
            op="start",
            duration=25,
            time="2026-03-12T13:00:00.000+0000",
        )
        assert op.op == "start"
        assert op.duration == 25
        assert op.o_id == "session1"

    def test_to_api(self) -> None:
        op = FocusOperation(id="op1", oId="s1", op="pause")
        api = op.to_api()
        assert api["oId"] == "s1"
        assert api["op"] == "pause"
        assert "o_id" not in api  # Should use alias


# ── Helper function tests ────────────────────────────────────


class TestFmtUtc:
    def test_format(self) -> None:
        dt = datetime(2026, 3, 12, 14, 30, 0, tzinfo=timezone.utc)
        assert _fmt_utc(dt) == "2026-03-12T14:30:00.000+0000"

    def test_naive_datetime_assumed_utc(self) -> None:
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = _fmt_utc(dt)
        assert "2026-01-01" in result
        assert "+0000" in result


class TestParseTime:
    def test_hhmm(self) -> None:
        result = _parse_time("14:30")
        assert result.tzinfo is not None  # Has timezone

    def test_iso_datetime(self) -> None:
        result = _parse_time("2026-03-12T14:30")
        assert result.year == 2026
        assert result.tzinfo is not None

    def test_iso_with_seconds(self) -> None:
        result = _parse_time("2026-03-12T14:30:45")
        assert result.second == 45

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse time"):
            _parse_time("not-a-time")


# ── CLI command tests (mocked API) ───────────────────────────


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
    return client


class TestFocusStart:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_start_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        # focus_op: first call returns idle state, second returns started
        client.v2.focus_op.side_effect = [
            {"point": 100, "current": {"exited": True}},
            {
                "point": 200,
                "current": {
                    "id": "sess123",
                    "startTime": "2026-03-12T14:00:00.000+0000",
                    "endTime": "2026-03-12T14:25:00.000+0000",
                    "duration": 25,
                },
            },
        ]

        runner = CliRunner()
        result = runner.invoke(focus_group, ["start"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["action"] == "started"
        assert data["data"]["duration"] == 25

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_start_already_running(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.return_value = {
            "point": 100,
            "current": {"exited": False, "status": 0, "id": "running123"},
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["start"], obj=_make_ctx())
        assert result.exit_code == 1

    def test_start_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            focus_group, ["start", "--duration", "30"], obj=_make_ctx(dry_run=True)
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_start_custom_duration(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.side_effect = [
            {"point": 100, "current": {"exited": True}},
            {"point": 200, "current": {"id": "s1", "duration": 45}},
        ]

        runner = CliRunner()
        result = runner.invoke(focus_group, ["start", "-d", "45"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["duration"] == 45

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_start_with_task(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.side_effect = [
            {"point": 100, "current": {"exited": True}},
            {
                "point": 200,
                "current": {
                    "id": "sess123",
                    "startTime": "2026-03-12T14:00:00.000+0000",
                    "endTime": "2026-03-12T14:25:00.000+0000",
                    "duration": 25,
                },
            },
        ]

        runner = CliRunner()
        result = runner.invoke(
            focus_group, ["start", "--task", "task123"], obj=_make_ctx()
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["data"]["taskId"] == "task123"

        start_call = client.v2.focus_op.call_args_list[1]
        assert start_call.kwargs["operations"][0]["focusOnId"] == "task123"


class TestFocusStop:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_stop_save(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.side_effect = [
            {
                "point": 100,
                "current": {
                    "id": "sess1",
                    "firstId": "sess1",
                    "exited": False,
                    "status": 0,
                    "duration": 25,
                    "startTime": "2026-03-12T14:00:00.000+0000",
                    "autoPomoLeft": 5,
                    "pomoCount": 1,
                },
            },
            {"point": 200, "current": {"exited": True}},
        ]
        client.v2.batch_pomodoros.return_value = {"id2etag": {}, "id2error": {}}

        runner = CliRunner()
        result = runner.invoke(focus_group, ["stop"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["action"] == "saved"
        assert client.v2.batch_pomodoros.called

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_stop_no_save(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.side_effect = [
            {
                "point": 100,
                "current": {
                    "id": "sess1",
                    "firstId": "sess1",
                    "exited": False,
                    "status": 0,
                    "duration": 25,
                    "autoPomoLeft": 5,
                    "pomoCount": 1,
                },
            },
            {"point": 200, "current": {"exited": True}},
        ]

        runner = CliRunner()
        result = runner.invoke(focus_group, ["stop", "--no-save"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["action"] == "abandoned"
        assert not client.v2.batch_pomodoros.called

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_stop_no_active(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.return_value = {
            "point": 100,
            "current": {"exited": True},
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["stop"], obj=_make_ctx())
        assert result.exit_code == 1

    def test_stop_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(focus_group, ["stop"], obj=_make_ctx(dry_run=True))
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestFocusStatus:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_status_idle(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.return_value = {
            "point": 100,
            "current": {"exited": True},
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["status"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["status"] == "idle"

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_status_running(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.return_value = {
            "point": 100,
            "current": {
                "id": "sess1",
                "exited": False,
                "status": 0,
                "duration": 25,
                "startTime": "2026-03-12T14:00:00.000+0000",
                "endTime": "2026-03-12T14:25:00.000+0000",
                "pomoCount": 1,
            },
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["status"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["status"] == "running"
        assert data["data"]["duration"] == 25


class TestFocusLink:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_link_requires_active_session(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.return_value = {
            "point": 100,
            "current": {"exited": True},
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["link", "task123"], obj=_make_ctx())
        assert result.exit_code == 1

        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert "No active focus session" in payload["error"]

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_link_fails_fast_for_running_session(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.focus_op.return_value = {
            "point": 100,
            "current": {
                "id": "sess1",
                "firstId": "sess1",
                "exited": False,
                "status": 0,
                "duration": 25,
                "startTime": "2026-03-12T14:00:00.000+0000",
                "endTime": "2026-03-12T14:25:00.000+0000",
                "pomoCount": 1,
            },
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["link", "task123"], obj=_make_ctx())
        assert result.exit_code == 1
        assert client.v2.focus_op.call_count == 1

        payload = json.loads(result.output)
        assert payload["ok"] is False
        assert "not supported reliably yet" in payload["error"]

    def test_link_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            focus_group, ["link", "task123"], obj=_make_ctx(dry_run=True)
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestFocusLog:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_log_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.batch_pomodoros.return_value = {"id2etag": {"x": "y"}, "id2error": {}}

        runner = CliRunner()
        result = runner.invoke(
            focus_group,
            ["log", "--start", "14:00", "--end", "14:30"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["action"] == "logged"
        assert data["data"]["duration"] == "30m"

    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_log_end_before_start(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        runner = CliRunner()
        result = runner.invoke(
            focus_group,
            ["log", "--start", "15:00", "--end", "14:00"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 1

    def test_log_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            focus_group,
            ["log", "--start", "14:00", "--end", "14:30"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestFocusDelete:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_delete_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.delete_pomodoro.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            focus_group, ["delete", "abc123"], obj=_make_ctx()
        )
        assert result.exit_code == 0
        client.v2.delete_pomodoro.assert_called_once_with("abc123")

    def test_delete_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            focus_group, ["delete", "abc123"], obj=_make_ctx(dry_run=True)
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestFocusStats:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_stats(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_focus_stats.return_value = {
            "todayPomoCount": 3,
            "todayPomoDuration": 90,
            "totalPomoCount": 766,
            "totalPomoDuration": 23869,
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["stats"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["todayPomos"] == 3
        assert data["data"]["totalMinutes"] == 23869


class TestFocusHeatmap:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_heatmap(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_focus_heatmap.return_value = [
            {"day": "20260312", "duration": 30, "timezone": "UTC"},
            {"day": "20260311", "duration": 0, "timezone": "UTC"},
        ]

        runner = CliRunner()
        result = runner.invoke(focus_group, ["heatmap", "--days", "7"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1  # Only non-zero
        assert data["data"][0]["minutes"] == 30


class TestFocusByTag:
    @patch("ticktick_cli.commands.focus_cmd.get_client")
    def test_by_tag(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_focus_by_tag.return_value = {
            "tagDurations": {"work": 120, "study": 60},
            "projectDurations": {"ProjectA": 90},
            "taskDurations": {},
        }

        runner = CliRunner()
        result = runner.invoke(focus_group, ["by-tag", "--days", "30"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 3
