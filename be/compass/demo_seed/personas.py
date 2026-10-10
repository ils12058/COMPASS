"""Shared demo identity specifications, independent of scenario and cohort data."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class AuthState(StrEnum):
    READY = "READY"  # usable password from DEMO_ACCOUNT_PASSWORD, email verified
    ONBOARDING = "ONBOARDING"  # provisioned only: no usable password, email unverified


class Lifecycle(StrEnum):
    CURRENT = "CURRENT"
    GRADUATED = "GRADUATED"
    FORMER = "FORMER"


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    institutional_id: str
    email_local_part: str
    first_name: str
    middle_name: str
    last_name: str
    role: str
    designations: tuple[str, ...] = ()
    auth_state: AuthState = AuthState.READY
    active: bool = True

    @property
    def full_name(self) -> str:
        return " ".join(
            part for part in (self.first_name, self.middle_name, self.last_name) if part
        )


@dataclass(frozen=True)
class StudentPersona(Persona):
    role: str = "STUDENT"
    sex: str = ""
    date_of_birth: date | None = None
    campus_code: str = ""
    college_code: str = ""
    program_code: str = ""
    # Lifecycle the persona ends with; historical back-entry runs while the Student was CURRENT.
    lifecycle: Lifecycle = Lifecycle.CURRENT
    # Graduated and former Students keep no current College affiliation.
    affiliated: bool = True
    civil_status: str = "Single"
    home_address: str = ""
    # Year level in each Academic Year the Student submitted (or drafted) an Inventory.
    year_levels: tuple[tuple[str, int], ...] = ()
