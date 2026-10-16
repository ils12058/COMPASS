"""Synthetic identity specifications for Staging Dataset v1, independent of scenario data.

Account state, authentication state, Student lifecycle and UAT suitability are declared
separately on purpose: none of them implies another.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class AuthPlan(StrEnum):
    """How the seeder provisions authentication. Credentials are never set by seeding."""

    # Active, email verified, no usable password. ``issue-credentials`` makes it sign-in ready.
    CREDENTIAL = "CREDENTIAL"
    # Active, email unverified, no password: first sign-in uses normal Password Access onboarding.
    ONBOARDING = "ONBOARDING"
    # Provisioned, then disabled through the Account Management invariants.
    DISABLED = "DISABLED"


class Suitability(StrEnum):
    # Intended for assignment to one UAT evaluator.
    PARTICIPANT = "UAT_READY"
    # Populates the environment; never assigned to an evaluator as delivered.
    BACKGROUND = "BACKGROUND"
    # Negative-authorization or lifecycle evidence only; never assigned for ordinary workflows.
    RESTRICTED = "RESTRICTED"


class Lifecycle(StrEnum):
    CURRENT = "CURRENT"
    GRADUATED = "GRADUATED"
    FORMER = "FORMER"


class StudentGroup(StrEnum):
    RICH = "RICH_SCENARIO"
    ACTION_READY = "ACTION_READY"
    BACKGROUND = "BACKGROUND"


@dataclass(frozen=True)
class AccountSpec:
    key: str
    label: str
    institutional_id: str
    email_local_part: str
    first_name: str
    middle_name: str
    last_name: str
    role: str
    designations: tuple[str, ...] = ()
    auth: AuthPlan = AuthPlan.CREDENTIAL
    suitability: Suitability = Suitability.PARTICIPANT
    # Human-readable catalog fields. They describe intent; verification proves the state.
    summary: str = ""
    limitations: str = ""

    @property
    def full_name(self) -> str:
        return " ".join(
            part for part in (self.first_name, self.middle_name, self.last_name) if part
        )

    @property
    def active(self) -> bool:
        return self.auth != AuthPlan.DISABLED

    @property
    def is_student(self) -> bool:
        return self.role == "STUDENT"


@dataclass(frozen=True)
class StudentSpec(AccountSpec):
    role: str = "STUDENT"
    group: StudentGroup = StudentGroup.BACKGROUND
    sex: str = ""
    date_of_birth: date | None = None
    campus_code: str = ""
    college_code: str = ""
    program_code: str = ""
    # Lifecycle the Student ends with; historical back-entry runs while the Student was CURRENT.
    lifecycle: Lifecycle = Lifecycle.CURRENT
    # Graduated and former Students keep no current College affiliation.
    affiliated: bool = True
    civil_status: str = "Single"
    home_address: str = ""
    # Year level in each Academic Year the Student submitted (or drafted) an Inventory.
    year_levels: tuple[tuple[str, int], ...] = ()
    # Lightweight-population content selectors (see content.inventory_population).
    inventory_state: str = "SUBMITTED"
    background: str = "ordinary"
    tracer: str = "missing"
    # A stable ordinal for deterministic content variation; never derived from the key text.
    ordinal: int = 0
    # Declared year level: current enrollment, or the last enrolled year for graduates/former
    # Students. Independent of whether an Inventory records it.
    enrolled_year_level: int | None = None

    @property
    def current_year_level(self) -> int | None:
        return dict(self.year_levels).get("2026-2027") or (
            self.enrolled_year_level if self.lifecycle == Lifecycle.CURRENT else None
        )


__all__ = [
    "AccountSpec",
    "AuthPlan",
    "Lifecycle",
    "StudentGroup",
    "StudentSpec",
    "Suitability",
]
