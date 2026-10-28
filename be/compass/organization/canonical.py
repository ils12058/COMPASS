"""Frozen V1 installation baseline; not a live catalog or policy authority."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from compass.organization.program_policy import AcademicClassification, YearLevelPolicyStatus

# Frozen installation input only. Never reconcile an adopted catalog against this version.
BASELINE_VERSION = "ucn-2026-09-27-v1"


@dataclass(frozen=True, slots=True)
class CanonicalProgram:
    code: str
    name: str
    academic_classification: AcademicClassification
    applicable_year_levels: tuple[int, ...] | None
    active: bool = True

    @property
    def year_level_policy_status(self) -> YearLevelPolicyStatus:
        return (
            YearLevelPolicyStatus.CONFIGURED
            if self.applicable_year_levels is not None
            else YearLevelPolicyStatus.PENDING_POLICY
        )


@dataclass(frozen=True, slots=True)
class CanonicalCollege:
    code: str
    name: str
    programs: tuple[CanonicalProgram, ...]
    active: bool = True


@dataclass(frozen=True, slots=True)
class CanonicalCampus:
    code: str
    name: str
    colleges: tuple[CanonicalCollege, ...]
    active: bool = True


def _bachelors(code: str, name: str) -> CanonicalProgram:
    return CanonicalProgram(
        code=code,
        name=name,
        academic_classification=AcademicClassification.BACHELORS,
        applicable_year_levels=(1, 2, 3, 4),
    )


def _masters(code: str, name: str) -> CanonicalProgram:
    return CanonicalProgram(
        code=code,
        name=name,
        academic_classification=AcademicClassification.MASTERS,
        applicable_year_levels=None,
    )


def _doctoral(code: str, name: str) -> CanonicalProgram:
    return CanonicalProgram(
        code=code,
        name=name,
        academic_classification=AcademicClassification.DOCTORAL,
        applicable_year_levels=None,
    )


CANONICAL_CAMPUSES = (
    CanonicalCampus(
        code="MAIN",
        name="Main Campus",
        colleges=(
            CanonicalCollege(
                code="CAS",
                name="College of Arts and Sciences",
                programs=(
                    _bachelors("BSDEVCOM", "Bachelor of Science in Development Communication"),
                    _bachelors("BSAM", "Bachelor of Science in Applied Mathematics"),
                    _bachelors("BSPSYCH", "Bachelor of Science in Psychology"),
                    _bachelors("BSBIOL", "Bachelor of Science in Biology"),
                    _bachelors("BAELS", "Bachelor of Arts in English Language Studies"),
                    _bachelors("BASOC", "Bachelor of Arts in Sociology"),
                ),
            ),
            CanonicalCollege(
                code="CBPA",
                name="College of Business and Public Administration",
                programs=(
                    _bachelors("BPA", "Bachelor of Public Administration"),
                    _bachelors("BSHM", "Bachelor of Science in Hospitality Management"),
                    _bachelors("BSA", "Bachelor of Science in Accountancy"),
                    _bachelors("BSOA", "Bachelor of Science in Office Administration"),
                    _bachelors("BSENTREP", "Bachelor of Science in Entrepreneurship"),
                    _bachelors("BSBA", "Bachelor of Science in Business Administration"),
                ),
            ),
            CanonicalCollege(
                code="COENG",
                name="College of Engineering",
                programs=(
                    _bachelors("BSCE", "Bachelor of Science in Civil Engineering"),
                    _bachelors("BSEE", "Bachelor of Science in Electrical Engineering"),
                    _bachelors("BSME", "Bachelor of Science in Mechanical Engineering"),
                ),
            ),
            CanonicalCollege(
                code="GS",
                name="Graduate School",
                programs=(
                    _doctoral("DBA", "Doctor in Business Administration"),
                    _doctoral("DPA", "Doctor of Public Administration"),
                    _doctoral("EDD", "Doctor of Education"),
                    _masters("MBA", "Master in Business Administration"),
                    _masters("MPA", "Master in Public Administration"),
                    _masters("MM", "Master in Management"),
                    _masters("MAED", "Master of Arts in Education"),
                ),
            ),
            CanonicalCollege(
                code="CCMS",
                name="College of Computing and Multimedia Studies",
                programs=(
                    _bachelors("BSIT", "Bachelor of Science in Information Technology"),
                    _bachelors("BSIS", "Bachelor of Science in Information Systems"),
                    _masters("MIT", "Master in Information Technology"),
                ),
            ),
        ),
    ),
    CanonicalCampus(
        code="ABANO",
        name="Abaño Campus",
        colleges=(
            CanonicalCollege(
                code="COED",
                name="College of Education",
                programs=(
                    _bachelors("BSED", "Bachelor of Secondary Education"),
                    _bachelors("BEED", "Bachelor of Elementary Education"),
                    _bachelors("BTLED", "Bachelor of Technology and Livelihood Education"),
                    _bachelors("BPED", "Bachelor of Physical Education"),
                ),
            ),
        ),
    ),
    CanonicalCampus(
        code="MERCEDES",
        name="Mercedes Campus",
        colleges=(
            CanonicalCollege(
                code="CFAST",
                name="College of Fisheries, Aquatic Sciences, and Technology",
                programs=(_bachelors("BSF", "Bachelor of Science in Fisheries"),),
            ),
        ),
    ),
    CanonicalCampus(
        code="LABO",
        name="Labo Campus",
        colleges=(
            CanonicalCollege(
                code="CANR",
                name="College of Agriculture and Natural Resources",
                programs=(
                    _bachelors("BSAGRI", "Bachelor of Science in Agriculture"),
                    _bachelors("BSES", "Bachelor of Science in Environmental Science"),
                    _bachelors(
                        "BSABE", "Bachelor of Science in Agricultural and Biosystems Engineering"
                    ),
                ),
            ),
        ),
    ),
    CanonicalCampus(
        code="PANGANIBAN",
        name="Jose Panganiban Campus",
        colleges=(
            CanonicalCollege(
                code="COTT",
                name="College of Trades and Technology",
                programs=(
                    _bachelors("BTVTED", "Bachelor of Technical-Vocational Teacher Education"),
                    _bachelors("BSINDTECH", "Bachelor of Science in Industrial Technology"),
                ),
            ),
        ),
    ),
    CanonicalCampus(
        code="ENTIENZA",
        name="Ret. Judge Antonio C. Entienza Campus",
        colleges=(
            CanonicalCollege(
                code="ENTIENZA",
                name="Ret. Judge Antonio C. Entienza Campus",
                programs=(
                    _bachelors("BSED", "Bachelor of Secondary Education"),
                    _bachelors("BEED", "Bachelor of Elementary Education"),
                    _bachelors("BSENTREP", "Bachelor of Science in Entrepreneurship"),
                ),
            ),
        ),
    ),
)


EXPECTED_CAMPUS_COUNT = 6
EXPECTED_COLLEGE_COUNT = 10
EXPECTED_PROGRAM_COUNT = 38


def _validate_registry() -> None:
    campus_codes: set[str] = set()
    college_count = 0
    program_count = 0

    for campus in CANONICAL_CAMPUSES:
        if not campus.code or not campus.name:
            raise RuntimeError("canonical Campus code and name are required")
        if len(campus.code) > 32 or len(campus.name) > 160:
            raise RuntimeError(f"canonical Campus exceeds DB limits: {campus.code}")
        if campus.code in campus_codes:
            raise RuntimeError(f"duplicate canonical Campus code: {campus.code}")
        campus_codes.add(campus.code)

        college_codes: set[str] = set()
        for college in campus.colleges:
            college_count += 1
            if not college.code or not college.name:
                raise RuntimeError(
                    f"canonical College code and name are required under {campus.code}"
                )
            if len(college.code) > 32 or len(college.name) > 160:
                raise RuntimeError(
                    f"canonical College exceeds DB limits: {campus.code}/{college.code}"
                )
            if college.code in college_codes:
                raise RuntimeError(
                    f"duplicate canonical College code: {campus.code}/{college.code}"
                )
            college_codes.add(college.code)

            program_codes: set[str] = set()
            for program in college.programs:
                program_count += 1
                if not program.code or not program.name:
                    raise RuntimeError(
                        f"canonical Program code and name are required under "
                        f"{campus.code}/{college.code}"
                    )
                if program.academic_classification == AcademicClassification.BACHELORS:
                    if program.applicable_year_levels != (1, 2, 3, 4):
                        raise RuntimeError(
                            "canonical Bachelor's Programs must support Year Levels 1 through 4"
                        )
                elif program.applicable_year_levels is not None:
                    raise RuntimeError(
                        "postgraduate Year Level policy must remain unconfigured until confirmed"
                    )
                if len(program.code) > 32 or len(program.name) > 160:
                    raise RuntimeError(
                        f"canonical Program exceeds DB limits: "
                        f"{campus.code}/{college.code}/{program.code}"
                    )
                if program.code in program_codes:
                    raise RuntimeError(
                        f"duplicate canonical Program code: "
                        f"{campus.code}/{college.code}/{program.code}"
                    )
                program_codes.add(program.code)

    if len(CANONICAL_CAMPUSES) != EXPECTED_CAMPUS_COUNT:
        raise RuntimeError("canonical Organization registry must contain exactly 6 Campuses")
    if college_count != EXPECTED_COLLEGE_COUNT:
        raise RuntimeError("canonical Organization registry must contain exactly 10 academic units")
    if program_count != EXPECTED_PROGRAM_COUNT:
        raise RuntimeError("canonical Organization registry must contain exactly 38 base Programs")


_validate_registry()

CANONICAL_CAMPUS_BY_CODE: Mapping[str, CanonicalCampus] = MappingProxyType(
    {campus.code: campus for campus in CANONICAL_CAMPUSES}
)
CANONICAL_CAMPUS_CODES = frozenset(CANONICAL_CAMPUS_BY_CODE)
CANONICAL_COLLEGE_IDENTITIES = frozenset(
    (campus.code, college.code) for campus in CANONICAL_CAMPUSES for college in campus.colleges
)
CANONICAL_PROGRAM_IDENTITIES = frozenset(
    (campus.code, college.code, program.code)
    for campus in CANONICAL_CAMPUSES
    for college in campus.colleges
    for program in college.programs
)
CANONICAL_PROGRAM_BY_IDENTITY: Mapping[tuple[str, str, str], CanonicalProgram] = MappingProxyType(
    {
        (campus.code, college.code, program.code): program
        for campus in CANONICAL_CAMPUSES
        for college in campus.colleges
        for program in college.programs
    }
)


def canonical_program_metadata(
    campus_code: str, college_code: str, program_code: str
) -> CanonicalProgram | None:
    """Seed/fixture metadata only; live consumers must use get_program_policy."""
    return CANONICAL_PROGRAM_BY_IDENTITY.get((campus_code, college_code, program_code))
