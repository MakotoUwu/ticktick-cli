"""Filter (smart list) model."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class FilterCondition(BaseModel):
    """A single filter condition."""

    or_values: list[Any] = Field(alias="or", default_factory=list)
    condition_type: int = Field(alias="conditionType", default=1)
    condition_name: str = Field(alias="conditionName", default="")

    model_config = {"populate_by_name": True, "extra": "allow"}


class FilterRule(BaseModel):
    """Filter rule containing AND-combined conditions."""

    and_conditions: list[FilterCondition] = Field(alias="and", default_factory=list)
    version: int = 1
    type: int = 0  # 0 = Normal, 1 = Advanced

    model_config = {"populate_by_name": True, "extra": "allow"}


class Filter(BaseModel):
    """A saved filter (smart list)."""

    id: str = ""
    name: str = ""
    rule: str = ""  # JSON-encoded FilterRule
    sort_order: int = Field(alias="sortOrder", default=0)
    sort_type: str = Field(alias="sortType", default="project")
    etag: str | None = None
    created_time: str = Field(alias="createdTime", default="")
    modified_time: str = Field(alias="modifiedTime", default="")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def parsed_rule(self) -> FilterRule | None:
        """Parse the JSON rule string into a FilterRule."""
        if not self.rule:
            return None
        try:
            data = json.loads(self.rule)
            return FilterRule(**data)
        except (json.JSONDecodeError, Exception):
            return None

    def to_output(self) -> dict[str, Any]:
        """Convert to output dict."""
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "sortType": self.sort_type,
        }
        rule = self.parsed_rule()
        if rule:
            conditions = []
            for cond in rule.and_conditions:
                conditions.append({
                    "field": cond.condition_name,
                    "values": cond.or_values,
                })
            result["conditions"] = conditions
        if self.etag:
            result["etag"] = self.etag
        return result
