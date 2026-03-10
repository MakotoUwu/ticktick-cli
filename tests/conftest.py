"""Shared test fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ticktick_cli.api.client import TickTickClient


@pytest.fixture
def runner() -> CliRunner:
    """Click CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def mock_v2() -> MagicMock:
    """Mock V2Client."""
    v2 = MagicMock()
    v2.sync.return_value = {
        "projectProfiles": [
            {"id": "proj1", "name": "Inbox"},
            {"id": "proj2", "name": "Work"},
        ],
        "syncTaskBean": {
            "update": [
                {
                    "id": "task1",
                    "title": "Buy groceries",
                    "projectId": "proj1",
                    "status": 0,
                    "priority": 5,
                    "dueDate": "2026-03-09T00:00:00.000+0000",
                    "tags": ["shopping"],
                    "content": "",
                    "isAllDay": False,
                },
                {
                    "id": "task2",
                    "title": "Write report",
                    "projectId": "proj2",
                    "status": 0,
                    "priority": 3,
                    "dueDate": "2026-03-10T00:00:00.000+0000",
                    "tags": ["work"],
                    "content": "Quarterly report",
                    "isAllDay": False,
                },
            ]
        },
        "tags": [
            {"name": "shopping", "color": "#FF0000"},
            {"name": "work", "color": "#00FF00"},
        ],
        "projectGroups": [],
        "filters": [],
    }
    v2.get_task.return_value = {
        "id": "task1",
        "title": "Buy groceries",
        "projectId": "proj1",
        "status": 0,
        "priority": 5,
        "dueDate": "2026-03-09T00:00:00.000+0000",
        "tags": ["shopping"],
        "content": "",
        "isAllDay": False,
    }
    v2.batch_tasks.return_value = {}
    v2.batch_habits.return_value = {}
    v2.batch_tags.return_value = {}
    v2.batch_columns.return_value = {}
    v2.batch_project_groups.return_value = {}
    v2.batch_habit_checkins.return_value = {}
    v2.get_habits.return_value = [
        {
            "id": "habit1",
            "name": "Exercise",
            "type": "Boolean",
            "goal": 1.0,
            "unit": "Count",
            "color": "#97E38B",
            "status": 0,
            "totalCheckIns": 10,
            "currentStreak": 3,
            "iconRes": "habit_exercise",
            "sectionId": "_morning",
        }
    ]
    v2.get_columns.return_value = [
        {"id": "col1", "name": "To Do", "sortOrder": 0},
        {"id": "col2", "name": "Done", "sortOrder": 1},
    ]
    v2.get_completed_tasks.return_value = []
    v2.get_deleted_tasks.return_value = {"tasks": []}
    v2.get_focus_heatmap.return_value = [
        {"duration": 60, "day": "20260301", "timezone": "America/New_York"},
        {"duration": 30, "day": "20260302", "timezone": "America/New_York"},
    ]
    v2.get_focus_by_tag.return_value = {
        "projectDurations": {"Inbox": 120, "Work": 60},
        "tagDurations": {"work": 90, "study": 45},
        "taskDurations": {"Write report": 60},
    }
    v2.get_user_profile.return_value = {
        "username": "testuser",
        "name": "Test User",
        "email": "test@example.com",
        "timeZone": "America/New_York",
        "inboxId": "inbox_id",
        "createdTime": "2024-01-01T00:00:00.000+0000",
    }
    v2.get_user_status.return_value = {
        "proLevel": 0,
        "proExpireDate": "",
        "subscribeType": "",
        "freeTrial": False,
    }
    v2.get_user_statistics.return_value = {
        "completedCount": 100,
        "currentStreak": 5,
    }
    v2.get_user_preferences.return_value = {
        "timeZone": "America/New_York",
        "startOfWeek": 0,
    }
    v2.query_habit_checkins.return_value = {
        "checkins": {
            "habit1": [
                {"checkinStamp": 20260301, "value": 1, "status": 2},
                {"checkinStamp": 20260302, "value": 1, "status": 2},
            ]
        }
    }
    v2.rename_tag.return_value = {}
    v2.delete_tag.return_value = {}
    v2.merge_tags.return_value = {}
    v2.move_tasks.return_value = {}
    v2.authenticate.return_value = {"token": "v2_session"}
    v2.get_session_cookies.return_value = {"t": "session_cookie"}
    return v2


@pytest.fixture
def mock_v1() -> MagicMock:
    """Mock V1Client."""
    v1 = MagicMock()
    v1.list_projects.return_value = [
        {"id": "proj1", "name": "Inbox"},
        {"id": "proj2", "name": "Work"},
    ]
    v1.create_task.return_value = {
        "id": "new_task",
        "title": "New Task",
        "projectId": "proj1",
        "status": 0,
        "priority": 0,
    }
    v1.complete_task.return_value = {}
    return v1


@pytest.fixture
def mock_client(mock_v1: MagicMock, mock_v2: MagicMock) -> MagicMock:
    """Mock TickTickClient with both V1 and V2."""
    client = MagicMock(spec=TickTickClient)
    client._v1 = mock_v1
    client._v2 = mock_v2
    client.v1 = mock_v1
    client.v2 = mock_v2
    client.has_v1 = True
    client.has_v2 = True
    client.list_projects.return_value = [
        {"id": "proj1", "name": "Inbox"},
        {"id": "proj2", "name": "Work"},
    ]
    client.get_all_tasks.return_value = mock_v2.sync.return_value["syncTaskBean"]["update"]
    client.get_all_tags.return_value = mock_v2.sync.return_value["tags"]
    client.get_all_project_groups.return_value = []
    return client
