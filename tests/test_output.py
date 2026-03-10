"""Test output formatting layer."""

from __future__ import annotations

import json

import click
import pytest

from ticktick_cli.output import (
    output_success,
    output_error,
    output_list,
    output_item,
    output_message,
)


def _make_ctx(human: bool = False) -> click.Context:
    """Create a click Context with obj dict."""
    ctx = click.Context(click.Command("test"))
    ctx.obj = {"human": human}
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
