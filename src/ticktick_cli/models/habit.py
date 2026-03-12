"""Habit and HabitCheckin models — Pydantic v2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Habit(BaseModel):
    """Represents a TickTick habit."""

    id: str = ""
    name: str = ""
    type: str = "Boolean"  # "Boolean" or "Real"
    goal: float = 1.0
    step: float = 0.0
    unit: str = "Count"
    icon_res: str = Field(default="", alias="iconRes")
    color: str = ""
    status: int = 0  # 0=active, 2=archived
    total_check_ins: int = Field(default=0, alias="totalCheckIns")
    current_streak: int = Field(default=0, alias="currentStreak")
    section_id: str = Field(default="", alias="sectionId")
    repeat_rule: str | None = Field(default=None, alias="repeatRule")
    created_time: str | None = Field(default=None, alias="createdTime")
    modified_time: str | None = Field(default=None, alias="modifiedTime")

    model_config = {"populate_by_name": True, "extra": "allow"}

    @property
    def status_label(self) -> str:
        return "archived" if self.status == 2 else "active"

    def to_output(self) -> dict[str, Any]:
        """Serialize for CLI output."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "goal": self.goal,
            "unit": self.unit,
            "color": self.color,
            "status": self.status_label,
            "totalCheckIns": self.total_check_ins,
            "currentStreak": self.current_streak,
            "iconRes": self.icon_res,
            "sectionId": self.section_id,
        }


class HabitCheckin(BaseModel):
    """Represents a habit check-in record."""

    id: str = ""
    habit_id: str = Field(default="", alias="habitId")
    checkin_stamp: int = Field(default=0, alias="checkinStamp")
    value: float = 0.0
    goal: float = 0.0
    status: int = 0
    created_time: str | None = Field(default=None, alias="createdTime")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_output(self) -> dict[str, Any]:
        return {
            "date": self.checkin_stamp,
            "value": self.value,
            "status": self.status,
        }
