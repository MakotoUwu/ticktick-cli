"""Tag model — Pydantic v2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """Represents a TickTick tag."""

    name: str = ""
    label: str = ""
    color: str = ""
    parent: str = ""
    sort_type: str = Field(default="", alias="sortType")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_output(self) -> dict[str, Any]:
        """Serialize for CLI output."""
        return {
            "name": self.name,
            "label": self.label or self.name,
            "color": self.color,
            "parent": self.parent,
            "sortType": self.sort_type,
        }
