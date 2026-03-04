"""ACP exception hierarchy."""


class ACPError(Exception):
    """Base ACP exception."""


class ACPValidationError(ACPError):
    """Raised when an ACP object fails JSON schema validation."""


class ACPStateError(ACPError):
    """Raised for invalid ACP state transitions."""


class ACPSplitError(ACPError):
    """Raised when split rules are invalid or cannot be applied."""


class ACPExpiredError(ACPError):
    """Raised when a negotiation or settlement is expired."""
