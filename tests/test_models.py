"""Test Pydantic models."""

from __future__ import annotations

from ticktick_cli.models import (
    Habit,
    HabitCheckin,
    Project,
    Tag,
    Task,
    TaskPriority,
    TaskStatus,
)


class TestTaskModel:
    def test_from_api_dict(self) -> None:
        raw = {
            "id": "abc123",
            "title": "Buy milk",
            "status": 0,
            "priority": 5,
            "projectId": "proj1",
            "dueDate": "2026-03-15T00:00:00.000+0000",
            "tags": ["shopping"],
            "content": "2% milk",
            "isAllDay": True,
        }
        task = Task(**raw)
        assert task.id == "abc123"
        assert task.title == "Buy milk"
        assert task.priority == TaskPriority.HIGH
        assert task.project_id == "proj1"
        assert task.is_all_day is True
        assert task.tags == ["shopping"]

    def test_status_label(self) -> None:
        assert Task(status=0).status_label == "active"
        assert Task(status=2).status_label == "completed"
        assert Task(status=-1).status_label == "abandoned"

    def test_priority_label(self) -> None:
        assert Task(priority=0).priority_label == "none"
        assert Task(priority=1).priority_label == "low"
        assert Task(priority=3).priority_label == "medium"
        assert Task(priority=5).priority_label == "high"

    def test_to_output(self) -> None:
        task = Task(id="t1", title="Test", priority=3, status=2)
        out = task.to_output()
        assert out["id"] == "t1"
        assert out["status"] == "completed"
        assert out["priority"] == "medium"

    def test_extra_fields_allowed(self) -> None:
        task = Task(id="t1", unknownField="value")
        assert task.id == "t1"

    def test_default_values(self) -> None:
        task = Task()
        assert task.id == ""
        assert task.status == TaskStatus.NORMAL
        assert task.priority == TaskPriority.NONE
        assert task.tags == []
        assert task.items == []


class TestProjectModel:
    def test_from_api_dict(self) -> None:
        raw = {"id": "proj1", "name": "Work", "color": "#FF0000", "viewMode": "kanban"}
        project = Project(**raw)
        assert project.id == "proj1"
        assert project.name == "Work"
        assert project.view_mode == "kanban"

    def test_to_output(self) -> None:
        project = Project(id="p1", name="Home")
        out = project.to_output()
        assert out["id"] == "p1"
        assert out["name"] == "Home"
        assert out["kind"] == "TASK"  # default

    def test_default_values(self) -> None:
        project = Project()
        assert project.id == ""
        assert project.name == ""
        assert project.is_owner is True


class TestHabitModel:
    def test_from_api_dict(self) -> None:
        raw = {
            "id": "h1",
            "name": "Exercise",
            "type": "Boolean",
            "goal": 1.0,
            "status": 0,
            "totalCheckIns": 42,
            "currentStreak": 5,
        }
        habit = Habit(**raw)
        assert habit.id == "h1"
        assert habit.name == "Exercise"
        assert habit.total_check_ins == 42
        assert habit.current_streak == 5

    def test_status_label(self) -> None:
        assert Habit(status=0).status_label == "active"
        assert Habit(status=2).status_label == "archived"

    def test_to_output(self) -> None:
        habit = Habit(id="h1", name="Read", status=2, total_check_ins=100)
        out = habit.to_output()
        assert out["status"] == "archived"
        assert out["totalCheckIns"] == 100


class TestHabitCheckinModel:
    def test_from_api_dict(self) -> None:
        raw = {"id": "c1", "habitId": "h1", "checkinStamp": 20260311, "value": 1.0, "status": 2}
        checkin = HabitCheckin(**raw)
        assert checkin.habit_id == "h1"
        assert checkin.checkin_stamp == 20260311

    def test_to_output(self) -> None:
        checkin = HabitCheckin(checkin_stamp=20260311, value=1.0, status=2)
        out = checkin.to_output()
        assert out["date"] == 20260311


class TestTagModel:
    def test_from_api_dict(self) -> None:
        raw = {"name": "urgent", "label": "Urgent", "color": "#FF0000", "parent": ""}
        tag = Tag(**raw)
        assert tag.name == "urgent"
        assert tag.label == "Urgent"

    def test_to_output_uses_name_as_label_fallback(self) -> None:
        tag = Tag(name="test")
        out = tag.to_output()
        assert out["label"] == "test"

    def test_default_values(self) -> None:
        tag = Tag()
        assert tag.name == ""
        assert tag.color == ""
        assert tag.parent == ""
