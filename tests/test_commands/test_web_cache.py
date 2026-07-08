"""Tests for read-only TickTick web-cache audits."""

from __future__ import annotations

import json

from click.testing import CliRunner

from ticktick_cli.cli import cli


def test_web_cache_audit_filters_north_star_group(runner: CliRunner, tmp_path) -> None:
    snapshot = {
        "projectGroups": [{"id": "north-star", "name": "North Star"}],
        "projects": [
            {"id": "founder", "name": "Founder Focus", "groupId": "north-star"},
            {"id": "projects", "name": "Projects", "groupId": "north-star"},
            {"id": "life", "name": "Life"},
        ],
        "columns": [
            {"id": "today-top-3", "name": "Today - Top 3", "projectId": "founder"},
            {"id": "speakers", "name": "Speakers", "projectId": "projects"},
        ],
        "tasks": [
            {
                "id": "today-task",
                "title": "Close Imec follow-up",
                "projectId": "founder",
                "columnId": "today-top-3",
                "status": 0,
                "priority": 5,
                "dueDate": "2026-07-08T00:00:00.000+0000",
            },
            {
                "id": "overdue-task",
                "title": "Send Noah video",
                "projectId": "founder",
                "columnId": "today-top-3",
                "status": 0,
                "priority": 3,
                "dueDate": "2026-07-01T00:00:00.000+0000",
            },
            {
                "id": "no-date-task",
                "title": "Create HackNation marketing calendar",
                "projectId": "projects",
                "columnId": "speakers",
                "status": 0,
                "priority": 1,
            },
            {
                "id": "completed-task",
                "title": "Post Codex video",
                "projectId": "founder",
                "status": 2,
                "completedTime": "2026-07-07T10:00:00.000+0000",
            },
            {
                "id": "life-task",
                "title": "Buy groceries",
                "projectId": "life",
                "status": 0,
                "dueDate": "2026-07-08T00:00:00.000+0000",
            },
        ],
    }
    snapshot_path = tmp_path / "ticktick-web-cache.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "web-cache",
            "audit",
            "--file",
            str(snapshot_path),
            "--today",
            "2026-07-08",
            "--group",
            "North Star",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.output)["data"]
    assert data["read_only"] is True
    assert data["group_filter_matched"] is True
    assert data["totals"] == {
        "tasks": 4,
        "active": 3,
        "completed_recent": 1,
        "today": 1,
        "overdue": 1,
        "future": 0,
        "no_date": 1,
        "high_or_medium_priority": 2,
    }
    assert data["samples"]["today"][0]["title"] == "Close Imec follow-up"
    assert data["samples"]["today"][0]["group"] == "North Star"
    assert data["projects"][0]["name"] == "Founder Focus"
    assert data["columns"][0]["name"] == "Today - Top 3"


def test_web_cache_audit_reports_invalid_date(runner: CliRunner, tmp_path) -> None:
    snapshot_path = tmp_path / "ticktick-web-cache.json"
    snapshot_path.write_text(json.dumps({"tasks": []}), encoding="utf-8")

    result = runner.invoke(
        cli,
        ["web-cache", "audit", "--file", str(snapshot_path), "--today", "08-07-2026"],
    )

    assert result.exit_code == 2
    data = json.loads(result.stderr)
    assert data["ok"] is False
    assert data["exit_code"] == 2
    assert "Expected YYYY-MM-DD" in data["error"]
