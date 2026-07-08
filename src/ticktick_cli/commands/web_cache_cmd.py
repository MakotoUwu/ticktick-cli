"""Web cache commands for read-only TickTick browser-state audits."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import click

from ticktick_cli.output import output_error, output_item


@click.group("web-cache")
def web_cache_group() -> None:
    """Analyze exported TickTick web app cache snapshots."""


@web_cache_group.command("audit")
@click.option(
    "--file",
    "cache_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="JSON snapshot exported from TickTick web cache.",
)
@click.option("--today", default=None, help="Audit date in YYYY-MM-DD format. Defaults to local date.")
@click.option("--group", "group_name", default=None, help="Only include projects in this folder/group name.")
@click.option("--sample-limit", type=click.IntRange(0, 25), default=5, show_default=True)
@click.pass_context
def audit_web_cache(
    ctx: click.Context,
    cache_file: Path,
    today: str | None,
    group_name: str | None,
    sample_limit: int,
) -> None:
    """Audit a TickTick web-cache snapshot without calling TickTick APIs."""
    try:
        audit_day = _parse_day(today) if today else date.today()
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        result = _audit_cache(data, audit_day=audit_day, group_name=group_name, sample_limit=sample_limit)
        output_item(result, ctx)
    except ValueError as exc:
        output_error(str(exc), ctx, exit_code=2)
        raise SystemExit(2) from None
    except OSError as exc:
        output_error(str(exc), ctx)
        raise SystemExit(1) from None


def _audit_cache(
    data: dict[str, Any],
    *,
    audit_day: date,
    group_name: str | None,
    sample_limit: int,
) -> dict[str, Any]:
    tasks = _records(data, "tasks", "taskRows")
    columns = _records(data, "columns", "columnRows")
    projects = _records(data, "projects", "projectProfiles", "projectRows")
    groups = _records(data, "projectGroups", "projectGroup", "folderRows")

    project_map = _map_by_id(projects)
    column_map = _map_by_id(columns)
    group_map = _map_by_id(groups)
    filtered_tasks = _filter_tasks_by_group(tasks, project_map, group_map, group_name)
    active_tasks = [task for task in filtered_tasks if _is_active(task)]
    completed_recent_since = audit_day - timedelta(days=7)
    completed_recent = [
        task
        for task in filtered_tasks
        if _is_completed(task) and _completed_day(task) and _completed_day(task) >= completed_recent_since
    ]

    due_buckets = _due_buckets(active_tasks, audit_day)
    priority_tasks = [task for task in active_tasks if _priority(task) >= 3]
    project_stats = _project_stats(active_tasks, project_map, group_map, audit_day)
    column_stats = _column_stats(active_tasks, column_map, project_map, audit_day)
    flags = _flags(active_tasks, project_stats, due_buckets)

    return {
        "source": "ticktick-web-cache",
        "read_only": True,
        "today": audit_day.isoformat(),
        "group_filter": group_name,
        "group_filter_matched": group_name is None or any(_same_name(group, group_name) for group in group_map.values()),
        "totals": {
            "tasks": len(filtered_tasks),
            "active": len(active_tasks),
            "completed_recent": len(completed_recent),
            "today": len(due_buckets["today"]),
            "overdue": len(due_buckets["overdue"]),
            "future": len(due_buckets["future"]),
            "no_date": len(due_buckets["no_date"]),
            "high_or_medium_priority": len(priority_tasks),
        },
        "projects": project_stats,
        "columns": column_stats,
        "samples": {
            "today": [_sample_task(task, project_map, column_map, group_map) for task in due_buckets["today"][:sample_limit]],
            "overdue": [
                _sample_task(task, project_map, column_map, group_map)
                for task in sorted(due_buckets["overdue"], key=_sort_by_due)[:sample_limit]
            ],
            "no_date": [_sample_task(task, project_map, column_map, group_map) for task in due_buckets["no_date"][:sample_limit]],
        },
        "flags": flags,
    }


def _records(data: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        if key in data:
            return _flatten_records(data[key])
    for container_key in ("indexedDB", "localStorage", "cache"):
        nested = data.get(container_key)
        if isinstance(nested, dict):
            nested_records = _records(nested, *keys)
            if nested_records:
                return nested_records
    return []


def _flatten_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        records: list[dict[str, Any]] = []
        for item in value:
            records.extend(_flatten_records(item))
        return records
    if isinstance(value, dict):
        if _looks_like_record(value):
            return [value]
        records = []
        for key, item in value.items():
            if isinstance(item, dict) and _looks_like_record(item):
                records.append({"id": item.get("id", key), **item})
            else:
                records.extend(_flatten_records(item))
        return records
    return []


def _looks_like_record(value: dict[str, Any]) -> bool:
    return any(key in value for key in ("id", "title", "name", "projectId", "columnId", "status"))


def _map_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record["id"]): record for record in records if record.get("id")}


def _filter_tasks_by_group(
    tasks: list[dict[str, Any]],
    project_map: dict[str, dict[str, Any]],
    group_map: dict[str, dict[str, Any]],
    group_name: str | None,
) -> list[dict[str, Any]]:
    if not group_name:
        return tasks

    result = []
    for task in tasks:
        project = project_map.get(_project_id(task), {})
        group = group_map.get(str(project.get("groupId", "")), {})
        if _same_name(group, group_name):
            result.append(task)
    return result


def _same_name(record: dict[str, Any], name: str) -> bool:
    return str(record.get("name", "")).casefold() == name.casefold()


def _is_active(task: dict[str, Any]) -> bool:
    return not _is_deleted(task) and not _is_completed(task)


def _is_deleted(task: dict[str, Any]) -> bool:
    return bool(task.get("deleted") or task.get("isDeleted"))


def _is_completed(task: dict[str, Any]) -> bool:
    return _status(task) == 2 or bool(task.get("completedTime") or task.get("completedDate"))


def _status(task: dict[str, Any]) -> int:
    try:
        return int(task.get("status") or 0)
    except (TypeError, ValueError):
        return 0


def _priority(task: dict[str, Any]) -> int:
    try:
        return int(task.get("priority") or 0)
    except (TypeError, ValueError):
        return 0


def _due_buckets(tasks: list[dict[str, Any]], audit_day: date) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {"today": [], "overdue": [], "future": [], "no_date": []}
    for task in tasks:
        due_day = _due_day(task)
        if due_day is None:
            buckets["no_date"].append(task)
        elif due_day == audit_day:
            buckets["today"].append(task)
        elif due_day < audit_day:
            buckets["overdue"].append(task)
        else:
            buckets["future"].append(task)
    return buckets


def _project_stats(
    tasks: list[dict[str, Any]],
    project_map: dict[str, dict[str, Any]],
    group_map: dict[str, dict[str, Any]],
    audit_day: date,
) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"active": 0, "today": 0, "overdue": 0, "no_date": 0})
    for task in tasks:
        project_id = _project_id(task)
        stat = stats[project_id]
        stat["active"] += 1
        due_day = _due_day(task)
        if due_day == audit_day:
            stat["today"] += 1
        elif due_day is None:
            stat["no_date"] += 1
        elif due_day < audit_day:
            stat["overdue"] += 1

    result = []
    for project_id, stat in stats.items():
        project = project_map.get(project_id, {})
        group = group_map.get(str(project.get("groupId", "")), {})
        result.append({
            "id": project_id,
            "name": _project_name(project_id, project),
            "group": group.get("name") or None,
            **stat,
        })
    return sorted(result, key=lambda item: (-int(item["active"]), str(item["name"]).casefold()))


def _column_stats(
    tasks: list[dict[str, Any]],
    column_map: dict[str, dict[str, Any]],
    project_map: dict[str, dict[str, Any]],
    audit_day: date,
) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"active": 0, "today": 0, "overdue": 0})
    for task in tasks:
        column_id = str(task.get("columnId") or "")
        if not column_id:
            continue
        stat = stats[column_id]
        stat["active"] += 1
        due_day = _due_day(task)
        if due_day == audit_day:
            stat["today"] += 1
        elif due_day and due_day < audit_day:
            stat["overdue"] += 1

    result = []
    for column_id, stat in stats.items():
        column = column_map.get(column_id, {})
        project = project_map.get(str(column.get("projectId", "")), {})
        result.append({
            "id": column_id,
            "name": column.get("name") or "(unknown column)",
            "project": _project_name(str(project.get("id", "")), project) if project else None,
            **stat,
        })
    return sorted(result, key=lambda item: (-int(item["active"]), str(item["name"]).casefold()))


def _flags(
    active_tasks: list[dict[str, Any]],
    project_stats: list[dict[str, Any]],
    due_buckets: dict[str, list[dict[str, Any]]],
) -> list[str]:
    flags: list[str] = []
    if len(due_buckets["overdue"]) >= 20:
        flags.append("overdue_dates_are_noisy")
    if len(due_buckets["today"]) >= 10:
        flags.append("today_is_overloaded")
    if len(due_buckets["no_date"]) >= 30:
        flags.append("many_active_tasks_have_no_date")
    if len(active_tasks) >= 150:
        flags.append("active_task_inventory_is_high")
    for project in project_stats:
        if str(project["id"]).startswith("inbox") and int(project["active"]) >= 25:
            flags.append("inbox_needs_triage")
            break
    return flags


def _sample_task(
    task: dict[str, Any],
    project_map: dict[str, dict[str, Any]],
    column_map: dict[str, dict[str, Any]],
    group_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    project_id = _project_id(task)
    project = project_map.get(project_id, {})
    group = group_map.get(str(project.get("groupId", "")), {})
    column_id = str(task.get("columnId") or "")
    column = column_map.get(column_id, {})
    return {
        "id": task.get("id"),
        "title": task.get("title") or task.get("content") or "(untitled)",
        "project_id": project_id,
        "project": _project_name(project_id, project),
        "group": group.get("name") or None,
        "column_id": column_id or None,
        "column": column.get("name") or None,
        "due_date": _day_string(task),
        "priority": _priority(task),
        "tags": task.get("tags") or [],
    }


def _project_id(task: dict[str, Any]) -> str:
    return str(task.get("projectId") or task.get("project_id") or "")


def _project_name(project_id: str, project: dict[str, Any]) -> str:
    if project.get("name"):
        return str(project["name"])
    if project_id.startswith("inbox"):
        return "Inbox"
    return "(unknown project)"


def _completed_day(task: dict[str, Any]) -> date | None:
    return _parse_optional_day(task.get("completedTime") or task.get("completedDate"))


def _due_day(task: dict[str, Any]) -> date | None:
    return _parse_optional_day(task.get("dueDate") or task.get("startDate"))


def _day_string(task: dict[str, Any]) -> str | None:
    day = _due_day(task)
    return day.isoformat() if day else None


def _sort_by_due(task: dict[str, Any]) -> tuple[date, str]:
    return (_due_day(task) or date.min, str(task.get("title") or ""))


def _parse_optional_day(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value)
    if len(text) < 10:
        return None
    try:
        return _parse_day(text[:10])
    except ValueError:
        return None


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc
