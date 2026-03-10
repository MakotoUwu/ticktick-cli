"""Authentication flows for V1 (OAuth 2.0) and V2 (session-based).

V1: OAuth 2.0 authorization code flow with local HTTP callback server
V2: Username/password session login
"""

from __future__ import annotations

import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from typing import Any

import httpx

from ticktick_cli.config import load_auth, save_auth
from ticktick_cli.exceptions import AuthenticationError

OAUTH_AUTHORIZE_URL = "https://ticktick.com/oauth/authorize"
OAUTH_TOKEN_URL = "https://ticktick.com/oauth/token"


def oauth2_login(
    client_id: str,
    client_secret: str,
    redirect_uri: str = "http://localhost:8080/callback",
    profile: str = "default",
) -> dict[str, Any]:
    """Run OAuth 2.0 authorization code flow.

    1. Opens browser to TickTick auth page
    2. Starts local HTTP server to catch the callback
    3. Exchanges authorization code for access token
    4. Saves tokens to config
    """
    # Generate CSRF state token for OAuth2 security (RFC 6749 §10.12)
    state = secrets.token_urlsafe(32)

    # Build authorization URL
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "tasks:read tasks:write",
        "state": state,
    }
    auth_url = f"{OAUTH_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    # Capture the authorization code via local server
    code_holder: dict[str, str] = {}

    parsed = urllib.parse.urlparse(redirect_uri)
    port = parsed.port or 8080
    callback_path = parsed.path or "/callback"

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed_req = urllib.parse.urlparse(self.path)
            # Validate callback path matches redirect URI
            if parsed_req.path != callback_path:
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed_req.query)
            # Validate CSRF state parameter
            returned_state = qs.get("state", [None])[0]
            if returned_state != state:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"Invalid state parameter (CSRF protection).")
                return
            if "code" in qs:
                code_holder["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Success!</h1>"
                    b"<p>You can close this window and return to the terminal.</p>"
                    b"</body></html>"
                )
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing authorization code.")

        def log_message(self, format: str, *args: Any) -> None:
            pass  # Suppress HTTP log noise

    server = http.server.HTTPServer(("localhost", port), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    server_thread.join(timeout=120)
    server.server_close()

    if "code" not in code_holder:
        raise AuthenticationError("OAuth callback timed out. No authorization code received.")

    # Exchange code for token
    token_data = _exchange_code(
        code_holder["code"],
        client_id,
        client_secret,
        redirect_uri,
    )

    # Save everything
    auth = load_auth(profile)
    auth["v1"] = {
        "access_token": token_data["access_token"],
        "token_type": token_data.get("token_type", "bearer"),
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "obtained_at": int(time.time()),
    }
    if "refresh_token" in token_data:
        auth["v1"]["refresh_token"] = token_data["refresh_token"]
    if "expires_in" in token_data:
        auth["v1"]["expires_in"] = token_data["expires_in"]
    save_auth(auth, profile)

    return token_data


def _exchange_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Exchange authorization code for access token."""
    response = httpx.post(
        OAUTH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code != 200:
        raise AuthenticationError(
            f"Token exchange failed ({response.status_code}): {response.text}"
        )
    return response.json()


def v2_login(
    username: str,
    password: str,
    profile: str = "default",
) -> dict[str, Any]:
    """Login via V2 session (username/password)."""
    from ticktick_cli.api.v2 import V2Client

    client = V2Client()
    result = client.authenticate(username, password)

    # Save session cookies
    auth = load_auth(profile)
    auth["v2"] = {
        "cookies": client.get_session_cookies(),
        "username": username,
    }
    save_auth(auth, profile)

    return result


def get_client(profile: str = "default") -> "TickTickClient":
    """Create a TickTickClient from stored credentials."""
    from ticktick_cli.api.client import TickTickClient

    auth = load_auth(profile)
    v1_token = None
    v2_cookies = None

    v1_data = auth.get("v1", {})
    if v1_data.get("access_token"):
        v1_token = v1_data["access_token"]

    v2_data = auth.get("v2", {})
    if v2_data.get("cookies"):
        v2_cookies = v2_data["cookies"]

    if not v1_token and not v2_cookies:
        raise AuthenticationError(
            "Not authenticated. Run `ticktick auth login` or `ticktick auth login-v2`."
        )

    return TickTickClient(v1_access_token=v1_token, v2_cookies=v2_cookies)
