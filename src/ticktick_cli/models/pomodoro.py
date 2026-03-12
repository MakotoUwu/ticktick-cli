"""Pomodoro / Focus record model — Pydantic v2."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class PomodoroStatus(IntEnum):
    """Status of a pomodoro record."""

    RUNNING = 0
    COMPLETED = 1


class PomodoroTask(BaseModel):
    """A task associated with a pomodoro session."""

    id: str = ""
    tags: list[str] = Field(default_factory=list)
    project_name: str = Field(default="", alias="projectName")
    start_time: str = Field(default="", alias="startTime")
    end_time: str = Field(default="", alias="endTime")

    model_config = {"populate_by_name": True, "extra": "allow"}


class Pomodoro(BaseModel):
    """Represents a TickTick pomodoro (focus) record.

    Time format: ``YYYY-MM-DDTHH:mm:ss.SSS+0000`` (UTC).
    ID format: 24-char hex (MongoDB ObjectId).
    """

    id: str = ""
    start_time: str = Field(default="", alias="startTime")
    end_time: str = Field(default="", alias="endTime")
    pause_duration: int = Field(default=0, alias="pauseDuration")
    status: int = PomodoroStatus.COMPLETED
    note: str = ""
    tasks: list[PomodoroTask] = Field(default_factory=list)
    added: bool = True

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_output(self) -> dict[str, Any]:
        """Flatten for CLI output."""
        return {
            "id": self.id,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "pauseDuration": self.pause_duration,
            "status": self.status,
            "note": self.note,
            "tasks": len(self.tasks),
        }


class FocusOperation(BaseModel):
    """A single operation in a focus session (start/pause/drop/exit)."""

    id: str = ""
    o_id: str = Field(default="", alias="oId")
    o_type: int = Field(default=0, alias="oType")
    op: str = ""
    duration: int = 0
    first_focus_id: str = Field(default="", alias="firstFocusId")
    focus_on_id: str = Field(default="", alias="focusOnId")
    auto_pomo_left: int = Field(default=5, alias="autoPomoLeft")
    pomo_count: int = Field(default=1, alias="pomoCount")
    manual: bool = True
    note: str = ""
    time: str = ""

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_api(self) -> dict[str, Any]:
        """Serialize to API request format (camelCase)."""
        return self.model_dump(by_alias=True)
