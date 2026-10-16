"""Code-owned retention policy register: read-only oversight metadata, never enforcement (ADR-115).

Each entry records what COMPASS knows about the institutional retention policy for one record
category. Changing an entry requires an authorized institutional policy source and a reviewed
code change; code ownership is implementation ownership, and developers do not decide University
retention periods. No database row, setting, environment variable, capability, or API request
can change the register.

The register never queries records, computes eligibility, creates disposition cases, schedules
tasks, anonymizes, or deletes anything. Adopting an entry changes only what oversight displays.

``NOT_ADOPTED`` means no adopted policy has been verified and recorded in COMPASS for that
category. It is not a statement that the University has no applicable records policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

MAX_LABEL_LENGTH = 160
MAX_TEXT_LENGTH = 500


class RetentionPolicyCategory(StrEnum):
    GRADUATE_TRACER = "GRADUATE_TRACER"
    ECOUNSELING_RECORDING = "ECOUNSELING_RECORDING"
    ECOUNSELING_TRANSCRIPT = "ECOUNSELING_TRANSCRIPT"


class RetentionAdoptionStatus(StrEnum):
    NOT_ADOPTED = "NOT_ADOPTED"
    ADOPTED = "ADOPTED"


class RetentionPolicyRegisterError(ValueError):
    """The code-owned register is malformed, so COMPASS refuses to load it."""


def _text(value, field, limit):
    if type(value) is not str or not value.strip() or value != value.strip():
        raise RetentionPolicyRegisterError(f"{field} must be nonblank text without padding")
    if len(value) > limit:
        raise RetentionPolicyRegisterError(f"{field} must be at most {limit} characters")


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    category_code: RetentionPolicyCategory
    category_label: str
    adoption_status: RetentionAdoptionStatus
    # Verbatim wording of the adopted schedule item; never parsed or evaluated.
    retention_period: str | None = None
    policy_reference: str | None = None
    effective_date: date | None = None

    def __post_init__(self):
        if type(self.category_code) is not RetentionPolicyCategory:
            raise RetentionPolicyRegisterError("category_code must be a RetentionPolicyCategory")
        if type(self.adoption_status) is not RetentionAdoptionStatus:
            raise RetentionPolicyRegisterError("adoption_status must be a RetentionAdoptionStatus")
        _text(self.category_label, "category_label", MAX_LABEL_LENGTH)
        terms = (self.retention_period, self.policy_reference, self.effective_date)
        if self.adoption_status is RetentionAdoptionStatus.NOT_ADOPTED:
            # No placeholder period, reference, or date: nothing may suggest adoption or deletion.
            if any(value is not None for value in terms):
                raise RetentionPolicyRegisterError(
                    f"{self.category_code} is not adopted, so it records no period, "
                    "reference, or effective date"
                )
            return
        # ADOPTED needs the complete institutional terms. Code can require them; it cannot
        # verify that the approval is genuine, so the reviewed change must cite its source.
        _text(self.retention_period, "retention_period", MAX_TEXT_LENGTH)
        _text(self.policy_reference, "policy_reference", MAX_TEXT_LENGTH)
        if type(self.effective_date) is not date:
            raise RetentionPolicyRegisterError("an adopted policy requires an effective_date")


def validate_register(entries):
    if type(entries) is not tuple or not entries:
        raise RetentionPolicyRegisterError("the register must be a nonempty tuple")
    codes = []
    for entry in entries:
        if type(entry) is not RetentionPolicy:
            raise RetentionPolicyRegisterError("every register entry must be a RetentionPolicy")
        codes.append(entry.category_code)
    if len(set(codes)) != len(codes):
        raise RetentionPolicyRegisterError("each category appears in the register once")
    return entries


# One entry per record category the former in-app engine covered. Legacy contract versions,
# triggers, durations and actions are not carried over; they were never institutional policy.
REGISTER: tuple[RetentionPolicy, ...] = validate_register(
    (
        RetentionPolicy(
            category_code=RetentionPolicyCategory.GRADUATE_TRACER,
            category_label="Graduate Tracer responses",
            adoption_status=RetentionAdoptionStatus.NOT_ADOPTED,
        ),
        RetentionPolicy(
            category_code=RetentionPolicyCategory.ECOUNSELING_RECORDING,
            category_label="E-Counseling recordings",
            adoption_status=RetentionAdoptionStatus.NOT_ADOPTED,
        ),
        RetentionPolicy(
            category_code=RetentionPolicyCategory.ECOUNSELING_TRANSCRIPT,
            category_label="E-Counseling transcripts",
            adoption_status=RetentionAdoptionStatus.NOT_ADOPTED,
        ),
    )
)


def project(entry):
    return {
        "category_code": entry.category_code,
        "category_label": entry.category_label,
        "adoption_status": entry.adoption_status,
        "retention_period": entry.retention_period,
        "policy_reference": entry.policy_reference,
        "effective_date": entry.effective_date,
    }
