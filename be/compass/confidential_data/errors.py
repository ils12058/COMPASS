"""Safe failures without content, tokens, keys, or domain context."""

from typing import Literal

UnavailableReason = Literal[
    "missing", "undecryptable", "malformed", "unsupported_schema", "binding_mismatch"
]


class ConfidentialDataUnavailable(RuntimeError):
    """Confidential content could not be authenticated and verified in full."""

    def __init__(self, *, reason: UnavailableReason) -> None:
        if reason not in {
            "missing",
            "undecryptable",
            "malformed",
            "unsupported_schema",
            "binding_mismatch",
        }:
            raise ValueError("Unsupported confidential-data failure reason")
        super().__init__("The confidential data is unavailable.")
        self.reason = reason
