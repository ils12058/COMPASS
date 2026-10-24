"""Current persisted Program policy. No installation-registry fallback."""

from dataclasses import dataclass
from enum import StrEnum

from django.core.exceptions import ValidationError


class AcademicClassification(StrEnum):
    BACHELORS = "BACHELORS"
    MASTERS = "MASTERS"
    DOCTORAL = "DOCTORAL"


class YearLevelPolicyStatus(StrEnum):
    CONFIGURED = "CONFIGURED"
    PENDING_POLICY = "PENDING_POLICY"


def validate_program_policy(classification, status, levels) -> None:
    """Reject malformed input before Django field coercion; never normalize policy."""
    if classification is not None and (
        not isinstance(classification, str) or classification not in AcademicClassification
    ):
        raise ValidationError({"academic_classification": "Choose a supported classification."})
    if not isinstance(status, str) or status not in YearLevelPolicyStatus:
        raise ValidationError({"year_level_policy_status": "Choose a supported policy status."})
    if status == YearLevelPolicyStatus.PENDING_POLICY:
        if levels is not None:
            raise ValidationError(
                {"applicable_year_levels": "Pending policy requires null levels."}
            )
        return
    if classification is None:
        raise ValidationError(
            {"academic_classification": "Configured policy requires classification."}
        )
    if (
        not isinstance(levels, (list, tuple))
        or not levels
        or any(type(level) is not int or not 1 <= level <= 10 for level in levels)
        or tuple(levels) != tuple(sorted(set(levels)))
    ):
        raise ValidationError(
            {"applicable_year_levels": "Use sorted unique integers 1–10; empty is invalid."}
        )


@dataclass(frozen=True, slots=True)
class ProgramPolicy:
    academic_classification: AcademicClassification | None
    year_level_policy_status: YearLevelPolicyStatus
    applicable_year_levels: tuple[int, ...] | None


def get_program_policy(program) -> ProgramPolicy:
    """Read the record, including explicitly unresolved policy, without inferring identity."""
    validate_program_policy(
        program.academic_classification,
        program.year_level_policy_status,
        program.applicable_year_levels,
    )
    return ProgramPolicy(
        AcademicClassification(program.academic_classification)
        if program.academic_classification is not None
        else None,
        YearLevelPolicyStatus(program.year_level_policy_status),
        tuple(program.applicable_year_levels)
        if program.applicable_year_levels is not None
        else None,
    )
