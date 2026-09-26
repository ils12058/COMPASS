"""OpenAPI enum types generated from the code-owned canonical identity policy.

The members come from ``compass.accounts.policy`` so API schemas never keep a second, hand-written
copy of role, designation, capability, or Student lifecycle codes.
"""

from __future__ import annotations

from enum import Enum

from compass.accounts.models import StudentLifecycleStatus
from compass.accounts.policy import CAPABILITY_CODES, DESIGNATION_CODES, ROLE_CODES


def _code_enum(name: str, codes: frozenset[str]) -> type[Enum]:
    members = {code.replace(".", "_").replace("-", "_").upper(): code for code in sorted(codes)}
    return Enum(name, members, module=__name__, type=str)


RoleCode = _code_enum("RoleCode", ROLE_CODES)
DesignationCode = _code_enum("DesignationCode", DESIGNATION_CODES)
CapabilityCode = _code_enum("CapabilityCode", CAPABILITY_CODES)
StudentLifecycleCode = _code_enum("StudentLifecycleCode", frozenset(StudentLifecycleStatus.values))

__all__ = ["CapabilityCode", "DesignationCode", "RoleCode", "StudentLifecycleCode"]
