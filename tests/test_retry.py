"""Test retry logic and response handling in base HTTP client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from ticktick_cli.api.base import (
    _BACKOFF_BASE,
    _DEFAULT_MIN_REQUEST_INTERVAL,
    _MAX_RETRIES,
    _RETRYABLE_STATUS,
    BaseClient,
)
from ticktick_cli.exceptions import APIError, AuthenticationError, NotFoundError, RateLimitError


class TestHandleResponse:
    """Test _handle_response error mapping."""

    def _make_response(self, status_code: int, text: str = "", json_data: dict | None = None) -> MagicMock:
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.text = text
        resp.content = text.encode() if text else (b'{}' if json_data else b'')
        resp.json.return_value = json_data or {}
        resp.headers = {}
        return resp

    def test_401_raises_auth_error(self) -> None:
        client = BaseClient("https://example.com")
        with pytest.raises(AuthenticationError, match="401"):
            client._handle_response(self._make_response(401), "/test")

    def test_429_raises_rate_limit(self) -> None:
        client = BaseClient("https://example.com")
        with pytest.raises(RateLimitError, match="429") as exc_info:
            client._handle_response(self._make_response(429), "/test")
        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after_seconds is None

    def test_429_preserves_retry_after_header(self) -> None:
        client = BaseClient("https://example.com")
        response = self._make_response(429)
        response.headers = {"Retry-After": "42"}

        with pytest.raises(RateLimitError, match="Retry after 42s") as exc_info:
            client._handle_response(response, "/test")

        assert exc_info.value.retry_after_seconds == 42

    def test_404_raises_not_found(self) -> None:
        client = BaseClient("https://example.com")
        with pytest.raises(NotFoundError, match="/test"):
            client._handle_response(self._make_response(404), "/test")

    def test_500_raises_api_error(self) -> None:
        client = BaseClient("https://example.com")
        with pytest.raises(APIError, match="500"):
            client._handle_response(self._make_response(500, text="Internal Server Error"), "/test")

    def test_204_returns_empty_dict(self) -> None:
        client = BaseClient("https://example.com")
        result = client._handle_response(self._make_response(204), "/test")
        assert result == {}

    def test_200_returns_json(self) -> None:
        client = BaseClient("https://example.com")
        resp = self._make_response(200, text='{"key": "value"}', json_data={"key": "value"})
        result = client._handle_response(resp, "/test")
        assert result == {"key": "value"}

    def test_error_body_truncated(self) -> None:
        client = BaseClient("https://example.com")
        long_body = "x" * 500
        with pytest.raises(APIError) as exc_info:
            client._handle_response(self._make_response(400, text=long_body), "/test")
        assert len(exc_info.value.response_body) <= 200


class TestRetryLogic:
    """Test retry with exponential backoff."""

    def test_success_on_first_attempt(self) -> None:
        client = BaseClient("https://example.com")
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b'{"ok": true}'
        mock_resp.json.return_value = {"ok": True}
        with patch.object(client._http, "request", return_value=mock_resp):
            result = client._request("GET", "/test")
        assert result == {"ok": True}

    @patch("ticktick_cli.api.base.time.sleep")
    def test_retries_on_429_with_retry_after(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 429
        bad_resp.headers = {"Retry-After": "5"}
        good_resp = MagicMock(spec=httpx.Response)
        good_resp.status_code = 200
        good_resp.content = b'{"ok": true}'
        good_resp.json.return_value = {"ok": True}

        with patch.object(client._http, "request", side_effect=[bad_resp, good_resp]):
            result = client._request("GET", "/test")

        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(5.0)

    @patch("ticktick_cli.api.base.time.sleep")
    @patch("ticktick_cli.api.base.time.monotonic")
    def test_throttles_sequential_first_attempts(
        self,
        mock_monotonic: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        client = BaseClient("https://example.com", min_request_interval=0.5)
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.content = b'{}'
        mock_resp.json.return_value = {}
        mock_monotonic.side_effect = [100.0, 100.1, 100.5]

        with patch.object(client._http, "request", return_value=mock_resp):
            client._request("GET", "/one")
            client._request("GET", "/two")

        mock_sleep.assert_called_once_with(pytest.approx(0.4))

    @patch("ticktick_cli.api.base.time.sleep")
    @patch("ticktick_cli.api.base.time.monotonic")
    def test_retry_backoff_is_not_double_throttled(
        self,
        mock_monotonic: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        client = BaseClient("https://example.com", min_request_interval=10.0)
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 429
        bad_resp.headers = {"Retry-After": "5"}
        good_resp = MagicMock(spec=httpx.Response)
        good_resp.status_code = 200
        good_resp.content = b'{}'
        good_resp.json.return_value = {}
        mock_monotonic.side_effect = [100.0, 100.1]

        with patch.object(client._http, "request", side_effect=[bad_resp, good_resp]):
            client._request("GET", "/test")

        mock_sleep.assert_called_once_with(5.0)

    def test_min_request_interval_can_be_disabled_by_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TICKTICK_MIN_REQUEST_INTERVAL", "0")
        client = BaseClient("https://example.com")

        assert client._min_request_interval == 0

    @patch("ticktick_cli.api.base.time.sleep")
    def test_retries_on_429_without_retry_after_uses_backoff(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 429
        bad_resp.headers = {}
        good_resp = MagicMock(spec=httpx.Response)
        good_resp.status_code = 200
        good_resp.content = b'{"ok": true}'
        good_resp.json.return_value = {"ok": True}

        with patch.object(client._http, "request", side_effect=[bad_resp, good_resp]):
            result = client._request("GET", "/test")

        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(_BACKOFF_BASE)

    @patch("ticktick_cli.api.base.time.sleep")
    def test_exhausted_429_preserves_retry_after(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 429
        bad_resp.text = ""
        bad_resp.headers = {"Retry-After": "7"}

        with patch.object(client._http, "request", return_value=bad_resp):
            with pytest.raises(RateLimitError) as exc_info:
                client._request("GET", "/test")

        assert mock_sleep.call_count == _MAX_RETRIES - 1
        assert [c.args[0] for c in mock_sleep.call_args_list] == [7.0, 7.0]
        assert exc_info.value.retry_after_seconds == 7

    @patch("ticktick_cli.api.base.time.sleep")
    def test_retries_on_502(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 502
        good_resp = MagicMock(spec=httpx.Response)
        good_resp.status_code = 200
        good_resp.content = b'{"ok": true}'
        good_resp.json.return_value = {"ok": True}

        with patch.object(client._http, "request", side_effect=[bad_resp, good_resp]):
            result = client._request("GET", "/test")

        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(_BACKOFF_BASE * (2 ** 0))

    @patch("ticktick_cli.api.base.time.sleep")
    def test_retries_on_503(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 503
        good_resp = MagicMock(spec=httpx.Response)
        good_resp.status_code = 200
        good_resp.content = b'{}'
        good_resp.json.return_value = {}

        with patch.object(client._http, "request", side_effect=[bad_resp, good_resp]):
            client._request("GET", "/test")

        mock_sleep.assert_called_once()

    @patch("ticktick_cli.api.base.time.sleep")
    def test_retries_on_connect_error(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        good_resp = MagicMock(spec=httpx.Response)
        good_resp.status_code = 200
        good_resp.content = b'{"ok": true}'
        good_resp.json.return_value = {"ok": True}

        with patch.object(
            client._http, "request",
            side_effect=[httpx.ConnectError("Connection refused"), good_resp],
        ):
            result = client._request("GET", "/test")

        assert result == {"ok": True}
        mock_sleep.assert_called_once()

    @patch("ticktick_cli.api.base.time.sleep")
    def test_retries_on_read_timeout(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        good_resp = MagicMock(spec=httpx.Response)
        good_resp.status_code = 200
        good_resp.content = b'{}'
        good_resp.json.return_value = {}

        with patch.object(
            client._http, "request",
            side_effect=[httpx.ReadTimeout("Read timed out"), good_resp],
        ):
            client._request("GET", "/test")

        mock_sleep.assert_called_once()

    @patch("ticktick_cli.api.base.time.sleep")
    def test_exhausts_retries_raises_api_error(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        with patch.object(
            client._http, "request",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(APIError, match=f"after {_MAX_RETRIES} retries"):
                client._request("GET", "/test")

        assert mock_sleep.call_count == _MAX_RETRIES

    @patch("ticktick_cli.api.base.time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep: MagicMock) -> None:
        client = BaseClient("https://example.com")

        with patch.object(
            client._http, "request",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(APIError):
                client._request("GET", "/test")

        calls = [c.args[0] for c in mock_sleep.call_args_list]
        for i, wait in enumerate(calls):
            assert wait == pytest.approx(_BACKOFF_BASE * (2 ** i))

    @patch("ticktick_cli.api.base.time.sleep")
    def test_non_retryable_status_not_retried(self, mock_sleep: MagicMock) -> None:
        """400 errors should NOT be retried."""
        client = BaseClient("https://example.com")
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 400
        bad_resp.text = "Bad request"
        bad_resp.content = b"Bad request"

        with patch.object(client._http, "request", return_value=bad_resp):
            with pytest.raises(APIError, match="400"):
                client._request("GET", "/test")

        mock_sleep.assert_not_called()

    @patch("ticktick_cli.api.base.time.sleep")
    def test_last_502_still_handled(self, mock_sleep: MagicMock) -> None:
        """On last attempt, 502 should be passed to _handle_response (which raises APIError)."""
        client = BaseClient("https://example.com")
        bad_resp = MagicMock(spec=httpx.Response)
        bad_resp.status_code = 502
        bad_resp.text = "Bad gateway"
        bad_resp.content = b"Bad gateway"

        with patch.object(client._http, "request", return_value=bad_resp):
            with pytest.raises(APIError, match="502"):
                client._request("GET", "/test")


class TestRetryableConstants:
    """Verify retry configuration values."""

    def test_retryable_statuses(self) -> None:
        assert {502, 503, 504} == _RETRYABLE_STATUS

    def test_max_retries(self) -> None:
        assert _MAX_RETRIES == 3

    def test_backoff_base(self) -> None:
        assert _BACKOFF_BASE == 1.0

    def test_default_min_request_interval(self) -> None:
        assert _DEFAULT_MIN_REQUEST_INTERVAL == 0.25
