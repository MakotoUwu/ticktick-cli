"""Tests for task comments, activities, and duplicate commands and models."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.commands.task_cmd import task_group
from ticktick_cli.models.comment import Activity, Comment, UserProfile

# ── UserProfile model tests ──────────────────────────────────


class TestUserProfileModel:
    def test_defaults(self) -> None:
        u = UserProfile()
        assert u.is_myself is False
        assert u.name is None

    def test_from_api(self) -> None:
        u = UserProfile(**{"isMyself": True, "name": "Alice"})
        assert u.is_myself is True
        assert u.name == "Alice"

    def test_extra_fields_allowed(self) -> None:
        u = UserProfile(**{"isMyself": False, "avatar": "http://img.png"})
        assert u.is_myself is False


# ── Comment model tests ──────────────────────────────────────


class TestCommentModel:
    def test_defaults(self) -> None:
        c = Comment()
        assert c.id == ""
        assert c.title == ""
        assert c.created_time == ""
        assert c.user_profile is None
        assert c.mentions == []
        assert c.attachments == []

    def test_from_api(self) -> None:
        data = {
            "id": "comment1",
            "title": "This is a comment",
            "createdTime": "2026-03-12T10:00:00.000+0000",
            "modifiedTime": "2026-03-12T10:05:00.000+0000",
            "userProfile": {"isMyself": True, "name": "Bob"},
        }
        c = Comment(**data)
        assert c.id == "comment1"
        assert c.title == "This is a comment"
        assert c.created_time == "2026-03-12T10:00:00.000+0000"
        assert c.modified_time == "2026-03-12T10:05:00.000+0000"
        assert c.user_profile is not None
        assert c.user_profile.is_myself is True
        assert c.user_profile.name == "Bob"

    def test_to_output_basic(self) -> None:
        c = Comment(id="c1", title="hello", createdTime="2026-01-01T00:00:00.000+0000")
        out = c.to_output()
        assert out["id"] == "c1"
        assert out["title"] == "hello"
        assert out["createdTime"] == "2026-01-01T00:00:00.000+0000"
        assert "isMyself" not in out
        assert "author" not in out
        assert "replyTo" not in out

    def test_to_output_with_user(self) -> None:
        c = Comment(
            id="c2",
            title="noted",
            createdTime="2026-01-01",
            userProfile={"isMyself": True, "name": "Alice"},
        )
        out = c.to_output()
        assert out["isMyself"] is True
        assert out["author"] == "Alice"

    def test_to_output_with_reply(self) -> None:
        c = Comment(id="c3", title="reply", createdTime="", replyCommentId="c1")
        out = c.to_output()
        assert out["replyTo"] == "c1"

    def test_to_output_user_no_name(self) -> None:
        c = Comment(
            id="c4",
            title="x",
            createdTime="",
            userProfile={"isMyself": False},
        )
        out = c.to_output()
        assert out["isMyself"] is False
        assert "author" not in out

    def test_extra_fields_allowed(self) -> None:
        c = Comment(id="c5", unknownField="val")
        assert c.id == "c5"


# ── Activity model tests ─────────────────────────────────────


class TestActivityModel:
    def test_defaults(self) -> None:
        a = Activity()
        assert a.id == ""
        assert a.action == ""
        assert a.when == ""
        assert a.device_channel is None
        assert a.start_date is None

    def test_from_api(self) -> None:
        data = {
            "id": "act1",
            "action": "update",
            "when": "2026-03-12T10:00:00.000+0000",
            "deviceChannel": "web",
            "startDate": "2026-03-15T00:00:00.000+0000",
            "startDateBefore": "2026-03-14T00:00:00.000+0000",
        }
        a = Activity(**data)
        assert a.id == "act1"
        assert a.action == "update"
        assert a.device_channel == "web"
        assert a.start_date == "2026-03-15T00:00:00.000+0000"
        assert a.start_date_before == "2026-03-14T00:00:00.000+0000"

    def test_to_output_minimal(self) -> None:
        a = Activity(id="a1", action="create", when="2026-01-01")
        out = a.to_output()
        assert out == {"id": "a1", "action": "create", "when": "2026-01-01"}

    def test_to_output_with_device(self) -> None:
        a = Activity(id="a2", action="update", when="t", deviceChannel="android")
        out = a.to_output()
        assert out["device"] == "android"

    def test_to_output_with_dates(self) -> None:
        a = Activity(
            id="a3",
            action="update",
            when="t",
            startDate="2026-03-15",
            startDateBefore="2026-03-14",
            dueDate="2026-04-01",
            dueDateBefore="2026-03-31",
        )
        out = a.to_output()
        assert out["startDate"] == "2026-03-15"
        assert out["startDateBefore"] == "2026-03-14"
        assert out["dueDate"] == "2026-04-01"
        assert out["dueDateBefore"] == "2026-03-31"

    def test_extra_fields_allowed(self) -> None:
        a = Activity(id="a4", extraField="abc")
        assert a.id == "a4"


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
    client.has_v2 = True
    client.has_v1 = False
    return client


class TestCommentList:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_list_with_auto_project(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_task.return_value = {"projectId": "proj1"}
        client.v2.get_task_comments.return_value = [
            {
                "id": "c1",
                "title": "First comment",
                "createdTime": "2026-03-12T10:00:00.000+0000",
            },
            {
                "id": "c2",
                "title": "Second",
                "createdTime": "2026-03-12T11:00:00.000+0000",
            },
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["comment", "list", "task1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["data"][0]["title"] == "First comment"
        client.v2.get_task.assert_called_once_with("task1")
        client.v2.get_task_comments.assert_called_once_with("proj1", "task1")

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_list_with_explicit_project(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_task_comments.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["comment", "list", "task1", "--project", "proj99"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0
        client.v2.get_task.assert_not_called()
        client.v2.get_task_comments.assert_called_once_with("proj99", "task1")


class TestCommentAdd:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_add_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_task.return_value = {"projectId": "proj1"}
        client.v2.create_task_comment.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["comment", "add", "task1", "Hello world"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["message"] == "Comment added."
        client.v2.create_task_comment.assert_called_once_with("proj1", "task1", "Hello world")

    def test_add_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["comment", "add", "task1", "test comment"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.comment.add"


class TestCommentDelete:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_delete_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_task.return_value = {"projectId": "proj1"}
        client.v2.delete_task_comment.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["comment", "delete", "task1", "comment1"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["message"] == "Comment deleted."
        client.v2.delete_task_comment.assert_called_once_with("proj1", "task1", "comment1")

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_delete_with_explicit_project(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.delete_task_comment.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["comment", "delete", "task1", "comment1", "--project", "proj99"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        client.v2.get_task.assert_not_called()
        client.v2.delete_task_comment.assert_called_once_with("proj99", "task1", "comment1")

    def test_delete_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["comment", "delete", "task1", "comment1"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.comment.delete"


class TestTaskActivity:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_activity_list(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_task_activities.return_value = [
            {
                "id": "act1",
                "action": "create",
                "when": "2026-03-12T08:00:00.000+0000",
                "deviceChannel": "web",
            },
            {
                "id": "act2",
                "action": "update",
                "when": "2026-03-12T09:00:00.000+0000",
                "startDate": "2026-03-15",
            },
        ]

        runner = CliRunner()
        result = runner.invoke(task_group, ["activity", "task123"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2
        assert data["data"][0]["action"] == "create"
        assert data["data"][0]["device"] == "web"
        assert data["data"][1]["startDate"] == "2026-03-15"
        client.v2.get_task_activities.assert_called_once_with("task123")

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_activity_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_task_activities.return_value = []

        runner = CliRunner()
        result = runner.invoke(task_group, ["activity", "task123"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0


class TestTaskDuplicate:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_duplicate_success(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client

        client.v2.get_task.return_value = {
            "id": "orig1",
            "title": "My Task",
            "projectId": "proj1",
            "etag": "abc",
            "sortOrder": 100,
            "modifiedTime": "2026-03-12T00:00:00.000+0000",
            "createdTime": "2026-03-10T00:00:00.000+0000",
        }
        client.v2.batch_tasks.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(task_group, ["duplicate", "orig1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Task duplicated" in data["message"]

        # Verify batch_tasks was called with the right shape
        call_args = client.v2.batch_tasks.call_args
        added = call_args[1]["add"][0]
        assert added["title"] == "My Task (copy)"
        assert added["id"] != "orig1"
        assert len(added["id"]) == 24
        assert "etag" not in added
        assert "sortOrder" not in added
        assert "modifiedTime" not in added
        assert "createdTime" not in added
        assert added["projectId"] == "proj1"

    def test_duplicate_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            task_group, ["duplicate", "orig1"], obj=_make_ctx(dry_run=True)
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.duplicate"
