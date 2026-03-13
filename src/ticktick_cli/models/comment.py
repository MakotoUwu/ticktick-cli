"""Pydantic models for TickTick task comments and activities."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User profile in a comment or activity."""

    is_myself: bool = Field(False, alias="isMyself")
    name: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class Comment(BaseModel):
    """A comment on a task."""

    id: str = ""
    title: str = ""
    created_time: str = Field("", alias="createdTime")
    modified_time: str = Field("", alias="modifiedTime")
    reply_comment_id: str | None = Field(None, alias="replyCommentId")
    mentions: list = Field(default_factory=list)
    attachments: list = Field(default_factory=list)
    user_profile: UserProfile | None = Field(None, alias="userProfile")
    reply_user_profile: UserProfile | None = Field(None, alias="replyUserProfile")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_output(self) -> dict:
        """Convert to output-friendly dict."""
        result: dict = {
            "id": self.id,
            "title": self.title,
            "createdTime": self.created_time,
        }
        if self.user_profile:
            result["isMyself"] = self.user_profile.is_myself
            if self.user_profile.name:
                result["author"] = self.user_profile.name
        if self.reply_comment_id:
            result["replyTo"] = self.reply_comment_id
        return result


class Activity(BaseModel):
    """A task activity/changelog entry."""

    id: str = ""
    action: str = ""
    when: str = ""
    device_channel: str | None = Field(None, alias="deviceChannel")
    kind: str | None = None
    # Date change fields
    start_date: str | None = Field(None, alias="startDate")
    start_date_before: str | None = Field(None, alias="startDateBefore")
    due_date: str | None = Field(None, alias="dueDate")
    due_date_before: str | None = Field(None, alias="dueDateBefore")
    is_all_day: bool | None = Field(None, alias="isAllDay")
    is_all_day_before: bool | None = Field(None, alias="isAllDayBefore")
    # Who
    who_profile: UserProfile | None = Field(None, alias="whoProfile")

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_output(self) -> dict:
        """Convert to output-friendly dict."""
        result: dict = {
            "id": self.id,
            "action": self.action,
            "when": self.when,
        }
        if self.device_channel:
            result["device"] = self.device_channel
        if self.start_date:
            result["startDate"] = self.start_date
        if self.start_date_before:
            result["startDateBefore"] = self.start_date_before
        if self.due_date:
            result["dueDate"] = self.due_date
        if self.due_date_before:
            result["dueDateBefore"] = self.due_date_before
        return result
