"""Read-only calendar discovery commands (V2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_error, output_list


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


def _flatten_calendar_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
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
            rows.append(
                {
                    "id": event.get("id", ""),
                    "uid": event.get("uid", ""),
                    "title": event.get("title", ""),
                    "dueStart": event.get("dueStart", ""),
                    "dueEnd": event.get("dueEnd", ""),
                    "isAllDay": event.get("isAllDay", False),
                    "calendarId": calendar_id,
                    "calendarName": calendar_name,
                    "calendarColor": calendar_color,
                    "timezone": event.get("timezone", ""),
                    "location": event.get("location", ""),
                    "responseStatus": event.get("responseStatus", ""),
                    "repeatFlag": event.get("repeatFlag", ""),
                }
            )
    return rows


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
        events = _flatten_calendar_events(client.v2.get_calendar_bound_events())
        if calendar_id:
            events = [event for event in events if event.get("calendarId") == calendar_id]
        events.sort(key=_event_sort_key)
        if not ctx.obj.get("all"):
            events = events[:limit]
        output_list(
            events,
            columns=[
                "id",
                "title",
                "dueStart",
                "dueEnd",
                "isAllDay",
                "calendarId",
                "calendarName",
            ],
            title="Calendar Events",
            ctx=ctx,
        )
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1) from None
