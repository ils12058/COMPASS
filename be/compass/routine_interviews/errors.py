"""Routine Interview domain errors shared by the crypto, content, and service layers."""

from __future__ import annotations

from uuid import UUID


class RoutineInterviewError(RuntimeError):
    pass


class RoutineContentUnavailable(RoutineInterviewError):
    """Stored Routine content could not be decrypted or verified, so it is never returned.

    The attributes are safe operational context only. The message is deliberately generic and
    never includes plaintext, ciphertext, key material, or key order.
    """

    def __init__(self, *, routine_interview_id: UUID, section: str, reason: str) -> None:
        super().__init__("The Routine Interview content is unavailable.")
        self.routine_interview_id = routine_interview_id
        self.section = str(section)
        self.reason = reason
