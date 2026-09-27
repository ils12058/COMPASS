"""Code-owned UCN organization catalog used by this COMPASS version."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class CanonicalProgram:
    code: str
    name: str
    active: bool = True


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


def _program(code: str, name: str) -> CanonicalProgram:
    return CanonicalProgram(code=code, name=name)


CANONICAL_CAMPUSES = (
    CanonicalCampus(
        code="MAIN",
        name="Main Campus",
        colleges=(
            CanonicalCollege(
                code="CAS",
                name="College of Arts and Sciences",
                programs=(
                    _program("BSDEVCOM", "Bachelor of Science in Development Communication"),
                    _program("BSAM", "Bachelor of Science in Applied Mathematics"),
                    _program("BSPSYCH", "Bachelor of Science in Psychology"),
                    _program("BSBIOL", "Bachelor of Science in Biology"),
                    _program("BAELS", "Bachelor of Arts in English Language Studies"),
                    _program("BASOC", "Bachelor of Arts in Sociology"),
                ),
            ),
            CanonicalCollege(
                code="CBPA",
                name="College of Business and Public Administration",
                programs=(
                    _program("BPA", "Bachelor of Public Administration"),
                    _program("BSHM", "Bachelor of Science in Hospitality Management"),
                    _program("BSA", "Bachelor of Science in Accountancy"),
                    _program("BSOA", "Bachelor of Science in Office Administration"),
                    _program("BSENTREP", "Bachelor of Science in Entrepreneurship"),
                    _program("BSBA", "Bachelor of Science in Business Administration"),
                ),
            ),
            CanonicalCollege(
                code="COENG",
                name="College of Engineering",
                programs=(
                    _program("BSCE", "Bachelor of Science in Civil Engineering"),
                    _program("BSEE", "Bachelor of Science in Electrical Engineering"),
                    _program("BSME", "Bachelor of Science in Mechanical Engineering"),
                ),
            ),
            CanonicalCollege(
                code="GS",
                name="Graduate School",
                programs=(
                    _program("DBA", "Doctor in Business Administration"),
                    _program("DPA", "Doctor of Public Administration"),
                    _program("EDD", "Doctor of Education"),
                    _program("MBA", "Master in Business Administration"),
                    _program("MPA", "Master in Public Administration"),
                    _program("MM", "Master in Management"),
                    _program("MAED", "Master of Arts in Education"),
                ),
            ),
            CanonicalCollege(
                code="CCMS",
                name="College of Computing and Multimedia Studies",
                programs=(
                    _program("BSIT", "Bachelor of Science in Information Technology"),
                    _program("BSIS", "Bachelor of Science in Information Systems"),
                    _program("MIT", "Master in Information Technology"),
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
                    _program("BSED", "Bachelor of Secondary Education"),
                    _program("BEED", "Bachelor of Elementary Education"),
                    _program("BTLED", "Bachelor of Technology and Livelihood Education"),
                    _program("BPED", "Bachelor of Physical Education"),
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
                programs=(
                    _program("BSF", "Bachelor of Science in Fisheries"),
                ),
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
                    _program("BSAGRI", "Bachelor of Science in Agriculture"),
                    _program("BSES", "Bachelor of Science in Environmental Science"),
                    _program("BSABE", "Bachelor of Science in Agricultural and Biosystems Engineering"),
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
                    _program("BTVTED", "Bachelor of Technical-Vocational Teacher Education"),
                    _program("BSINDTECH", "Bachelor of Science in Industrial Technology"),
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
                    _program("BSED", "Bachelor of Secondary Education"),
                    _program("BEED", "Bachelor of Elementary Education"),
                    _program("BSENTREP", "Bachelor of Science in Entrepreneurship"),
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
                raise RuntimeError(f"canonical College code and name are required under {campus.code}")
            if len(college.code) > 32 or len(college.name) > 160:
                raise RuntimeError(f"canonical College exceeds DB limits: {campus.code}/{college.code}")
            if college.code in college_codes:
                raise RuntimeError(f"duplicate canonical College code: {campus.code}/{college.code}")
            college_codes.add(college.code)

            program_codes: set[str] = set()
            for program in college.programs:
                program_count += 1
                if not program.code or not program.name:
                    raise RuntimeError(
                        f"canonical Program code and name are required under "
                        f"{campus.code}/{college.code}"
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
    (campus.code, college.code)
    for campus in CANONICAL_CAMPUSES
    for college in campus.colleges
)
CANONICAL_PROGRAM_IDENTITIES = frozenset(
    (campus.code, college.code, program.code)
    for campus in CANONICAL_CAMPUSES
    for college in campus.colleges
    for program in college.programs
)
