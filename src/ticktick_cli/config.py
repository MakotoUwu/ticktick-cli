"""Configuration management for TickTick CLI.

Stores config and credentials at ~/.config/ticktick-cli/ (XDG-compliant).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = {
    "default_project": None,
    "date_format": "YYYY-MM-DD",
    "output": "json",  # "json" or "human"
    "v1_client_id": None,
    "v1_client_secret": None,
    "v1_redirect_uri": "http://localhost:8080/callback",
}

_PROFILE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_profile(profile: str) -> str:
    """Validate profile name to prevent directory traversal."""
    if not _PROFILE_RE.match(profile):
        raise ValueError(
            f"Invalid profile name '{profile}'. "
            "Only letters, digits, hyphens, and underscores are allowed."
        )
    return profile


def get_config_dir(profile: str = "default") -> Path:
    """Get the config directory, creating it if needed."""
    profile = _validate_profile(profile)
    xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    config_dir = Path(xdg) / "ticktick-cli" / profile
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path(profile: str = "default") -> Path:
    """Get the config file path."""
    return get_config_dir(profile) / "config.json"


def get_auth_path(profile: str = "default") -> Path:
    """Get the auth credentials file path."""
    return get_config_dir(profile) / "auth.json"


def load_config(profile: str = "default") -> dict[str, Any]:
    """Load config, merging with defaults."""
    path = get_config_path(profile)
    config = dict(DEFAULT_CONFIG)
    if path.exists():
        with open(path) as f:
            stored = json.load(f)
        config.update(stored)
    return config


def save_config(config: dict[str, Any], profile: str = "default") -> None:
    """Save config to disk with restricted permissions (600)."""
    path = get_config_path(profile)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2)


def load_auth(profile: str = "default") -> dict[str, Any]:
    """Load stored auth credentials."""
    path = get_auth_path(profile)
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_auth(auth: dict[str, Any], profile: str = "default") -> None:
    """Save auth credentials with secure permissions (600).

    Uses os.open() with explicit mode to avoid TOCTOU race condition
    where the file is briefly world-readable before chmod.
    """
    path = get_auth_path(profile)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(auth, f, indent=2)


def clear_auth(profile: str = "default") -> None:
    """Remove stored auth credentials."""
    path = get_auth_path(profile)
    if path.exists():
        path.unlink()
