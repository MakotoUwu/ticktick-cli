"""Custom exceptions for TickTick CLI.

Exit code semantics:
    0 — Success
    1 — General error
    2 — Usage / input error
    3 — Authentication failure
    4 — Resource not found
    5 — Rate limited (transient, safe to retry)
    6 — Conflict / resource already exists
"""

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

    exit_code = 3


class APIError(TickTickCLIError):
    """TickTick API returned an error."""

    exit_code = 1

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

    exit_code = 4


class RateLimitError(APIError):
    """Rate limit exceeded (429)."""

    exit_code = 5


class ConflictError(APIError):
    """Conflict — resource already exists (409)."""

    exit_code = 6


class ConfigError(TickTickCLIError):
    """Configuration error."""

    exit_code = 1


def _exit_code_suggestion(error: TickTickCLIError) -> str | None:
    """Return an actionable suggestion string based on error type."""
    if isinstance(error, AuthenticationError):
        return "Run `ticktick auth login` or `ticktick auth login-v2` to authenticate."
    if isinstance(error, RateLimitError):
        return "Rate limited — wait a moment and retry the request."
    if isinstance(error, ConflictError):
        return "A resource with the same identifier already exists."
    if isinstance(error, NotFoundError):
        return "Verify the resource ID is correct and that it has not been deleted."
    return None


def handle_cli_error(error: TickTickCLIError) -> None:
    """Print error as JSON and exit with appropriate code."""
    import json

    output: dict[str, object] = {
        "ok": False,
        "error": str(error),
        "error_type": type(error).__name__,
        "exit_code": error.exit_code,
    }
    if isinstance(error, APIError) and error.status_code:
        output["status_code"] = error.status_code
    suggestion = _exit_code_suggestion(error)
    if suggestion:
        output["suggestion"] = suggestion
    print(json.dumps(output), file=sys.stderr)
    sys.exit(error.exit_code)
