"""Base HTTP client with shared transport logic for V1 and V2 APIs."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ticktick_cli.exceptions import (
    APIError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# Retry config: transient errors that are safe to retry
_RETRYABLE_STATUS = {502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds: 1s, 2s, 4s


class BaseClient:
    """Shared HTTP transport for both V1 and V2 APIs."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Override in subclass to provide auth headers."""
        return {}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_data: Any = None,
    ) -> Any:
        """Central request method with error handling and retry."""
        headers = self._get_auth_headers()
        logger.debug("%s %s%s", method, self._base_url, path)

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._http.request(
                    method,
                    path,
                    headers=headers,
                    params=params,
                    json=json_data,
                )
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                wait = _BACKOFF_BASE * (2 ** attempt)
                logger.warning("Request failed (attempt %d/%d): %s — retrying in %.1fs",
                               attempt + 1, _MAX_RETRIES, exc, wait)
                time.sleep(wait)
                continue

            # Retry on transient server errors
            if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                wait = _BACKOFF_BASE * (2 ** attempt)
                logger.warning("HTTP %d (attempt %d/%d) — retrying in %.1fs",
                               response.status_code, attempt + 1, _MAX_RETRIES, wait)
                time.sleep(wait)
                continue

            return self._handle_response(response, path)

        # All retries exhausted
        raise APIError(f"Request failed after {_MAX_RETRIES} retries: {last_exc}") from last_exc

    def _handle_response(self, response: httpx.Response, path: str) -> Any:
        """Parse response, raising typed exceptions for error codes."""
        if response.status_code == 401:
            raise AuthenticationError(
                "Authentication failed (401). Run `ticktick auth login` first."
            )
        if response.status_code == 429:
            raise RateLimitError("API rate limit exceeded (429). Try again later.")
        if response.status_code == 404:
            raise NotFoundError(f"Resource not found: {path}", status_code=404)
        if response.status_code == 409:
            body = response.text[:200] if response.text else ""
            raise ConflictError(
                f"Conflict (409): {body}",
                status_code=409,
                response_body=body,
            )
        if response.status_code >= 400:
            body = response.text[:200] if response.text else ""
            raise APIError(
                f"API error {response.status_code}: {body}",
                status_code=response.status_code,
                response_body=body,
            )

        if response.status_code == 204 or not response.content:
            return {}

        return response.json()

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self._request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BaseClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
