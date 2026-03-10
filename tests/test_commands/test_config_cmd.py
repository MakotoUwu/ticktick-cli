"""Test config CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from ticktick_cli.cli import cli


@pytest.fixture
def temp_config_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set XDG_CONFIG_HOME for config command tests."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


class TestConfigSet:
    def test_set_string(self, runner: CliRunner, temp_config_env: Path) -> None:
        result = runner.invoke(cli, ["config", "set", "key1", "value1"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert "key1" in data["message"]

    def test_set_boolean(self, runner: CliRunner, temp_config_env: Path) -> None:
        result = runner.invoke(cli, ["config", "set", "flag", "true"])
        assert result.exit_code == 0


class TestConfigGet:
    def test_get_existing_key(self, runner: CliRunner, temp_config_env: Path) -> None:
        # Set first
        runner.invoke(cli, ["config", "set", "mykey", "myval"])
        # Then get
        result = runner.invoke(cli, ["config", "get", "mykey"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["value"] == "myval"

    def test_get_missing_key(self, runner: CliRunner, temp_config_env: Path) -> None:
        result = runner.invoke(cli, ["config", "get", "nonexistent"])
        assert result.exit_code != 0


class TestConfigList:
    def test_list_config(self, runner: CliRunner, temp_config_env: Path) -> None:
        result = runner.invoke(cli, ["config", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True


class TestConfigPath:
    def test_config_path(self, runner: CliRunner, temp_config_env: Path) -> None:
        result = runner.invoke(cli, ["config", "path"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "config_dir" in data["data"]
        assert "ticktick-cli" in data["data"]["config_dir"]
