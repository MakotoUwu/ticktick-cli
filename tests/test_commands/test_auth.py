"""Test auth commands and auth module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ticktick_cli.cli import cli
from ticktick_cli.config import load_auth, save_auth
from ticktick_cli.exceptions import AuthenticationError


@pytest.fixture
def temp_auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path


# ── CLI: auth status ────────────────────────────────────────


class TestAuthStatus:
    def test_status_not_authenticated(self, runner: CliRunner, temp_auth_env: Path) -> None:
        result = runner.invoke(cli, ["auth", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["v1_authenticated"] is False
        assert data["data"]["v2_authenticated"] is False

    def test_status_v1_authenticated(self, runner: CliRunner, temp_auth_env: Path) -> None:
        save_auth({"v1": {"access_token": "tok_abc123", "client_id": "my_client"}})
        result = runner.invoke(cli, ["auth", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["v1_authenticated"] is True
        assert data["data"]["v2_authenticated"] is False
        assert data["data"]["v1_client_id"] == "my_client"

    def test_status_v2_authenticated(self, runner: CliRunner, temp_auth_env: Path) -> None:
        save_auth({"v2": {"cookies": {"t": "session"}, "username": "me@test.com"}})
        result = runner.invoke(cli, ["auth", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["data"]["v1_authenticated"] is False
        assert data["data"]["v2_authenticated"] is True
        assert data["data"]["v2_username"] == "me@test.com"

    def test_status_both_authenticated(self, runner: CliRunner, temp_auth_env: Path) -> None:
        save_auth({
            "v1": {"access_token": "tok_abc", "client_id": "cid"},
            "v2": {"cookies": {"t": "s"}, "username": "user@x.com"},
        })
        result = runner.invoke(cli, ["auth", "status"])
        data = json.loads(result.output)
        assert data["data"]["v1_authenticated"] is True
        assert data["data"]["v2_authenticated"] is True

    def test_status_with_profile(self, runner: CliRunner, temp_auth_env: Path) -> None:
        save_auth({"v1": {"access_token": "work_tok"}}, profile="work")
        # Default profile should be empty
        result = runner.invoke(cli, ["auth", "status"])
        data = json.loads(result.output)
        assert data["data"]["v1_authenticated"] is False
        # Work profile should have the token
        result2 = runner.invoke(cli, ["--profile", "work", "auth", "status"])
        data2 = json.loads(result2.output)
        assert data2["data"]["v1_authenticated"] is True


# ── CLI: auth logout ────────────────────────────────────────


class TestAuthLogout:
    def test_logout_with_yes(self, runner: CliRunner, temp_auth_env: Path) -> None:
        result = runner.invoke(cli, ["auth", "logout", "--yes"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "removed" in data["message"].lower() or "logged out" in data["message"].lower()

    def test_logout_clears_stored_auth(self, runner: CliRunner, temp_auth_env: Path) -> None:
        save_auth({
            "v1": {"access_token": "tok"},
            "v2": {"cookies": {"t": "s"}, "username": "u@x.com"},
        })
        # Verify it's stored
        assert load_auth()["v1"]["access_token"] == "tok"
        # Logout
        runner.invoke(cli, ["auth", "logout", "--yes"])
        # Verify it's gone
        assert load_auth() == {}

    def test_logout_without_yes_aborts(self, runner: CliRunner, temp_auth_env: Path) -> None:
        save_auth({"v1": {"access_token": "keep_me"}})
        runner.invoke(cli, ["auth", "logout"], input="n\n")
        # Should abort — credentials remain
        assert load_auth().get("v1", {}).get("access_token") == "keep_me"


# ── CLI: auth login (OAuth2) ────────────────────────────────


class TestAuthLogin:
    def test_login_success(self, runner: CliRunner, temp_auth_env: Path) -> None:
        mock_token = {"access_token": "new_token", "token_type": "bearer"}
        with patch("ticktick_cli.auth.oauth2_login", return_value=mock_token):
            result = runner.invoke(cli, [
                "auth", "login",
                "--client-id", "test_cid",
                "--client-secret", "test_secret",
            ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "successful" in data["message"].lower()

    def test_login_failure_exits_2(self, runner: CliRunner, temp_auth_env: Path) -> None:
        with patch(
            "ticktick_cli.auth.oauth2_login",
            side_effect=AuthenticationError("OAuth callback timed out"),
        ):
            result = runner.invoke(cli, [
                "auth", "login",
                "--client-id", "bad",
                "--client-secret", "bad",
            ])
        assert result.exit_code == 2

    def test_login_missing_client_id_fails(self, runner: CliRunner, temp_auth_env: Path) -> None:
        result = runner.invoke(cli, ["auth", "login", "--client-secret", "x"])
        assert result.exit_code != 0
        assert "client-id" in result.output.lower() or "Missing" in result.output


# ── CLI: auth login-v2 ──────────────────────────────────────


class TestAuthLoginV2:
    def test_login_v2_success(self, runner: CliRunner, temp_auth_env: Path) -> None:
        with patch("ticktick_cli.auth.v2_login", return_value={"token": "sess"}):
            result = runner.invoke(cli, [
                "auth", "login-v2",
                "--username", "me@test.com",
                "--password", "secret",
            ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "successful" in data["message"].lower()

    def test_login_v2_bad_credentials_exits_2(self, runner: CliRunner, temp_auth_env: Path) -> None:
        with patch(
            "ticktick_cli.auth.v2_login",
            side_effect=AuthenticationError("Invalid credentials"),
        ):
            result = runner.invoke(cli, [
                "auth", "login-v2",
                "--username", "bad@x.com",
                "--password", "wrong",
            ])
        assert result.exit_code == 2

    def test_login_v2_missing_password_fails(self, runner: CliRunner, temp_auth_env: Path) -> None:
        result = runner.invoke(cli, ["auth", "login-v2", "--username", "user"])
        assert result.exit_code != 0


# ── auth module: get_client ──────────────────────────────────


class TestGetClient:
    def test_get_client_no_credentials_raises(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import get_client

        with pytest.raises(AuthenticationError, match="Not authenticated"):
            get_client()

    def test_get_client_v1_only(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import get_client

        save_auth({"v1": {"access_token": "my_token"}})
        client = get_client()
        assert client.has_v1 is True
        assert client.has_v2 is False

    def test_get_client_v2_only(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import get_client

        save_auth({"v2": {"cookies": {"t": "session_cookie"}}})
        client = get_client()
        assert client.has_v1 is False
        assert client.has_v2 is True

    def test_get_client_both(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import get_client

        save_auth({
            "v1": {"access_token": "tok"},
            "v2": {"cookies": {"t": "sess"}},
        })
        client = get_client()
        assert client.has_v1 is True
        assert client.has_v2 is True

    def test_get_client_respects_profile(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import get_client

        save_auth({"v1": {"access_token": "work_tok"}}, profile="work")
        # Default profile: no credentials
        with pytest.raises(AuthenticationError):
            get_client("default")
        # Work profile: has credentials
        client = get_client("work")
        assert client.has_v1 is True

    def test_get_client_empty_token_not_treated_as_auth(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import get_client

        save_auth({"v1": {"access_token": ""}, "v2": {"cookies": {}}})
        with pytest.raises(AuthenticationError, match="Not authenticated"):
            get_client()


# ── auth module: v2_login ────────────────────────────────────


class TestV2Login:
    def test_v2_login_saves_session(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import v2_login

        mock_v2 = MagicMock()
        mock_v2.authenticate.return_value = {"token": "ok"}
        mock_v2.get_session_cookies.return_value = {"t": "cookie_val"}

        with patch("ticktick_cli.api.v2.V2Client", return_value=mock_v2):
            result = v2_login("me@test.com", "mypass")

        assert result == {"token": "ok"}
        auth = load_auth()
        assert auth["v2"]["cookies"] == {"t": "cookie_val"}
        assert auth["v2"]["username"] == "me@test.com"

    def test_v2_login_auth_failure_propagates(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import v2_login

        mock_v2 = MagicMock()
        mock_v2.authenticate.side_effect = AuthenticationError("Invalid credentials")

        with patch("ticktick_cli.api.v2.V2Client", return_value=mock_v2):
            with pytest.raises(AuthenticationError, match="Invalid credentials"):
                v2_login("bad@x.com", "wrong")


# ── auth module: _exchange_code ──────────────────────────────


class TestExchangeCode:
    def test_exchange_code_success(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import _exchange_code

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "got_it",
            "token_type": "bearer",
            "expires_in": 86400,
        }

        with patch("ticktick_cli.auth.httpx.post", return_value=mock_resp) as mock_post:
            result = _exchange_code("auth_code", "cid", "csec", "http://localhost:8080/callback")

        assert result["access_token"] == "got_it"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["data"]["code"] == "auth_code"
        assert call_kwargs[1]["auth"] == ("cid", "csec")

    def test_exchange_code_failure_raises(self, temp_auth_env: Path) -> None:
        from ticktick_cli.auth import _exchange_code

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        with patch("ticktick_cli.auth.httpx.post", return_value=mock_resp):
            with pytest.raises(AuthenticationError, match="Token exchange failed"):
                _exchange_code("bad_code", "cid", "csec", "http://localhost:8080/callback")


# ── auth module: oauth2_login (end-to-end with mocks) ───────


class TestOAuth2Login:
    def test_oauth2_login_full_flow(self, temp_auth_env: Path) -> None:
        """Test the full OAuth2 flow with mocked browser + server + token exchange."""
        from ticktick_cli.auth import oauth2_login

        token_response = {
            "access_token": "oauth_tok_123",
            "token_type": "bearer",
            "refresh_token": "ref_tok",
            "expires_in": 86400,
        }

        # We'll intercept webbrowser.open to simulate the callback
        captured_url = {}

        def fake_browser_open(url: str) -> None:
            captured_url["url"] = url
            # Extract the state parameter from the auth URL for CSRF validation
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            state = qs.get("state", [""])[0]
            # Extract the port from redirect_uri, hit the local callback server
            # with a fake authorization code (include state for CSRF validation)
            import time
            time.sleep(0.1)  # Let the server start
            try:
                urllib.request.urlopen(
                    f"http://localhost:18999/callback?code=test_auth_code&state={state}",
                    timeout=5,
                )
            except Exception:
                pass

        with (
            patch("ticktick_cli.auth.webbrowser.open", side_effect=fake_browser_open),
            patch("ticktick_cli.auth._exchange_code", return_value=token_response),
        ):
            result = oauth2_login(
                client_id="test_cid",
                client_secret="test_csec",
                redirect_uri="http://localhost:18999/callback",
            )

        # Token was returned
        assert result["access_token"] == "oauth_tok_123"

        # Credentials were saved
        auth = load_auth()
        assert auth["v1"]["access_token"] == "oauth_tok_123"
        assert auth["v1"]["client_id"] == "test_cid"
        assert auth["v1"]["refresh_token"] == "ref_tok"
        assert auth["v1"]["expires_in"] == 86400
        assert "obtained_at" in auth["v1"]  # token expiry tracking
        assert "client_secret" not in auth["v1"]  # secret not stored on disk

        # Browser was opened with correct URL
        assert "client_id=test_cid" in captured_url["url"]
        assert "response_type=code" in captured_url["url"]
        assert "state=" in captured_url["url"]  # CSRF protection

    def test_oauth2_login_timeout_raises(self, temp_auth_env: Path) -> None:
        """If the callback never arrives, should raise AuthenticationError."""
        from ticktick_cli.auth import oauth2_login

        # Patch webbrowser to do nothing, and use a very short timeout
        # by mocking the server thread join
        with (
            patch("ticktick_cli.auth.webbrowser.open"),
            patch("ticktick_cli.auth.http.server.HTTPServer") as mock_server_cls,
        ):
            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server

            # The thread calls handle_request which does nothing (no callback)
            with patch("ticktick_cli.auth.threading.Thread") as mock_thread_cls:
                mock_thread = MagicMock()
                mock_thread_cls.return_value = mock_thread

                with pytest.raises(AuthenticationError, match="timed out"):
                    oauth2_login("cid", "csec", redirect_uri="http://localhost:19876/callback")


# ── TickTickClient properties ────────────────────────────────


class TestTickTickClient:
    def test_v1_property_raises_when_not_configured(self) -> None:
        from ticktick_cli.api.client import TickTickClient

        client = TickTickClient(v2_cookies={"t": "s"})
        assert client.has_v1 is False
        with pytest.raises(AuthenticationError, match="V1 API not configured"):
            _ = client.v1

    def test_v2_property_raises_when_not_configured(self) -> None:
        from ticktick_cli.api.client import TickTickClient

        client = TickTickClient(v1_access_token="tok")
        assert client.has_v2 is False
        with pytest.raises(AuthenticationError, match="V2 API not configured"):
            _ = client.v2

    def test_has_both(self) -> None:
        from ticktick_cli.api.client import TickTickClient

        client = TickTickClient(v1_access_token="tok", v2_cookies={"t": "s"})
        assert client.has_v1 is True
        assert client.has_v2 is True
