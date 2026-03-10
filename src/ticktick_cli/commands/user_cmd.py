"""User commands — profile, status, stats, preferences (V2 only)."""

from __future__ import annotations

import click

from ticktick_cli.auth import get_client
from ticktick_cli.output import output_item, output_error


@click.group("user")
def user_group() -> None:
    """User info, statistics & preferences (V2)."""


@user_group.command("profile")
@click.pass_context
def user_profile(ctx: click.Context) -> None:
    """Show user profile information."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        profile = client.v2.get_user_profile()
        formatted = {
            "username": profile.get("username", ""),
            "name": profile.get("name", ""),
            "email": profile.get("email", profile.get("username", "")),
            "timeZone": profile.get("timeZone", ""),
            "inboxId": profile.get("inboxId", ""),
            "createdTime": profile.get("createdTime", ""),
        }
        output_item(formatted, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@user_group.command("status")
@click.pass_context
def user_status(ctx: click.Context) -> None:
    """Show subscription/account status."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        status = client.v2.get_user_status()
        formatted = {
            "proLevel": status.get("proLevel", 0),
            "proExpireDate": status.get("proExpireDate", ""),
            "subscribeType": status.get("subscribeType", ""),
            "freeTrial": status.get("freeTrial", False),
        }
        output_item(formatted, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@user_group.command("stats")
@click.pass_context
def user_stats(ctx: click.Context) -> None:
    """Show productivity statistics."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        stats = client.v2.get_user_statistics()
        output_item(stats, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)


@user_group.command("preferences")
@click.pass_context
def user_preferences(ctx: click.Context) -> None:
    """Show user preferences / settings."""
    client = get_client(ctx.obj.get("profile", "default"))
    try:
        prefs = client.v2.get_user_preferences()
        output_item(prefs, ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(1)
