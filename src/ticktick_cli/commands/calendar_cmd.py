"""Read-only calendar discovery commands (V2)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import click

from ticktick_cli.auth import get_client
from ticktick_cli.commands.task_cmd import _format_task
from ticktick_cli.output import output_error, output_item, output_list


def _normalize_subscriptions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("subscriptions", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _format_calendar_accounts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    accounts = payload.get("accounts", [])
    if not isinstance(accounts, list):
        return []

    formatted: list[dict[str, Any]] = []
    for account in accounts:
        if not isinstance(account, dict):
            continue
        calendars = account.get("calendars", [])
        if not isinstance(calendars, list):
            calendars = []
        visible = sum(1 for calendar in calendars if isinstance(calendar, dict) and calendar.get("visible"))
        formatted.append(
            {
                "id": account.get("id", ""),
                "account": account.get("account", ""),
                "site": account.get("site", ""),
                "calendarCount": len(calendars),
                "visibleCalendars": visible,
                "createdTime": account.get("createdTime", ""),
                "modifiedTime": account.get("modifiedTime", ""),
            }
        )
    return formatted


def _build_external_calendar_map(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    accounts = payload.get("accounts", [])
    if not isinstance(accounts, list):
        return {}

    calendar_map: dict[str, dict[str, str]] = {}
    for account in accounts:
        if not isinstance(account, dict):
            continue
        calendars = account.get("calendars", [])
        if not isinstance(calendars, list):
            continue
        for calendar in calendars:
            if not isinstance(calendar, dict):
                continue
            calendar_id = calendar.get("id", "")
            if not calendar_id:
                continue
            calendar_map[calendar_id] = {
                "sourceSite": account.get("site", ""),
                "sourceAccount": account.get("account", ""),
            }
    return calendar_map


def _build_subscription_id_set(payload: Any) -> set[str]:
    subscriptions = _normalize_subscriptions(payload)
    return {
        subscription.get("id", "")
        for subscription in subscriptions
        if isinstance(subscription, dict) and subscription.get("id")
    }


def _extract_linked_task_id(uid: str) -> str | None:
    if not uid.endswith("@calendar.ticktick.com"):
        return None

    candidate = uid.partition("@")[0]
    if re.fullmatch(r"[0-9a-f]{24}", candidate):
        return candidate
    return None


def _flatten_calendar_events(
    payload: dict[str, Any],
    *,
    external_calendars: dict[str, dict[str, str]],
    subscription_ids: set[str],
) -> list[dict[str, Any]]:
    calendars = payload.get("events", [])
    if not isinstance(calendars, list):
        return []

    rows: list[dict[str, Any]] = []
    for calendar in calendars:
        if not isinstance(calendar, dict):
            continue
        calendar_id = calendar.get("id", "")
        calendar_name = calendar.get("name", "")
        calendar_color = calendar.get("color", "")
        entries = calendar.get("events", [])
        if not isinstance(entries, list):
            continue
        for event in entries:
            if not isinstance(event, dict):
                continue
            uid = event.get("uid", "")
            linked_task_id = _extract_linked_task_id(uid) if isinstance(uid, str) else None
            if linked_task_id or calendar_name == "TickTick":
                source_type = "ticktick"
                source_site = "ticktick"
                source_account = ""
            elif calendar_id in subscription_ids:
                source_type = "subscription"
                source_site = "subscription"
                source_account = ""
            elif calendar_id in external_calendars:
                source_type = "external"
                source_site = external_calendars[calendar_id].get("sourceSite", "")
                source_account = external_calendars[calendar_id].get("sourceAccount", "")
            else:
                source_type = "unknown"
                source_site = ""
                source_account = ""
            rows.append(
                {
                    "id": event.get("id", ""),
                    "uid": uid,
                    "title": event.get("title", ""),
                    "dueStart": event.get("dueStart", ""),
                    "dueEnd": event.get("dueEnd", ""),
                    "isAllDay": event.get("isAllDay", False),
                    "calendarId": calendar_id,
                    "calendarName": calendar_name,
                    "calendarColor": calendar_color,
                    "sourceType": source_type,
                    "sourceSite": source_site,
                    "sourceAccount": source_account,
                    "linkedTaskId": linked_task_id,
                    "timezone": event.get("timezone", ""),
                    "location": event.get("location", ""),
                    "responseStatus": event.get("responseStatus", ""),
                    "repeatFlag": event.get("repeatFlag", ""),
                }
            )
    return rows


def _get_calendar_events(client: Any) -> list[dict[str, Any]]:
    account_payload = client.v2.get_calendar_third_accounts()
    subscription_payload = client.v2.get_calendar_subscriptions()
    return _flatten_calendar_events(
        client.v2.get_calendar_bound_events(),
        external_calendars=_build_external_calendar_map(account_payload),
        subscription_ids=_build_subscription_id_set(subscription_payload),
    )


def _find_calendar_event(client: Any, event_id: str) -> dict[str, Any] | None:
    for event in _get_calendar_events(client):
        if event.get("id") == event_id:
            return event
    return None


def _event_sort_key(event: dict[str, Any]) -> tuple[int, float, str, str]:
    due_start = event.get("dueStart", "")
    due_end = event.get("dueEnd", "") or due_start
    now = datetime.now(timezone.utc)

    try:
        end_dt = datetime.strptime(due_end, "%Y-%m-%dT%H:%M:%S.000+0000").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        end_dt = now

    try:
        start_dt = datetime.strptime(due_start, "%Y-%m-%dT%H:%M:%S.000+0000").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        start_dt = now

    is_past = end_dt < now
    sort_time = -start_dt.timestamp() if is_past else start_dt.timestamp()

    return (
        1 if is_past else 0,
        sort_time,
        event.get("calendarName", ""),
        event.get("title", ""),
    )


@click.group("calendar")
def calendar_group() -> None:
    """Read-only calendar discovery commands (V2)."""


@calendar_group.group("account")
def calendar_account_group() -> None:
    """List linked third-party calendar accounts."""


@calendar_account_group.command("list")
@click.pass_context
def calendar_account_list(ctx: click.Context) -> None:
    """List linked third-party calendar accounts."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        accounts = _format_calendar_accounts(client.v2.get_calendar_third_accounts())
        output_list(
            accounts,
            columns=[
                "id",
                "site",
                "account",
                "calendarCount",
                "visibleCalendars",
                "createdTime",
                "modifiedTime",
            ],
            title="Calendar Accounts",
            ctx=ctx,
        )
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@calendar_group.group("subscription")
def calendar_subscription_group() -> None:
    """List subscribed external calendars."""


@calendar_subscription_group.command("list")
@click.pass_context
def calendar_subscription_list(ctx: click.Context) -> None:
    """List subscribed external calendars."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        subscriptions = _normalize_subscriptions(client.v2.get_calendar_subscriptions())
        output_list(subscriptions, title="Calendar Subscriptions", ctx=ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@calendar_group.group("event")
def calendar_event_group() -> None:
    """List bound calendar events."""


@calendar_event_group.command("list")
@click.option("--calendar-id", default=None, help="Filter to a single linked calendar ID.")
@click.option("--limit", "-n", type=int, default=100, help="Max results (ignored with --all).")
@click.pass_context
def calendar_event_list(
    ctx: click.Context,
    calendar_id: str | None,
    limit: int,
) -> None:
    """List bound calendar events."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        events = _get_calendar_events(client)
        if calendar_id:
            events = [event for event in events if event.get("calendarId") == calendar_id]
        events.sort(key=_event_sort_key)
        output_list(
            events,
            columns=[
                "id",
                "title",
                "dueStart",
                "dueEnd",
                "isAllDay",
                "sourceType",
                "linkedTaskId",
                "calendarId",
                "calendarName",
            ],
            title="Calendar Events",
            ctx=ctx,
            limit=limit,
        )
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@calendar_event_group.command("show")
@click.argument("event_id")
@click.pass_context
def calendar_event_show(ctx: click.Context, event_id: str) -> None:
    """Show detailed information for a single bound calendar event."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        event = _find_calendar_event(client, event_id)
        if not event:
            output_error(f"Calendar event not found: {event_id}", ctx, exit_code=4)
            raise SystemExit(4)
        output_item(event, ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None


@calendar_event_group.command("task")
@click.argument("event_id")
@click.pass_context
def calendar_event_task(ctx: click.Context, event_id: str) -> None:
    """Resolve a TickTick-owned calendar event to its backing task."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        event = _find_calendar_event(client, event_id)
        if not event:
            output_error(f"Calendar event not found: {event_id}", ctx, exit_code=4)
            raise SystemExit(4)

        linked_task_id = event.get("linkedTaskId")
        if not linked_task_id:
            output_error(
                "Calendar event is not backed by a TickTick task. External and subscribed calendars are read-only mirrors.",
                ctx,
            )
            raise SystemExit(1)

        task = _format_task(client.v2.get_task(linked_task_id))
        task["calendarEventId"] = event.get("id", "")
        task["calendarEventTitle"] = event.get("title", "")
        task["calendarSourceType"] = event.get("sourceType", "")
        output_item(task, ctx)
    except SystemExit:
        raise
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
