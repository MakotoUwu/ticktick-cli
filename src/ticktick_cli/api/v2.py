"""TickTick V2 (Unofficial) API Client.

Base URL: https://api.ticktick.com/api/v2
Auth: Session-based (cookie from /user/signon)
Endpoints: everything the web app uses — tasks, projects, tags, habits, focus, etc.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime
from typing import Any

from ticktick_cli.api.base import BaseClient

V2_BASE = "https://api.ticktick.com/api/v2"

# Minimal headers that make V2 API work (from pyticktick)
V2_USER_AGENT = "Mozilla/5.0 (rv:145.0) Firefox/145.0"
V2_DEVICE_VERSION = 6430


def _generate_object_id() -> str:
    """Generate a MongoDB-style ObjectId (24 hex chars) like the web app uses."""
    timestamp = int(time.time()).to_bytes(4, "big")
    random_bytes = os.urandom(5)
    counter = os.urandom(3)
    return (timestamp + random_bytes + counter).hex()


class V2Client(BaseClient):
    """Unofficial TickTick V2 API client — full feature set."""

    def __init__(self) -> None:
        super().__init__(V2_BASE)
        self._cookies: dict[str, str] = {}
        self._device_id = _generate_object_id()

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        """Login with username/password, stores session cookie."""
        payload = {"username": username, "password": password}
        params = {"wc": "true", "remember": "true"}
        headers = self._get_auth_headers()

        response = self._http.post(
            "/user/signon",
            params=params,
            json=payload,
            headers=headers,
        )

        if response.status_code == 200:
            # Extract cookies from response
            for name, value in response.cookies.items():
                self._cookies[name] = value
            data = response.json()
            # Also store token as cookie (required by V2 API for subsequent requests)
            if "t" not in self._cookies and "token" in data:
                self._cookies["t"] = data["token"]
            return data
        elif response.status_code == 401:
            from ticktick_cli.exceptions import AuthenticationError
            raise AuthenticationError("Invalid username or password.")
        else:
            from ticktick_cli.exceptions import APIError
            raise APIError(
                f"Login failed ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )

    def set_session(self, cookies: dict[str, str]) -> None:
        """Restore session from stored cookies."""
        self._cookies = cookies

    def get_session_cookies(self) -> dict[str, str]:
        """Get current session cookies for storage."""
        return dict(self._cookies)

    def _get_auth_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": V2_USER_AGENT,
            "X-Device": json.dumps({
                "platform": "web",
                "version": V2_DEVICE_VERSION,
                "id": self._device_id,
            }),
        }
        if self._cookies:
            cookie_str = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
            headers["Cookie"] = cookie_str
        return headers

    # ── Sync ──────────────────────────────────────────────────

    def sync(self) -> dict[str, Any]:
        """Get complete account state (all tasks, projects, tags, etc.)."""
        return self.get("/batch/check/0")

    # ── User ──────────────────────────────────────────────────

    def get_user_status(self) -> dict[str, Any]:
        return self.get("/user/status")

    def get_user_profile(self) -> dict[str, Any]:
        return self.get("/user/profile")

    def get_user_preferences(self) -> dict[str, Any]:
        return self.get("/user/preferences/settings", params={"includeWeb": "true"})

    def get_user_statistics(self) -> dict[str, Any]:
        return self.get("/statistics/general")

    # ── Tasks (batch) ─────────────────────────────────────────

    def batch_tasks(
        self,
        add: list[dict] | None = None,
        update: list[dict] | None = None,
        delete: list[dict] | None = None,
    ) -> dict[str, Any]:
        data = {
            "add": add or [],
            "update": update or [],
            "delete": delete or [],
            "addAttachments": [],
            "updateAttachments": [],
            "deleteAttachments": [],
        }
        return self.post("/batch/task", json_data=data)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.get(f"/task/{task_id}")

    def move_tasks(self, moves: list[dict]) -> Any:
        """Move tasks between projects. Each: {taskId, fromProjectId, toProjectId}."""
        return self.post("/batch/taskProject", json_data=moves)

    def set_task_parent(self, task_id: str, project_id: str, parent_id: str) -> Any:
        data = [{"taskId": task_id, "projectId": project_id, "parentId": parent_id}]
        return self.post("/batch/taskParent", json_data=data)

    def unset_task_parent(
        self, task_id: str, project_id: str, old_parent_id: str
    ) -> Any:
        data = [
            {"taskId": task_id, "projectId": project_id, "oldParentId": old_parent_id}
        ]
        return self.post("/batch/taskParent", json_data=data)

    def get_completed_tasks(
        self,
        from_date: datetime,
        to_date: datetime,
        limit: int = 100,
    ) -> list[dict]:
        params = {
            "from": from_date.strftime("%Y-%m-%d %H:%M:%S"),
            "to": to_date.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Completed",
            "limit": str(limit),
        }
        return self.get("/project/all/closed", params=params)

    def get_deleted_tasks(self, start: int = 0, limit: int = 500) -> dict[str, Any]:
        params = {"start": str(start), "limit": str(limit)}
        return self.get("/project/all/trash/pagination", params=params)

    # ── Projects (batch) ──────────────────────────────────────

    def batch_projects(
        self,
        add: list[dict] | None = None,
        update: list[dict] | None = None,
        delete: list[str] | None = None,
    ) -> dict[str, Any]:
        data = {"add": add or [], "update": update or [], "delete": delete or []}
        return self.post("/batch/project", json_data=data)

    # ── Project Groups / Folders ──────────────────────────────

    def batch_project_groups(
        self,
        add: list[dict] | None = None,
        update: list[dict] | None = None,
        delete: list[str] | None = None,
    ) -> dict[str, Any]:
        data = {"add": add or [], "update": update or [], "delete": delete or []}
        return self.post("/batch/projectGroup", json_data=data)

    # ── Kanban Columns ────────────────────────────────────────

    def get_columns(self, project_id: str) -> list[dict]:
        return self.get(f"/column/project/{project_id}")

    def batch_columns(
        self,
        add: list[dict] | None = None,
        update: list[dict] | None = None,
        delete: list[dict] | None = None,
    ) -> dict[str, Any]:
        data = {"add": add or [], "update": update or [], "delete": delete or []}
        return self.post("/column", json_data=data)

    # ── Tags ──────────────────────────────────────────────────

    def batch_tags(
        self,
        add: list[dict] | None = None,
        update: list[dict] | None = None,
    ) -> dict[str, Any]:
        data = {"add": add or [], "update": update or []}
        return self.post("/batch/tag", json_data=data)

    def rename_tag(self, old_name: str, new_name: str) -> Any:
        return self.put("/tag/rename", json_data={"name": old_name, "newName": new_name})

    def delete_tag(self, name: str) -> Any:
        return self.delete("/tag", params={"name": name})

    def merge_tags(self, source: str, target: str) -> Any:
        return self.put("/tag/merge", json_data={"name": source, "newName": target})

    # ── Focus / Pomodoro ──────────────────────────────────────

    def get_focus_heatmap(self, start: date, end: date) -> list[dict]:
        s = start.strftime("%Y%m%d")
        e = end.strftime("%Y%m%d")
        return self.get(f"/pomodoros/statistics/heatmap/{s}/{e}")

    def get_focus_by_tag(self, start: date, end: date) -> dict[str, Any]:
        s = start.strftime("%Y%m%d")
        e = end.strftime("%Y%m%d")
        return self.get(f"/pomodoros/statistics/dist/{s}/{e}")

    # ── Habits ────────────────────────────────────────────────

    def get_habits(self) -> list[dict]:
        return self.get("/habits")

    def get_habit_sections(self) -> list[dict]:
        return self.get("/habitSections")

    def get_habit_preferences(self) -> dict[str, Any]:
        return self.get("/user/preferences/habit", params={"platform": "web"})

    def batch_habits(
        self,
        add: list[dict] | None = None,
        update: list[dict] | None = None,
        delete: list[str] | None = None,
    ) -> dict[str, Any]:
        data = {"add": add or [], "update": update or [], "delete": delete or []}
        return self.post("/habits/batch", json_data=data)

    def query_habit_checkins(
        self, habit_ids: list[str], after_stamp: int = 0
    ) -> dict[str, Any]:
        data = {"habitIds": habit_ids, "afterStamp": after_stamp}
        return self.post("/habitCheckins/query", json_data=data)

    def batch_habit_checkins(
        self,
        add: list[dict] | None = None,
        update: list[dict] | None = None,
        delete: list[str] | None = None,
    ) -> dict[str, Any]:
        data = {"add": add or [], "update": update or [], "delete": delete or []}
        return self.post("/habitCheckins/batch", json_data=data)
