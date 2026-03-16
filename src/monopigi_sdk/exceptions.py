"""SDK exceptions."""


class MonopigiError(Exception):
    """Base exception for all Monopigi SDK errors."""


class AuthError(MonopigiError):
    """Invalid or missing API token."""


class RateLimitError(MonopigiError):
    """Daily query quota exceeded."""

    def __init__(self, message: str, reset_at: str = "") -> None:
        super().__init__(message)
        self.reset_at = reset_at


class NotFoundError(MonopigiError):
    """Requested resource not found (unknown source, etc.)."""
