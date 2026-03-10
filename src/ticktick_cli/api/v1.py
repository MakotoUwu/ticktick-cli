"""TickTick V1 (Official) API Client.

Base URL: https://api.ticktick.com/open/v1
Auth: OAuth 2.0 Bearer token
Endpoints: tasks, projects (documented, stable)
"""

from __future__ import annotations

from typing import Any

from ticktick_cli.api.base import BaseClient

V1_BASE = "https://api.ticktick.com/open/v1"


class V1Client(BaseClient):
    """Official TickTick Open API v1 client."""

    def __init__(self, access_token: str) -> None:
        super().__init__(V1_BASE)
        self._access_token = access_token

    def _get_auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    # ── Projects ──────────────────────────────────────────────

    def list_projects(self) -> list[dict[str, Any]]:
        return self.get("/project")

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self.get(f"/project/{project_id}")

    def get_project_with_data(self, project_id: str) -> dict[str, Any]:
        """Project with its tasks and kanban columns."""
        return self.get(f"/project/{project_id}/data")

    def create_project(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.post("/project", json_data=data)

    def update_project(self, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self.post(f"/project/{project_id}", json_data=data)

    def delete_project(self, project_id: str) -> Any:
        return self.delete(f"/project/{project_id}")

    # ── Tasks ─────────────────────────────────────────────────

    def create_task(self, data: dict[str, Any]) -> dict[str, Any]:
        return self.post("/task", json_data=data)

    def get_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        return self.get(f"/project/{project_id}/task/{task_id}")

    def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self.post(f"/task/{task_id}", json_data=data)

    def complete_task(self, project_id: str, task_id: str) -> Any:
        return self.post(f"/project/{project_id}/task/{task_id}/complete")

    def delete_task(self, project_id: str, task_id: str) -> Any:
        return self.delete(f"/project/{project_id}/task/{task_id}")
