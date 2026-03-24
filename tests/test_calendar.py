"""Tests for read-only calendar discovery commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.commands.calendar_cmd import calendar_group


def _make_ctx() -> dict[str, object]:
    return {
        "human": False,
        "verbose": False,
        "profile": "default",
        "fields": None,
        "dry_run": False,
        "output_format": "json",
        "quiet": False,
        "offset": 0,
        "all": False,
    }


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.v2 = MagicMock()
    return client


class TestCalendarAccountList:
    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_list_accounts(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {
            "accounts": [
                {
                    "id": "acct1",
                    "account": "user@example.com",
                    "site": "google",
                    "createdTime": "2026-03-01T10:00:00.000+0000",
                    "modifiedTime": "2026-03-02T10:00:00.000+0000",
                    "calendars": [
                        {"id": "cal1", "visible": True},
                        {"id": "cal2", "visible": False},
                    ],
                }
            ]
        }

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["account", "list"], obj=_make_ctx())
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["data"][0]["id"] == "acct1"
        assert data["data"][0]["calendarCount"] == 2
        assert data["data"][0]["visibleCalendars"] == 1


class TestCalendarSubscriptionList:
    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_list_subscriptions(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_subscriptions.return_value = [
            {"id": "sub1", "name": "Belgian holidays", "url": "https://example.com/holidays.ics"}
        ]

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["subscription", "list"], obj=_make_ctx())
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["data"][0]["id"] == "sub1"
        assert data["data"][0]["name"] == "Belgian holidays"


class TestCalendarEventList:
    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_list_events_flattens_grouped_payload(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {
            "accounts": [
                {
                    "id": "acct1",
                    "account": "user@example.com",
                    "site": "google",
                    "calendars": [{"id": "cal1", "visible": True}],
                }
            ]
        }
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "cal1",
                    "name": "Work",
                    "color": "#123456",
                    "events": [
                        {
                            "id": "evt1",
                            "uid": "uid1",
                            "title": "Team sync",
                            "dueStart": "2026-03-24T09:00:00.000+0000",
                            "dueEnd": "2026-03-24T09:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                }
            ]
        }

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["event", "list"], obj=_make_ctx())
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["data"][0]["id"] == "evt1"
        assert data["data"][0]["calendarId"] == "cal1"
        assert data["data"][0]["calendarName"] == "Work"
        assert data["data"][0]["sourceType"] == "external"
        assert data["data"][0]["linkedTaskId"] is None

    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_list_events_filters_and_limits(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {
            "accounts": [
                {
                    "id": "acct1",
                    "account": "user@example.com",
                    "site": "google",
                    "calendars": [{"id": "cal1", "visible": True}],
                }
            ]
        }
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "cal1",
                    "name": "Work",
                    "events": [
                        {
                            "id": "evt1",
                            "title": "A",
                            "dueStart": "2026-03-24T09:00:00.000+0000",
                            "dueEnd": "2026-03-24T09:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                },
                {
                    "id": "cal2",
                    "name": "Personal",
                    "events": [
                        {
                            "id": "evt2",
                            "title": "B",
                            "dueStart": "2026-03-24T10:00:00.000+0000",
                            "dueEnd": "2026-03-24T10:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                },
            ]
        }

        runner = CliRunner()
        filtered = runner.invoke(
            calendar_group,
            ["event", "list", "--calendar-id", "cal2"],
            obj=_make_ctx(),
        )
        assert filtered.exit_code == 0
        filtered_data = json.loads(filtered.output)
        assert filtered_data["count"] == 1
        assert filtered_data["data"][0]["calendarId"] == "cal2"

        limited = runner.invoke(
            calendar_group,
            ["event", "list", "--limit", "1"],
            obj=_make_ctx(),
        )
        assert limited.exit_code == 0
        limited_data = json.loads(limited.output)
        assert limited_data["count"] == 1

    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_list_events_prefers_upcoming_before_past(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {
            "accounts": [
                {
                    "id": "acct1",
                    "account": "user@example.com",
                    "site": "google",
                    "calendars": [{"id": "cal1", "visible": True}],
                }
            ]
        }
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "cal1",
                    "name": "Mixed",
                    "events": [
                        {
                            "id": "past",
                            "title": "Past",
                            "dueStart": "2025-03-24T09:00:00.000+0000",
                            "dueEnd": "2025-03-24T09:30:00.000+0000",
                            "isAllDay": False,
                        },
                        {
                            "id": "future",
                            "title": "Future",
                            "dueStart": "2099-03-24T10:00:00.000+0000",
                            "dueEnd": "2099-03-24T10:30:00.000+0000",
                            "isAllDay": False,
                        },
                    ],
                }
            ]
        }

        runner = CliRunner()
        result = runner.invoke(
            calendar_group,
            ["event", "list", "--limit", "1"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["data"][0]["id"] == "future"

    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_list_events_infers_ticktick_source_and_linked_task(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {"accounts": []}
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "ticktick-cal",
                    "name": "TickTick",
                    "events": [
                        {
                            "id": "evt1",
                            "uid": "69bf17e6c1955180d495f7bf@calendar.ticktick.com",
                            "title": "Task-backed event",
                            "dueStart": "2099-03-24T10:00:00.000+0000",
                            "dueEnd": "2099-03-24T10:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                }
            ]
        }

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["event", "list"], obj=_make_ctx())
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["data"][0]["sourceType"] == "ticktick"
        assert data["data"][0]["linkedTaskId"] == "69bf17e6c1955180d495f7bf"

    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_list_events_marks_subscription_source(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {"accounts": []}
        client.v2.get_calendar_subscriptions.return_value = [{"id": "sub-cal", "name": "Subscribed"}]
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "sub-cal",
                    "name": "Subscribed",
                    "events": [
                        {
                            "id": "evt1",
                            "uid": "subscription@example.com",
                            "title": "Subscribed event",
                            "dueStart": "2099-03-24T10:00:00.000+0000",
                            "dueEnd": "2099-03-24T10:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                }
            ]
        }

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["event", "list"], obj=_make_ctx())
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["data"][0]["sourceType"] == "subscription"


class TestCalendarEventShow:
    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_show_event(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {"accounts": []}
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "cal1",
                    "name": "TickTick",
                    "events": [
                        {
                            "id": "evt1",
                            "uid": "69bf17e6c1955180d495f7bf@calendar.ticktick.com",
                            "title": "Task-backed event",
                            "dueStart": "2099-03-24T10:00:00.000+0000",
                            "dueEnd": "2099-03-24T10:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                }
            ]
        }

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["event", "show", "evt1"], obj=_make_ctx())
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["data"]["id"] == "evt1"
        assert data["data"]["sourceType"] == "ticktick"
        assert data["data"]["linkedTaskId"] == "69bf17e6c1955180d495f7bf"

    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_show_event_not_found(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {"accounts": []}
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {"events": []}

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["event", "show", "missing"], obj=_make_ctx())
        assert result.exit_code == 4

        data = json.loads(result.output)
        assert data["ok"] is False
        assert "Calendar event not found" in data["error"]


class TestCalendarEventTask:
    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_task_bridge_returns_linked_task(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {"accounts": []}
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "ticktick-cal",
                    "name": "TickTick",
                    "events": [
                        {
                            "id": "evt1",
                            "uid": "69bf17e6c1955180d495f7bf@calendar.ticktick.com",
                            "title": "Task-backed event",
                            "dueStart": "2099-03-24T10:00:00.000+0000",
                            "dueEnd": "2099-03-24T10:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                }
            ]
        }
        client.v2.get_task.return_value = {
            "id": "69bf17e6c1955180d495f7bf",
            "title": "Resolved task",
            "status": 0,
            "priority": 0,
            "projectId": "inbox",
        }

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["event", "task", "evt1"], obj=_make_ctx())
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["data"]["id"] == "69bf17e6c1955180d495f7bf"
        assert data["data"]["calendarEventId"] == "evt1"
        assert data["data"]["calendarEventTitle"] == "Task-backed event"
        assert data["data"]["calendarSourceType"] == "ticktick"

    @patch("ticktick_cli.commands.calendar_cmd.get_client")
    def test_task_bridge_rejects_external_event(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_calendar_third_accounts.return_value = {
            "accounts": [
                {
                    "id": "acct1",
                    "account": "user@example.com",
                    "site": "google",
                    "calendars": [{"id": "cal1", "visible": True}],
                }
            ]
        }
        client.v2.get_calendar_subscriptions.return_value = []
        client.v2.get_calendar_bound_events.return_value = {
            "events": [
                {
                    "id": "cal1",
                    "name": "Work",
                    "events": [
                        {
                            "id": "evt1",
                            "uid": "uid1",
                            "title": "External event",
                            "dueStart": "2099-03-24T10:00:00.000+0000",
                            "dueEnd": "2099-03-24T10:30:00.000+0000",
                            "isAllDay": False,
                        }
                    ],
                }
            ]
        }

        runner = CliRunner()
        result = runner.invoke(calendar_group, ["event", "task", "evt1"], obj=_make_ctx())
        assert result.exit_code == 1

        data = json.loads(result.output)
        assert data["ok"] is False
        assert "not backed by a TickTick task" in data["error"]
