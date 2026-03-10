"""XAP exception hierarchy."""


class XAPError(Exception):
    """Base XAP exception."""


class XAPValidationError(XAPError):
    """Raised when an XAP object fails JSON schema validation."""


class XAPStateError(XAPError):
    """Raised for invalid XAP state transitions."""


class XAPSplitError(XAPError):
    """Raised when split rules are invalid or cannot be applied."""


class XAPExpiredError(XAPError):
    """Raised when a negotiation or settlement is expired."""
