"""Custom exceptions for TickTick CLI."""

from __future__ import annotations

import sys


class TickTickCLIError(Exception):
    """Base exception for all CLI errors."""

    exit_code: int = 1

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class AuthenticationError(TickTickCLIError):
    """Authentication failed or missing credentials."""

    exit_code = 2


class APIError(TickTickCLIError):
    """TickTick API returned an error."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class NotFoundError(APIError):
    """Resource not found (404)."""


class RateLimitError(APIError):
    """Rate limit exceeded (429)."""


class ConfigError(TickTickCLIError):
    """Configuration error."""


def handle_cli_error(error: TickTickCLIError) -> None:
    """Print error as JSON and exit with appropriate code."""
    import json

    output = {
        "ok": False,
        "error": str(error),
        "error_type": type(error).__name__,
    }
    if isinstance(error, APIError) and error.status_code:
        output["status_code"] = error.status_code
    print(json.dumps(output), file=sys.stderr)
    sys.exit(error.exit_code)
