"""Task model — Pydantic v2."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskPriority(IntEnum):
    """TickTick priority levels."""

    NONE = 0
    LOW = 1
    MEDIUM = 3
    HIGH = 5


class TaskStatus(IntEnum):
    """TickTick task statuses."""

    ABANDONED = -1
    NORMAL = 0
    COMPLETED = 2


class Task(BaseModel):
    """Represents a TickTick task."""

    id: str = ""
    title: str = ""
    status: int = TaskStatus.NORMAL
    priority: int = TaskPriority.NONE
    project_id: str = Field(default="", alias="projectId")
    due_date: str | None = Field(default=None, alias="dueDate")
    start_date: str | None = Field(default=None, alias="startDate")
    tags: list[str] = Field(default_factory=list)
    content: str = ""
    is_all_day: bool = Field(default=False, alias="isAllDay")
    parent_id: str | None = Field(default=None, alias="parentId")
    column_id: str | None = Field(default=None, alias="columnId")
    pinned_time: str | None = Field(default=None, alias="pinnedTime")
    items: list[dict[str, Any]] = Field(default_factory=list)
    repeat_flag: str | None = Field(default=None, alias="repeatFlag")
    created_time: str | None = Field(default=None, alias="createdTime")
    modified_time: str | None = Field(default=None, alias="modifiedTime")

    model_config = {"populate_by_name": True, "extra": "allow"}

    @property
    def priority_label(self) -> str:
        """Human-readable priority."""
        return {0: "none", 1: "low", 3: "medium", 5: "high"}.get(self.priority, "none")

    @property
    def status_label(self) -> str:
        """Human-readable status."""
        if self.status >= 2:
            return "completed"
        if self.status == -1:
            return "abandoned"
        return "active"

    def to_output(self) -> dict[str, Any]:
        """Serialize for CLI output."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status_label,
            "priority": self.priority_label,
            "projectId": self.project_id,
            "dueDate": self.due_date or "",
            "startDate": self.start_date or "",
            "tags": self.tags,
            "content": self.content,
            "isAllDay": self.is_all_day,
            "parentId": self.parent_id,
            "columnId": self.column_id,
            "pinnedTime": self.pinned_time,
            "items": self.items,
        }
