"""Test schema introspection command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from ticktick_cli.cli import cli


class TestSchemaCommand:
    def test_schema_outputs_json(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["schema"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["name"] == "ticktick"
        assert "version" in data["data"]

    def test_schema_has_global_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["schema"])
        data = json.loads(result.output)
        global_opts = data["data"]["global_options"]
        opt_names = [o["name"] for o in global_opts]
        assert "human" in opt_names
        assert "fields" in opt_names
        assert "dry_run" in opt_names
        assert "output_format" in opt_names

    def test_schema_has_commands(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["schema"])
        data = json.loads(result.output)
        commands = data["data"]["commands"]
        cmd_names = [c["command"] for c in commands]
        # Should have task subcommands
        assert any("task add" in c for c in cmd_names)
        assert any("task list" in c for c in cmd_names)
        assert any("project list" in c for c in cmd_names)
        assert any("habit list" in c for c in cmd_names)

    def test_schema_command_has_params(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["schema"])
        data = json.loads(result.output)
        commands = data["data"]["commands"]
        # Find 'task add' — should have params
        task_add = next(c for c in commands if c["command"].endswith("task add"))
        assert "params" in task_add
        param_names = [p["name"] for p in task_add["params"]]
        assert "title" in param_names
        assert "priority" in param_names

    def test_schema_shows_choices(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["schema"])
        data = json.loads(result.output)
        commands = data["data"]["commands"]
        task_add = next(c for c in commands if c["command"].endswith("task add"))
        priority_param = next(p for p in task_add["params"] if p["name"] == "priority")
        assert "choices" in priority_param
        assert "high" in priority_param["choices"]
