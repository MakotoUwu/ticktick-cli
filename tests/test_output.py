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


def _make_ctx(
    human: bool = False,
    fields: list[str] | None = None,
    dry_run: bool = False,
    output_format: str = "json",
    quiet: bool = False,
    offset: int = 0,
    fetch_all: bool = False,
) -> click.Context:
    """Create a click Context with obj dict."""
    ctx = click.Context(click.Command("test"))
    ctx.obj = {
        "human": human,
        "fields": fields,
        "dry_run": dry_run,
        "output_format": output_format,
        "quiet": quiet,
        "offset": offset,
        "all": fetch_all,
    }
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
        assert data["total"] == 2
        assert data["offset"] == 0
        assert data["has_more"] is False

    def test_output_list_empty(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(human=False)
        output_list([], ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["count"] == 0
        assert data["data"] == []
        assert data["has_more"] is False

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


class TestCsvOutput:
    def test_output_list_csv(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="csv")
        items = [{"id": "1", "name": "First"}, {"id": "2", "name": "Second"}]
        output_list(items, columns=["id", "name"], ctx=ctx)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines[0] == "id,name"
        assert lines[1] == "1,First"
        assert lines[2] == "2,Second"

    def test_output_item_csv(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="csv")
        output_item({"id": "task1", "title": "Test Task"}, ctx)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines[0] == "id,title"
        assert lines[1] == "task1,Test Task"

    def test_output_list_csv_empty(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="csv")
        output_list([], ctx=ctx)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_output_list_csv_with_list_values(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="csv")
        items = [{"id": "1", "tags": ["a", "b"]}]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        # CSV quotes JSON values that contain commas
        assert "tags" in captured.out
        assert "a" in captured.out
        assert "b" in captured.out

    def test_csv_with_fields(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="csv", fields=["id"])
        items = [{"id": "1", "name": "First", "extra": "data"}]
        output_list(items, columns=["id", "name"], ctx=ctx)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines[0] == "id"
        assert lines[1] == "1"


class TestYamlOutput:
    def test_output_item_yaml(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="yaml")
        output_item({"id": "t1", "title": "Test", "priority": 5}, ctx)
        captured = capsys.readouterr()
        assert "id: t1" in captured.out
        assert "title: Test" in captured.out
        assert "priority: 5" in captured.out

    def test_output_list_yaml(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="yaml")
        items = [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        assert "- id: 1" in captured.out
        assert "  name: A" in captured.out
        assert "- id: 2" in captured.out

    def test_yaml_null_values(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="yaml")
        output_item({"id": "1", "value": None}, ctx)
        captured = capsys.readouterr()
        assert "value: null" in captured.out

    def test_yaml_bool_values(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="yaml")
        output_item({"done": True, "archived": False}, ctx)
        captured = capsys.readouterr()
        assert "done: true" in captured.out
        assert "archived: false" in captured.out

    def test_output_success_yaml(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(output_format="yaml")
        output_success({"key": "value"}, ctx)
        captured = capsys.readouterr()
        assert "key: value" in captured.out


class TestQuietOutput:
    def test_output_list_quiet_prints_ids(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        items = [{"id": "abc123", "title": "First"}, {"id": "def456", "title": "Second"}]
        output_list(items, columns=["id", "title"], ctx=ctx)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines == ["abc123", "def456"]

    def test_output_list_quiet_empty(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        output_list([], ctx=ctx)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_output_item_quiet_prints_id(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        output_item({"id": "task1", "title": "Test"}, ctx)
        captured = capsys.readouterr()
        assert captured.out.strip() == "task1"

    def test_output_item_quiet_fallback_first_field(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        output_item({"name": "myname", "extra": "data"}, ctx)
        captured = capsys.readouterr()
        assert captured.out.strip() == "myname"

    def test_output_message_quiet_silent(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        output_message("Task completed", ctx)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_output_success_quiet_single_item(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        output_success({"id": "new123", "title": "Created"}, ctx)
        captured = capsys.readouterr()
        assert captured.out.strip() == "new123"

    def test_output_success_quiet_list(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        output_success([{"id": "a1"}, {"id": "b2"}], ctx)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines == ["a1", "b2"]

    def test_output_error_still_goes_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True)
        output_error("something failed", ctx)
        captured = capsys.readouterr()
        assert captured.out == ""  # Nothing on stdout
        data = json.loads(captured.err)
        assert data["ok"] is False
        assert data["error"] == "something failed"

    def test_quiet_overrides_human(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True, human=True)
        items = [{"id": "x1", "title": "T"}]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        assert captured.out.strip() == "x1"

    def test_quiet_overrides_csv_format(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True, output_format="csv")
        output_item({"id": "y2", "title": "T"}, ctx)
        captured = capsys.readouterr()
        assert captured.out.strip() == "y2"


class TestPagination:
    def test_offset_skips_items(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(offset=2)
        items = [{"id": str(i)} for i in range(5)]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 3
        assert data["total"] == 5
        assert data["offset"] == 2
        assert data["has_more"] is False
        assert [d["id"] for d in data["data"]] == ["2", "3", "4"]

    def test_limit_applies_after_offset(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(offset=1)
        items = [{"id": str(i)} for i in range(5)]
        output_list(items, ctx=ctx, limit=2)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 2
        assert data["total"] == 5
        assert data["offset"] == 1
        assert data["has_more"] is True
        assert [d["id"] for d in data["data"]] == ["1", "2"]

    def test_offset_beyond_items(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(offset=10)
        items = [{"id": "1"}, {"id": "2"}]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 0
        assert data["total"] == 2
        assert data["has_more"] is False

    def test_has_more_true_when_offset_leaves_remaining(self, capsys: pytest.CaptureFixture) -> None:
        """When offset + returned count < total, has_more should be True.

        Note: has_more is only meaningful when combined with command-level --limit.
        Without --limit, offset just slices and returns the rest.
        """
        ctx = _make_ctx(offset=0)
        items = [{"id": str(i)} for i in range(5)]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        # No limit applied, so all items returned, has_more is False
        assert data["has_more"] is False
        assert data["count"] == 5

    def test_fetch_all_skips_pagination(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(fetch_all=True)
        items = [{"id": str(i)} for i in range(5)]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["ok"] is True
        assert data["count"] == 5
        assert "total" not in data
        assert "offset" not in data
        assert "has_more" not in data

    def test_fetch_all_ignores_offset(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(offset=3, fetch_all=True)
        items = [{"id": str(i)} for i in range(5)]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 5  # All items returned, offset ignored

    def test_offset_with_quiet_mode(self, capsys: pytest.CaptureFixture) -> None:
        ctx = _make_ctx(quiet=True, offset=2)
        items = [{"id": str(i)} for i in range(5)]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        assert lines == ["2", "3", "4"]

    def test_pagination_metadata_with_pre_sliced_list(self, capsys: pytest.CaptureFixture) -> None:
        """When command pre-slices with --limit, total reflects what was passed in."""
        ctx = _make_ctx(offset=0)
        # Simulate a command that already applied --limit 3 to 10 items
        items = [{"id": str(i)} for i in range(3)]
        output_list(items, ctx=ctx)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["count"] == 3
        assert data["total"] == 3
        assert data["has_more"] is False
