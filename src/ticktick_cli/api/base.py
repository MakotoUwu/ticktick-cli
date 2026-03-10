"""Base HTTP client with shared transport logic for V1 and V2 APIs."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ticktick_cli.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


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
        """Central request method with error handling."""
        headers = self._get_auth_headers()
        logger.debug("%s %s%s", method, self._base_url, path)

        response = self._http.request(
            method,
            path,
            headers=headers,
            params=params,
            json=json_data,
        )

        if response.status_code == 401:
            raise AuthenticationError(
                "Authentication failed (401). Run `ticktick auth login` first."
            )
        if response.status_code == 429:
            raise RateLimitError("API rate limit exceeded (429). Try again later.")
        if response.status_code == 404:
            raise NotFoundError(f"Resource not found: {path}", status_code=404)
        if response.status_code >= 400:
            # Truncate response body to avoid leaking sensitive data in error messages
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
