"""Project model — Pydantic v2."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProjectKind(str, Enum):
    """Project kind/type."""

    TASK = "TASK"
    NOTE = "NOTE"


class ProjectViewMode(str, Enum):
    """Project view mode."""

    LIST = "list"
    KANBAN = "kanban"
    TIMELINE = "timeline"


class Project(BaseModel):
    """Represents a TickTick project (list)."""

    id: str = ""
    name: str = ""
    color: str | None = None
    kind: str | None = None
    view_mode: str | None = Field(default=None, alias="viewMode")
    group_id: str | None = Field(default=None, alias="groupId")
    sort_order: int = Field(default=0, alias="sortOrder")
    is_owner: bool = Field(default=True, alias="isOwner")
    closed: bool | None = None
    in_all: bool = Field(default=True, alias="inAll")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_output(self) -> dict[str, Any]:
        """Serialize for CLI output."""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color or "",
            "kind": self.kind or "TASK",
            "viewMode": self.view_mode or "list",
            "groupId": self.group_id or "",
            "closed": self.closed,
        }
