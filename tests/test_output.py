"""Test output formatting layer."""

from __future__ import annotations

import json

import click
import pytest

from ticktick_cli.output import (
    is_dry_run,
    output_dry_run,
    output_error,
    output_item,
    output_list,
    output_message,
    output_success,
)


def _make_ctx(human: bool = False, fields: list[str] | None = None, dry_run: bool = False) -> click.Context:
    """Create a click Context with obj dict."""
    ctx = click.Context(click.Command("test"))
    ctx.obj = {"human": human, "fields": fields, "dry_run": dry_run}
    return ctx


class TestJsonOutput:
    def test_output_success(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=False)
        output_success({"key": "value"}, ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"]["key"] == "value"

    def test_output_error(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=False)
        output_error("something failed", ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.err)
        assert data["ok"] is False
        assert data["error"] == "something failed"

    def test_output_list(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=False)
        items = [{"id": "1", "name": "First"}, {"id": "2", "name": "Second"}]
        output_list(items, columns=["id", "name"], ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["count"] == 2
        assert len(data["data"]) == 2

    def test_output_list_empty(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=False)
        output_list([], ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["count"] == 0
        assert data["data"] == []

    def test_output_item(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=False)
        output_item({"id": "task1", "title": "Test"}, ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["data"]["id"] == "task1"

    def test_output_message(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=False)
        output_message("Task created", ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["message"] == "Task created"


class TestHumanOutput:
    def test_output_list_human(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=True)
        items = [{"id": "1", "name": "First"}]
        output_list(items, columns=["id", "name"], title="Test", ctx=ctx)
        captured = capsys.readouterr()
        assert "First" in captured.out
        assert "Test" in captured.out

    def test_output_item_human(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=True)
        output_item({"id": "task1", "title": "Test"}, ctx)
        captured = capsys.readouterr()
        assert "task1" in captured.out
        assert "Test" in captured.out

    def test_output_message_human(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=True)
        output_message("Done!", ctx)
        captured = capsys.readouterr()
        assert "Done!" in captured.out

    def test_output_empty_list_human(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=True)
        output_list([], ctx=ctx)
        captured = capsys.readouterr()
        assert "No results" in captured.out


class TestFieldsFilter:
    def test_fields_filter_item(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(fields=["id", "title"])
        output_item({"id": "1", "title": "Test", "priority": "high", "tags": []}, ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert set(data["data"].keys()) == {"id", "title"}

    def test_fields_filter_list(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(fields=["id", "name"])
        items = [{"id": "1", "name": "First", "color": "red"}, {"id": "2", "name": "Second", "color": "blue"}]
        output_list(items, columns=["id", "name", "color"], ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        for item in data["data"]:
            assert set(item.keys()) == {"id", "name"}

    def test_fields_filter_success(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(fields=["id"])
        output_success({"id": "1", "title": "Test", "extra": "data"}, ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert set(data["data"].keys()) == {"id"}

    def test_no_fields_passes_everything(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(fields=None)
        output_item({"id": "1", "title": "Test", "priority": "high"}, ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert set(data["data"].keys()) == {"id", "title", "priority"}


class TestDryRun:
    def test_is_dry_run_true(self) -> None:
        ctx = _make_ctx(dry_run=True)
        assert is_dry_run(ctx) is True

    def test_is_dry_run_false(self) -> None:
        ctx = _make_ctx(dry_run=False)
        assert is_dry_run(ctx) is False

    def test_is_dry_run_none_ctx(self) -> None:
        assert is_dry_run(None) is False

    def test_output_dry_run_json(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx()
        output_dry_run("task.add", {"title": "Test", "priority": 0}, ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["dry_run"] is True
        assert data["action"] == "task.add"
        assert data["details"]["title"] == "Test"

    def test_output_dry_run_no_details(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx()
        output_dry_run("task.delete", ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["dry_run"] is True
        assert "details" not in data
