"""Auth commands: login, login-v2, logout, status, refresh."""

from __future__ import annotations

import click

from ticktick_cli.config import clear_auth, load_auth
from ticktick_cli.output import output_error, output_message, output_success


@click.group("auth")
def auth_group() -> None:
    """Manage authentication with TickTick."""


@auth_group.command("login")
@click.option(
    "--client-id",
    envvar="TICKTICK_CLIENT_ID",
    required=True,
    help="OAuth Client ID (or set TICKTICK_CLIENT_ID env var)",
)
@click.option(
    "--client-secret",
    envvar="TICKTICK_CLIENT_SECRET",
    required=True,
    help="OAuth Client Secret (or set TICKTICK_CLIENT_SECRET env var)",
)
@click.option("--redirect-uri", default="http://localhost:8080/callback", help="OAuth redirect URI")
@click.pass_context
def auth_login(ctx: click.Context, client_id: str, client_secret: str, redirect_uri: str) -> None:
    """Login via OAuth 2.0 (opens browser). Required for V1 API."""
    from ticktick_cli.auth import oauth2_login

    profile = ctx.obj.get("profile", "default")
    try:
        oauth2_login(client_id, client_secret, redirect_uri, profile=profile)
        output_message("V1 OAuth login successful.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(2) from None


@auth_group.command("login-v2")
@click.option(
    "--username",
    envvar="TICKTICK_USERNAME",
    required=True,
    help="TickTick username/email (or set TICKTICK_USERNAME env var)",
)
@click.option(
    "--password",
    envvar="TICKTICK_PASSWORD",
    prompt=True,
    hide_input=True,
    help="TickTick password (or set TICKTICK_PASSWORD env var; prompts if omitted)",
)
@click.pass_context
def auth_login_v2(ctx: click.Context, username: str, password: str) -> None:
    """Login via V2 session (username/password). Required for advanced features."""
    from ticktick_cli.auth import v2_login

    profile = ctx.obj.get("profile", "default")
    try:
        v2_login(username, password, profile=profile)
        output_message("V2 session login successful.", ctx)
    except Exception as e:
        output_error(str(e), ctx)
        raise SystemExit(2) from None


@auth_group.command("logout")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def auth_logout(ctx: click.Context, yes: bool) -> None:
    """Remove stored credentials."""
    if not yes:
        click.confirm("Remove all stored credentials?", abort=True)
    profile = ctx.obj.get("profile", "default")
    clear_auth(profile)
    output_message("Credentials removed.", ctx)


@auth_group.command("status")
@click.pass_context
def auth_status(ctx: click.Context) -> None:
    """Show current authentication status."""
    profile = ctx.obj.get("profile", "default")
    auth = load_auth(profile)

    status = {
        "v1_authenticated": bool(auth.get("v1", {}).get("access_token")),
        "v2_authenticated": bool(auth.get("v2", {}).get("cookies")),
    }
    if auth.get("v1", {}).get("client_id"):
        status["v1_client_id"] = auth["v1"]["client_id"]
    if auth.get("v2", {}).get("username"):
        status["v2_username"] = auth["v2"]["username"]

    output_success(status, ctx)
