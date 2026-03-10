"""Test config management."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ticktick_cli.config import (
    get_config_dir,
    load_config,
    save_config,
    load_auth,
    save_auth,
    clear_auth,
)


@pytest.fixture
def temp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set XDG_CONFIG_HOME to temp dir."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


class TestConfigDir:
    def test_creates_directory(self, temp_config: Path) -> None:
        config_dir = get_config_dir("test-profile")
        assert config_dir.exists()
        assert config_dir.is_dir()
        assert "ticktick-cli" in str(config_dir)
        assert "test-profile" in str(config_dir)

    def test_default_profile(self, temp_config: Path) -> None:
        config_dir = get_config_dir()
        assert "default" in str(config_dir)


class TestConfig:
    def test_load_default_config(self, temp_config: Path) -> None:
        config = load_config("test")
        assert config["output"] == "json"
        assert config["v1_redirect_uri"] == "http://localhost:8080/callback"

    def test_save_and_load(self, temp_config: Path) -> None:
        save_config({"key": "value", "output": "human"}, "test")
        config = load_config("test")
        assert config["key"] == "value"
        assert config["output"] == "human"

    def test_merge_with_defaults(self, temp_config: Path) -> None:
        save_config({"custom_key": "custom_value"}, "test")
        config = load_config("test")
        # Should have both custom and default keys
        assert config["custom_key"] == "custom_value"
        assert "output" in config  # from defaults


class TestAuth:
    def test_load_empty_auth(self, temp_config: Path) -> None:
        auth = load_auth("test")
        assert auth == {}

    def test_save_and_load_auth(self, temp_config: Path) -> None:
        auth_data = {"v1": {"access_token": "test_token"}}
        save_auth(auth_data, "test")
        loaded = load_auth("test")
        assert loaded["v1"]["access_token"] == "test_token"

    def test_auth_file_permissions(self, temp_config: Path) -> None:
        save_auth({"v1": {"access_token": "secret"}}, "test")
        auth_path = get_config_dir("test") / "auth.json"
        mode = oct(os.stat(auth_path).st_mode)[-3:]
        assert mode == "600"

    def test_clear_auth(self, temp_config: Path) -> None:
        save_auth({"v1": {"access_token": "token"}}, "test")
        clear_auth("test")
        auth = load_auth("test")
        assert auth == {}

    def test_clear_nonexistent_auth(self, temp_config: Path) -> None:
        # Should not raise
        clear_auth("nonexistent")
