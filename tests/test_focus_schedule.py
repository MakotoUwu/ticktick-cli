"""Tests for deterministic timed-task focus scheduling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.api.client import TickTickClient
from ticktick_cli.api.v1 import V1Client
from ticktick_cli.commands.focus_cmd import focus_group
from ticktick_cli.focus_schedule import (
    next_scheduled_focus,
    parse_task_datetime,
    scheduled_focus_plan,
    select_scheduled_focus,
)


def _task(**overrides):
    task = {
        "id": "task-1",
        "title": "Timed work",
        "status": 0,
        "priority": 3,
        "isAllDay": False,
        "startDate": "2026-07-12T08:00:00.000+0000",
        "dueDate": "2026-07-12T09:15:00.000+0000",
        "timeZone": "Europe/Brussels",
    }
    task.update(overrides)
    return task


def _ctx():
    return {
        "human": False,
        "verbose": False,
        "profile": "default",
        "fields": None,
        "dry_run": False,
        "output_format": "json",
    }


def test_parse_task_datetime_preserves_offset() -> None:
    parsed = parse_task_datetime("2026-07-12T10:00:00.000+0200")

    assert parsed is not None
    assert parsed.utcoffset().total_seconds() == 7_200


def test_schedule_uses_full_task_window_at_start() -> None:
    plan = scheduled_focus_plan(
        _task(),
        now=datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc),
    )

    assert plan["focusMinutes"] == 75
    assert plan["scheduledDurationMinutes"] == 75
    assert plan["durationSource"] == "scheduled_window"


def test_schedule_uses_remaining_window_after_late_start() -> None:
    plan = scheduled_focus_plan(
        _task(),
        now=datetime(2026, 7, 12, 8, 25, tzinfo=timezone.utc),
    )

    assert plan["focusMinutes"] == 50
    assert plan["remainingScheduledMinutes"] == 50
    assert plan["durationSource"] == "scheduled_remaining"


def test_schedule_ignores_non_executable_tasks() -> None:
    now = datetime(2026, 7, 12, 8, 10, tzinfo=timezone.utc)

    assert scheduled_focus_plan(_task(isAllDay=True), now=now) is None
    assert scheduled_focus_plan(_task(status=2), now=now) is None
    assert scheduled_focus_plan(_task(dueDate=_task()["startDate"]), now=now) is None
    assert scheduled_focus_plan(_task(startDate=""), now=now) is None


def test_schedule_skips_when_less_than_five_minutes_remain() -> None:
    plan = scheduled_focus_plan(
        _task(),
        now=datetime(2026, 7, 12, 9, 11, tzinfo=timezone.utc),
    )

    assert plan is None


def test_schedule_caps_one_focus_block_at_three_hours() -> None:
    plan = scheduled_focus_plan(
        _task(dueDate="2026-07-12T13:00:00.000+0000"),
        now=datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc),
    )

    assert plan["focusMinutes"] == 180
    assert plan["scheduledDurationMinutes"] == 300


def test_selector_prefers_the_most_recent_overlapping_task() -> None:
    tasks = [
        _task(id="older", startDate="2026-07-12T08:00:00.000+0000"),
        _task(id="newer", startDate="2026-07-12T08:30:00.000+0000"),
    ]

    plan = select_scheduled_focus(
        tasks,
        now=datetime(2026, 7, 12, 8, 40, tzinfo=timezone.utc),
    )

    assert plan["taskId"] == "newer"


def test_selector_excludes_persisted_attempt_key() -> None:
    now = datetime(2026, 7, 12, 8, 10, tzinfo=timezone.utc)
    attempted = scheduled_focus_plan(_task(), now=now)["attemptKey"]

    assert select_scheduled_focus([_task()], now=now, attempted_keys=[attempted]) is None


def test_next_schedule_returns_the_earliest_future_task() -> None:
    tasks = [
        _task(
            id="later",
            startDate="2026-07-12T10:00:00.000+0000",
            dueDate="2026-07-12T10:30:00.000+0000",
        ),
        _task(
            id="next",
            startDate="2026-07-12T09:00:00.000+0000",
            dueDate="2026-07-12T09:30:00.000+0000",
        ),
    ]

    plan = next_scheduled_focus(
        tasks,
        now=datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc),
    )

    assert plan["taskId"] == "next"


def test_v1_filter_tasks_uses_official_payload() -> None:
    client = V1Client("token")
    client.post = MagicMock(return_value=[{"id": "task-1"}])

    result = client.filter_tasks(project_ids=["p1", "p2"], statuses=[0])

    assert result == [{"id": "task-1"}]
    client.post.assert_called_once_with(
        "/task/filter",
        json_data={"projectIds": ["p1", "p2"], "status": [0]},
    )


def test_unified_client_filters_active_folder_projects() -> None:
    client = TickTickClient()
    client._v1 = MagicMock()
    client._v1.list_projects.return_value = [
        {"id": "p1", "groupId": "north-star", "closed": False},
        {"id": "p2", "groupId": "north-star", "closed": True},
        {"id": "p3", "groupId": "elsewhere", "closed": False},
    ]
    client._v1.filter_tasks.return_value = [_task()]

    tasks = client.get_folder_tasks("north-star")

    assert tasks[0]["id"] == "task-1"
    client._v1.filter_tasks.assert_called_once_with(project_ids=["p1"], statuses=[0])


@patch("ticktick_cli.commands.focus_cmd.get_client")
def test_focus_due_command_is_read_only(mock_get: MagicMock) -> None:
    client = MagicMock()
    client.get_folder_tasks.return_value = [_task()]
    mock_get.return_value = client

    result = CliRunner().invoke(
        focus_group,
        ["due", "--folder-id", "north-star", "--at", "2026-07-12T08:10:00+00:00"],
        obj=_ctx(),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["data"]["status"] == "due"
    assert payload["data"]["focusMinutes"] == 65
    client.v2.focus_op.assert_not_called()
