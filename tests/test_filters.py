"""Tests for filter, template, and task convert commands and models."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from ticktick_cli.commands.filter_cmd import filter_group
from ticktick_cli.commands.template_cmd import template_group
from ticktick_cli.commands.task_cmd import task_group
from ticktick_cli.models.filter import Filter, FilterCondition, FilterRule
from ticktick_cli.models.template import TaskTemplate

# ── Helper ────────────────────────────────────────────────────


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


# ── FilterCondition model tests ──────────────────────────────


class TestFilterConditionModel:
    def test_defaults(self) -> None:
        c = FilterCondition(conditionName="priority")
        assert c.condition_name == "priority"
        assert c.condition_type == 1
        assert c.or_values == []

    def test_from_api(self) -> None:
        c = FilterCondition(**{"or": [5, 3], "conditionType": 1, "conditionName": "priority"})
        assert c.or_values == [5, 3]
        assert c.condition_name == "priority"

    def test_extra_fields(self) -> None:
        c = FilterCondition(conditionName="x", unknown="y")
        assert c.condition_name == "x"


# ── FilterRule model tests ────────────────────────────────────


class TestFilterRuleModel:
    def test_defaults(self) -> None:
        r = FilterRule()
        assert r.and_conditions == []
        assert r.version == 1
        assert r.type == 0

    def test_from_api(self) -> None:
        data = {
            "and": [
                {"or": [5], "conditionType": 1, "conditionName": "priority"},
                {"or": ["thisweek"], "conditionType": 1, "conditionName": "dueDate"},
            ],
            "version": 1,
            "type": 0,
        }
        r = FilterRule(**data)
        assert len(r.and_conditions) == 2
        assert r.and_conditions[0].condition_name == "priority"
        assert r.and_conditions[1].or_values == ["thisweek"]


# ── Filter model tests ────────────────────────────────────────


class TestFilterModel:
    def test_defaults(self) -> None:
        f = Filter()
        assert f.id == ""
        assert f.name == ""
        assert f.rule == ""
        assert f.etag is None

    def test_from_api(self) -> None:
        f = Filter(
            id="abc123",
            name="High Priority",
            rule='{"and":[{"or":[5],"conditionType":1,"conditionName":"priority"}],"version":1,"type":0}',
            sortType="project",
            etag="xyz",
        )
        assert f.id == "abc123"
        assert f.name == "High Priority"
        assert f.etag == "xyz"

    def test_parsed_rule(self) -> None:
        f = Filter(
            id="f1",
            name="Test",
            rule='{"and":[{"or":[5,3],"conditionType":1,"conditionName":"priority"}],"version":1,"type":0}',
        )
        rule = f.parsed_rule()
        assert rule is not None
        assert len(rule.and_conditions) == 1
        assert rule.and_conditions[0].or_values == [5, 3]

    def test_parsed_rule_empty(self) -> None:
        f = Filter(id="f2", name="Empty")
        assert f.parsed_rule() is None

    def test_parsed_rule_invalid_json(self) -> None:
        f = Filter(id="f3", name="Bad", rule="not json")
        assert f.parsed_rule() is None

    def test_to_output_basic(self) -> None:
        f = Filter(id="f4", name="My Filter", sortType="project")
        out = f.to_output()
        assert out["id"] == "f4"
        assert out["name"] == "My Filter"
        assert out["sortType"] == "project"

    def test_to_output_with_conditions(self) -> None:
        f = Filter(
            id="f5",
            name="Complex",
            rule='{"and":[{"or":[5],"conditionType":1,"conditionName":"priority"},{"or":["today"],"conditionType":1,"conditionName":"dueDate"}],"version":1,"type":0}',
            etag="etag1",
        )
        out = f.to_output()
        assert out["etag"] == "etag1"
        assert len(out["conditions"]) == 2
        assert out["conditions"][0]["field"] == "priority"
        assert out["conditions"][1]["field"] == "dueDate"
        assert out["conditions"][1]["values"] == ["today"]

    def test_extra_fields(self) -> None:
        f = Filter(id="f6", extraField="val")
        assert f.id == "f6"


# ── TaskTemplate model tests ──────────────────────────────────


class TestTaskTemplateModel:
    def test_defaults(self) -> None:
        t = TaskTemplate()
        assert t.id == ""
        assert t.title == ""
        assert t.content == ""
        assert t.items == []
        assert t.tags == []
        assert t.etag is None

    def test_from_api(self) -> None:
        t = TaskTemplate(
            id="t1",
            title="Packing List",
            items=["Passport", "Charger", "Towel"],
            tags=["travel"],
            etag="abc",
            createdTime="2023-04-11T15:04:05.000+0000",
        )
        assert t.id == "t1"
        assert t.title == "Packing List"
        assert len(t.items) == 3
        assert t.tags == ["travel"]
        assert t.etag == "abc"

    def test_to_output_basic(self) -> None:
        t = TaskTemplate(id="t2", title="Simple")
        out = t.to_output()
        assert out == {"id": "t2", "title": "Simple"}

    def test_to_output_full(self) -> None:
        t = TaskTemplate(
            id="t3",
            title="Full",
            content="Body text",
            items=["A", "B"],
            tags=["work"],
            etag="xyz",
        )
        out = t.to_output()
        assert out["content"] == "Body text"
        assert out["items"] == ["A", "B"]
        assert out["tags"] == ["work"]
        assert out["etag"] == "xyz"

    def test_extra_fields(self) -> None:
        t = TaskTemplate(id="t4", unknownField="ok")
        assert t.id == "t4"


# ── Filter CLI commands ───────────────────────────────────────


class TestFilterList:
    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_list_filters(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.sync.return_value = {
            "filters": [
                {
                    "id": "f1",
                    "name": "High Priority",
                    "rule": '{"and":[{"or":[5],"conditionType":1,"conditionName":"priority"}],"version":1,"type":0}',
                    "sortType": "project",
                },
            ],
        }
        runner = CliRunner()
        result = runner.invoke(filter_group, ["list"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 1
        assert data["data"][0]["name"] == "High Priority"

    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_list_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.sync.return_value = {"filters": None}
        runner = CliRunner()
        result = runner.invoke(filter_group, ["list"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0


class TestFilterShow:
    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_show_found(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.sync.return_value = {
            "filters": [{"id": "f1", "name": "Test", "rule": "", "sortType": "project"}],
        }
        runner = CliRunner()
        result = runner.invoke(filter_group, ["show", "f1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["name"] == "Test"

    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_show_not_found(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.sync.return_value = {"filters": []}
        runner = CliRunner()
        result = runner.invoke(filter_group, ["show", "nonexistent"], obj=_make_ctx())
        assert result.exit_code == 1


class TestFilterCreate:
    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_create_with_priority(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_filters.return_value = {"id2etag": {}, "id2error": {}}

        runner = CliRunner()
        result = runner.invoke(
            filter_group,
            ["create", "My Filter", "--priority", "high"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Filter created" in data["message"]
        client.v2.batch_filters.assert_called_once()
        call_args = client.v2.batch_filters.call_args[1]
        added = call_args["add"][0]
        assert added["name"] == "My Filter"
        rule = json.loads(added["rule"])
        assert rule["and"][0]["conditionName"] == "priority"
        assert rule["and"][0]["or"] == [5]

    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_create_with_date_and_priority(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_filters.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(
            filter_group,
            ["create", "Weekly", "-p", "high", "-p", "medium", "-d", "thisweek"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_filters.call_args[1]
        rule = json.loads(call_args["add"][0]["rule"])
        assert len(rule["and"]) == 2

    def test_create_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            filter_group,
            ["create", "Test", "-p", "high"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "filter.create"


class TestFilterEdit:
    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_edit_name(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.sync.return_value = {
            "filters": [{"id": "f1", "name": "Old", "rule": '{"and":[],"version":1,"type":0}', "sortType": "project", "etag": "e1"}],
        }
        client.v2.batch_filters.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(
            filter_group,
            ["edit", "f1", "--name", "New Name"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_filters.call_args[1]
        assert call_args["update"][0]["name"] == "New Name"
        assert call_args["update"][0]["etag"] == "e1"

    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_edit_not_found(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.sync.return_value = {"filters": []}

        runner = CliRunner()
        result = runner.invoke(
            filter_group,
            ["edit", "nonexistent", "--name", "X"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 1


class TestFilterDelete:
    @patch("ticktick_cli.commands.filter_cmd.get_client")
    def test_delete_with_yes(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_filters.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(
            filter_group,
            ["delete", "f1", "--yes"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "deleted" in data["message"]
        client.v2.batch_filters.assert_called_once_with(delete=["f1"])

    def test_delete_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            filter_group,
            ["delete", "f1"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "filter.delete"


# ── Template CLI commands ──────────────────────────────────────


class TestTemplateList:
    @patch("ticktick_cli.commands.template_cmd.get_client")
    def test_list_templates(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_templates.return_value = {
            "taskTemplates": [
                {"id": "t1", "title": "Packing", "items": ["A", "B"], "etag": "x"},
                {"id": "t2", "title": "Daily", "content": "Journal..."},
            ],
        }
        runner = CliRunner()
        result = runner.invoke(template_group, ["list"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["count"] == 2

    @patch("ticktick_cli.commands.template_cmd.get_client")
    def test_list_empty(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_templates.return_value = {"taskTemplates": []}
        runner = CliRunner()
        result = runner.invoke(template_group, ["list"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 0


class TestTemplateShow:
    @patch("ticktick_cli.commands.template_cmd.get_client")
    def test_show_found(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_templates.return_value = {
            "taskTemplates": [{"id": "t1", "title": "Test", "content": "body"}],
        }
        runner = CliRunner()
        result = runner.invoke(template_group, ["show", "t1"], obj=_make_ctx())
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["title"] == "Test"

    @patch("ticktick_cli.commands.template_cmd.get_client")
    def test_show_not_found(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_templates.return_value = {"taskTemplates": []}
        runner = CliRunner()
        result = runner.invoke(template_group, ["show", "nope"], obj=_make_ctx())
        assert result.exit_code == 1


class TestTemplateCreate:
    @patch("ticktick_cli.commands.template_cmd.get_client")
    def test_create_simple(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_templates.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(
            template_group,
            ["create", "My Template"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Template created" in data["message"]

    @patch("ticktick_cli.commands.template_cmd.get_client")
    def test_create_with_items(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_templates.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(
            template_group,
            ["create", "Checklist", "--items", "A,B,C", "-t", "work"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        call_args = client.v2.batch_templates.call_args[1]
        added = call_args["add"][0]
        assert added["items"] == ["A", "B", "C"]
        assert added["tags"] == ["work"]

    def test_create_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            template_group,
            ["create", "Test"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "template.create"


class TestTemplateDelete:
    @patch("ticktick_cli.commands.template_cmd.get_client")
    def test_delete_with_yes(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.batch_templates.return_value = {}

        runner = CliRunner()
        result = runner.invoke(
            template_group,
            ["delete", "t1", "--yes"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "deleted" in data["message"]

    def test_delete_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            template_group,
            ["delete", "t1"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


# ── Task Convert CLI command ──────────────────────────────────


class TestTaskConvert:
    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_convert_to_note(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "p1", "kind": "TEXT"}
        client.v2.batch_tasks.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["convert", "t1", "--to", "note"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "converted to note" in data["message"]
        call_args = client.v2.batch_tasks.call_args[1]
        assert call_args["update"][0]["kind"] == "NOTE"

    @patch("ticktick_cli.commands.task_cmd.get_client")
    def test_convert_to_task(self, mock_get: MagicMock) -> None:
        client = _mock_client()
        mock_get.return_value = client
        client.v2.get_task.return_value = {"id": "t1", "projectId": "p1", "kind": "NOTE"}
        client.v2.batch_tasks.return_value = {"id2etag": {}}

        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["convert", "t1", "--to", "task"],
            obj=_make_ctx(),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "converted to task" in data["message"]
        call_args = client.v2.batch_tasks.call_args[1]
        assert call_args["update"][0]["kind"] == "TEXT"

    def test_convert_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["convert", "t1", "--to", "note"],
            obj=_make_ctx(dry_run=True),
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["action"] == "task.convert"
        assert data["details"]["kind"] == "NOTE"

    def test_convert_requires_to_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            task_group,
            ["convert", "t1"],
            obj=_make_ctx(),
        )
        assert result.exit_code != 0
