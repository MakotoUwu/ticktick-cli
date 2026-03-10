"""Unified TickTick client — routes operations to V1 or V2 as appropriate.

V1 (OAuth2): tasks CRUD, projects CRUD — official, stable
V2 (Session): everything else — tags, habits, focus, kanban, subtasks, batch ops
"""

from __future__ import annotations

from typing import Any

from ticktick_cli.api.v1 import V1Client
from ticktick_cli.api.v2 import V2Client
from ticktick_cli.exceptions import AuthenticationError


class TickTickClient:
    """Unified facade over V1 and V2 APIs."""

    def __init__(
        self,
        v1_access_token: str | None = None,
        v2_cookies: dict[str, str] | None = None,
    ) -> None:
        self._v1: V1Client | None = None
        self._v2: V2Client | None = None

        if v1_access_token:
            self._v1 = V1Client(v1_access_token)
        if v2_cookies:
            self._v2 = V2Client()
            self._v2.set_session(v2_cookies)

    @property
    def v1(self) -> V1Client:
        if self._v1 is None:
            raise AuthenticationError(
                "V1 API not configured. Run `ticktick auth login` with OAuth credentials."
            )
        return self._v1

    @property
    def v2(self) -> V2Client:
        if self._v2 is None:
            raise AuthenticationError(
                "V2 API not configured. Run `ticktick auth login-v2` with username/password."
            )
        return self._v2

    @property
    def has_v1(self) -> bool:
        return self._v1 is not None

    @property
    def has_v2(self) -> bool:
        return self._v2 is not None

    def close(self) -> None:
        if self._v1:
            self._v1.close()
        if self._v2:
            self._v2.close()

    # ── Convenience: choose best API per operation ────────────

    def list_projects(self) -> list[dict[str, Any]]:
        """List projects — prefers V2 (more metadata), falls back to V1."""
        if self.has_v2:
            state = self.v2.sync()
            return state.get("projectProfiles", [])
        return self.v1.list_projects()

    def get_all_tasks(self) -> list[dict[str, Any]]:
        """Get all uncompleted tasks — V2 only (V1 requires per-project)."""
        state = self.v2.sync()
        return state.get("syncTaskBean", {}).get("update", [])

    def get_all_tags(self) -> list[dict[str, Any]]:
        """Get all tags from sync state."""
        state = self.v2.sync()
        return state.get("tags", [])

    def get_all_project_groups(self) -> list[dict[str, Any]]:
        """Get all project groups/folders from sync state."""
        state = self.v2.sync()
        return state.get("projectGroups", [])
