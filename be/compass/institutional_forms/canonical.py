"""Code-owned institutional form identities supported by this COMPASS version."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class CanonicalFormRevision:
    official_code: str
    official_revision: str
    internal_schema_version: int
    active: bool


@dataclass(frozen=True, slots=True)
class CanonicalFormFamily:
    key: str
    title: str
    supported_schema_versions: frozenset[int]
    revisions: tuple[CanonicalFormRevision, ...] = ()


CANONICAL_FORM_FAMILIES = (
    CanonicalFormFamily(
        key="individual_inventory",
        title="Individual Inventory",
        supported_schema_versions=frozenset({1}),
        revisions=(
            CanonicalFormRevision(
                official_code="CNSC-OP-GCO-01F5",
                official_revision="0",
                internal_schema_version=1,
                active=True,
            ),
        ),
    ),
    CanonicalFormFamily(
        key="routine_interview",
        title="Routine Interview Form",
        supported_schema_versions=frozenset({1}),
    ),
    CanonicalFormFamily(
        key="referral_slip",
        title="Referral Slip",
        supported_schema_versions=frozenset({1}),
        revisions=(
            CanonicalFormRevision(
                official_code="CNSC-OP-GTA-01F9",
                official_revision="1",
                internal_schema_version=1,
                active=True,
            ),
        ),
    ),
    CanonicalFormFamily(
        key="call_slip",
        title="Interview Permit / Call Slip",
        supported_schema_versions=frozenset({1}),
        revisions=(
            CanonicalFormRevision(
                official_code="CNSC-OP-GTA-01F8",
                official_revision="0",
                internal_schema_version=1,
                active=True,
            ),
        ),
    ),
    CanonicalFormFamily(
        key="good_moral_current_student",
        title="Good Moral Character — Current Student",
        supported_schema_versions=frozenset({1}),
        revisions=(
            CanonicalFormRevision(
                official_code="CNSC-OP-GCO-01F4",
                official_revision="0",
                internal_schema_version=1,
                active=True,
            ),
        ),
    ),
    CanonicalFormFamily(
        key="good_moral_graduate",
        title="Good Moral Character — Graduate",
        supported_schema_versions=frozenset({1}),
        revisions=(
            CanonicalFormRevision(
                official_code="CNSC-OP-GCO-01F6",
                official_revision="0",
                internal_schema_version=1,
                active=True,
            ),
        ),
    ),
    CanonicalFormFamily(
        key="customer_feedback",
        title="Customer Feedback Form",
        supported_schema_versions=frozenset({1}),
        revisions=(
            CanonicalFormRevision(
                official_code="CNSC-OP-GTA-01F14",
                official_revision="0",
                internal_schema_version=1,
                active=True,
            ),
        ),
    ),
)


def _validate_registry() -> None:
    keys: set[str] = set()
    for family in CANONICAL_FORM_FAMILIES:
        if family.key in keys:
            raise RuntimeError(f"duplicate canonical Form Family key: {family.key}")
        keys.add(family.key)
        if not family.key or not family.title or not family.supported_schema_versions:
            raise RuntimeError(f"invalid canonical Form Family definition: {family.key}")

        identities: set[tuple[str, str]] = set()
        active_count = 0
        for revision in family.revisions:
            identity = (revision.official_code, revision.official_revision)
            if not all(identity) or identity in identities:
                raise RuntimeError(f"invalid canonical Form Revision identity for {family.key}")
            identities.add(identity)
            if revision.internal_schema_version not in family.supported_schema_versions:
                raise RuntimeError(
                    f"canonical revision schema is not supported by its family: {family.key}"
                )
            active_count += int(revision.active)
        if active_count > 1:
            raise RuntimeError(f"multiple active canonical revisions defined for {family.key}")


_validate_registry()

CANONICAL_FORM_FAMILY_BY_KEY: Mapping[str, CanonicalFormFamily] = MappingProxyType(
    {family.key: family for family in CANONICAL_FORM_FAMILIES}
)
CANONICAL_FORM_FAMILY_KEYS = frozenset(CANONICAL_FORM_FAMILY_BY_KEY)


def get_canonical_form_family(family_key: str) -> CanonicalFormFamily | None:
    return CANONICAL_FORM_FAMILY_BY_KEY.get(family_key)


def get_canonical_form_revision(
    *,
    family_key: str,
    official_code: str | None,
    official_revision: str | None,
    internal_schema_version: int,
) -> CanonicalFormRevision | None:
    family = get_canonical_form_family(family_key)
    if family is None or official_code is None or official_revision is None:
        return None
    return next(
        (
            revision
            for revision in family.revisions
            if revision.official_code == official_code
            and revision.official_revision == official_revision
            and revision.internal_schema_version == internal_schema_version
        ),
        None,
    )


def supported_schema_versions(family_key: str) -> frozenset[int]:
    family = get_canonical_form_family(family_key)
    return family.supported_schema_versions if family is not None else frozenset()
