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


class TierError(MonopigiError):
    """Raised when accessing an endpoint that requires a higher tier."""

    def __init__(self, required_tier: str, current_tier: str, endpoint: str) -> None:
        self.required_tier = required_tier
        self.current_tier = current_tier
        self.endpoint = endpoint
        super().__init__(
            f"Endpoint '{endpoint}' requires {required_tier} tier or higher. "
            f"Your current tier is {current_tier}. "
            f"Upgrade at https://monopigi.com/dashboard/billing"
        )
