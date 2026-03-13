"""Task template model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskTemplate(BaseModel):
    """A task template."""

    id: str = ""
    title: str = ""
    content: str = ""
    items: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    etag: str | None = None
    created_time: str = Field(alias="createdTime", default="")
    modified_time: str = Field(alias="modifiedTime", default="")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_output(self) -> dict[str, Any]:
        """Convert to output dict."""
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
        }
        if self.content:
            result["content"] = self.content
        if self.items:
            result["items"] = self.items
        if self.tags:
            result["tags"] = self.tags
        if self.etag:
            result["etag"] = self.etag
        return result
