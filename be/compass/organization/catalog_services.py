"""Protected definition management; stable identity, synchronous Audit, no generic PATCH.

No role grants are installed here. Basis is attributable operator evidence, not an
institutional approval workflow. Incomplete activation and pending F4 policy changes
remain fail-closed pending institutional decisions.
"""

from __future__ import annotations

import re
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError
from django.db.models import Q
from django.utils import timezone

from compass.accounts.models import User
from compass.accounts.policy import CATALOG_ELIGIBLE_ROLES
from compass.audit import actions
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent, AuditOutcome
from compass.audit.services import record_event
from compass.authentication.models import AuthSession, TOTPFactor
from compass.authentication.sessions import MFASetupRequired, require_recent_mfa
from compass.organization.integrity import catalog_gate
from compass.organization.models import (
    Campus,
    CatalogInitialization,
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
    normalize_code,
)
from compass.organization.program_policy import validate_program_policy

CatalogEntity = Campus | College | Program


class CatalogError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: int = 409, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


def _invalid(message):
    return CatalogError("invalid_catalog_request", message, status=422)


def _text(value, label, maximum):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > maximum
        or any(unicodedata.category(c).startswith("C") for c in value)
    ):
        raise _invalid(f"{label} must be nonblank plain text of at most {maximum} characters.")
    return value.strip()


def _code(value):
    value = normalize_code(_text(value, "Code", 32))
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,31}", value, flags=re.ASCII):
        raise _invalid("Code must use ASCII letters, digits, hyphens or underscores.")
    return value


def _boolean(value):
    if type(value) is not bool:
        raise _invalid("is_active must be a Boolean.")
    return value


def _policy(classification, status, levels):
    try:
        validate_program_policy(classification, status, levels)
    except ValidationError as exc:
        raise _invalid(
            "Supply a coherent classification, policy status and sorted unique levels 1–10."
        ) from exc
    return dict(
        academic_classification=classification,
        year_level_policy_status=status,
        applicable_year_levels=list(levels) if levels is not None else None,
    )


def _activation_policy(program):
    _policy(
        program.academic_classification,
        program.year_level_policy_status,
        program.applicable_year_levels,
    )
    if program.academic_classification is None or program.year_level_policy_status != "CONFIGURED":
        raise CatalogError(
            "catalog_policy_approval_required",
            "Incomplete Program policy cannot be activated. Resolve institutional policy first.",
        )


def require_catalog_manager(*, actor, actor_session=None, mutation=False, lock=False):
    """Reload authority and server-established session evidence instead of actor caches."""
    query = User.objects.select_related("role")
    if lock:
        query = query.select_for_update(of=("self",), no_key=True)
    current = query.filter(pk=getattr(actor, "pk", None), is_active=True).first()
    if (
        current is None
        or current.role.code not in CATALOG_ELIGIBLE_ROLES
        or not current.has_capability("organization.catalog.manage")
    ):
        raise CatalogError(
            "permission_denied",
            "Explicit Catalog authority for active eligible staff is required.",
            status=403,
        )
    if mutation:
        if not isinstance(actor_session, AuthSession):
            raise CatalogError(
                "invalid_session", "A persisted actor session is required.", status=403
            )
        # Existing session verification locks factor before session. Keep the same order.
        factor = (
            TOTPFactor.objects.select_for_update()
            .filter(user_id=current.pk, confirmed_at__isnull=False, disabled_at__isnull=True)
            .first()
        )
        session = (
            AuthSession.objects.select_for_update()
            .filter(
                pk=getattr(actor_session, "pk", None),
                user_id=current.pk,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if session is None or session.token_digest != actor_session.token_digest:
            raise CatalogError(
                "invalid_session", "A valid authenticated actor session is required.", status=403
            )
        if factor is None:
            raise MFASetupRequired("An active authenticator is required.")
        require_recent_mfa(session)
    return current


@contextmanager
def _mutation(*, actor, actor_session, context, basis):
    basis = _text(basis, "Change basis", 160)
    try:
        with catalog_gate(exclusive=True):
            current = require_catalog_manager(
                actor=actor, actor_session=actor_session, mutation=True, lock=True
            )
            if getattr(context.actor, "pk", None) != current.pk:
                raise CatalogError(
                    "permission_denied",
                    "Audit actor must match the authenticated Catalog manager.",
                    status=403,
                )
            if not CatalogInitialization.objects.filter(pk=1).exists():
                raise CatalogError(
                    "catalog_not_initialized",
                    "Catalog initialization/adoption is required before editing.",
                )
            yield basis
            # Recheck time-sensitive expiry after lock waits and all domain work.
            require_catalog_manager(actor=current, actor_session=actor_session, mutation=True)
    except IntegrityError as exc:
        if getattr(exc.__cause__, "sqlstate", None) == "23505":
            raise CatalogError(
                "catalog_duplicate_code",
                "This institutional code already exists under the selected parent.",
            ) from exc
        raise
    except OperationalError as exc:
        if getattr(exc.__cause__, "sqlstate", None) in {"40P01", "55P03", "57014"}:
            raise CatalogError(
                "catalog_busy", "Catalog changed concurrently. Refresh and review before retrying."
            ) from exc
        raise


def _get(model, target_id):
    item = model.objects.filter(pk=target_id).first()
    if item is None:
        raise CatalogError(
            "catalog_not_found", "The requested Catalog record was not found.", status=404
        )
    return item


def _locked(model, target_id):
    # Exclusive gate stabilizes ancestry IDs, then individual rows lock top-down.
    item = _get(model, target_id)
    if model is Program:
        college = _get(College, item.college_id)
        Campus.objects.select_for_update().get(pk=college.campus_id)
        College.objects.select_for_update().get(pk=college.pk)
    elif model is College:
        Campus.objects.select_for_update().get(pk=item.campus_id)
    return model.objects.select_for_update().get(pk=item.pk)


def _version(item, expected):
    if type(expected) is not int or expected < 1:
        raise _invalid("expected_resource_version must be a positive integer.")
    if item.resource_version != expected:
        raise CatalogError(
            "catalog_stale_version", "This record changed. Review the latest version before saving."
        )


def _snapshot(item):
    result = dict(name=item.name, is_active=item.is_active)
    if isinstance(item, Program):
        result.update(
            academic_classification=item.academic_classification,
            year_level_policy_status=item.year_level_policy_status,
            applicable_year_levels=item.applicable_year_levels,
        )
    return result


def _audit(item, *, context, action, before, basis):
    after = _snapshot(item)
    parent = (
        str(item.college_id)
        if isinstance(item, Program)
        else str(item.campus_id)
        if isinstance(item, College)
        else None
    )
    record_event(
        context=context,
        action=action,
        outcome=AuditOutcome.SUCCESS,
        target_type=f"organization.{item._meta.model_name}",
        target_id=item.pk,
        metadata={
            "catalog_change": 1,
            "code": item.code,
            "parent_id": parent,
            "changed_fields": sorted(k for k in after if before.get(k) != after[k]),
            "resource_version_before": item.resource_version - 1 if before else None,
            "resource_version_after": item.resource_version,
            "before": before,
            "after": after,
            "basis": basis,
        },
    )


def _save(item, changes, *, context, action, basis):
    before = _snapshot(item)
    changed = {k: v for k, v in changes.items() if getattr(item, k) != v}
    if not changed:
        return item
    for key, value in changed.items():
        setattr(item, key, value)
    item.resource_version += 1
    # Model.save normalizes code/name even when update_fields excludes them. Preserve
    # adopted values in memory and Audit too; only these already-validated fields change.
    item.updated_at = timezone.now()
    type(item).objects.filter(pk=item.pk).update(
        **changed, resource_version=item.resource_version, updated_at=item.updated_at
    )
    _audit(item, context=context, action=action, before=before, basis=basis)
    return item


def create_campus(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    code: str,
    name: str,
    is_active: bool,
    basis: str,
) -> Campus:
    with _mutation(
        actor=actor, actor_session=actor_session, context=context, basis=basis
    ) as reason:
        item = Campus.objects.create(
            code=_code(code), name=_text(name, "Official name", 160), is_active=_boolean(is_active)
        )
        _audit(
            item,
            context=context,
            action=actions.ORGANIZATION_CAMPUS_CREATED,
            before={},
            basis=reason,
        )
        return item


def create_college(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    campus_id: UUID,
    code: str,
    name: str,
    is_active: bool,
    basis: str,
) -> College:
    with _mutation(
        actor=actor, actor_session=actor_session, context=context, basis=basis
    ) as reason:
        campus = _locked(Campus, campus_id)
        active = _boolean(is_active)
        if active and not campus.is_active:
            raise CatalogError(
                "catalog_inactive_parent", "Activate the Campus before creating an active College."
            )
        item = College.objects.create(
            campus=campus,
            code=_code(code),
            name=_text(name, "Official name", 160),
            is_active=active,
        )
        _audit(
            item,
            context=context,
            action=actions.ORGANIZATION_COLLEGE_CREATED,
            before={},
            basis=reason,
        )
        return item


def create_program(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    college_id: UUID,
    code: str,
    name: str,
    is_active: bool,
    basis: str,
    academic_classification: str | None,
    year_level_policy_status: str,
    applicable_year_levels: list[int] | None,
) -> Program:
    with _mutation(
        actor=actor, actor_session=actor_session, context=context, basis=basis
    ) as reason:
        college = _locked(College, college_id)
        item = Program(
            college=college,
            code=_code(code),
            name=_text(name, "Official name", 160),
            is_active=_boolean(is_active),
            **_policy(academic_classification, year_level_policy_status, applicable_year_levels),
        )
        if item.is_active:
            _active_parent(item)
            _activation_policy(item)
        item.save(force_insert=True)
        _audit(
            item,
            context=context,
            action=actions.ORGANIZATION_PROGRAM_CREATED,
            before={},
            basis=reason,
        )
        return item


def _rename(
    model, *, actor, actor_session, context, target_id, expected_resource_version, name, basis
):
    with _mutation(
        actor=actor, actor_session=actor_session, context=context, basis=basis
    ) as reason:
        item = _locked(model, target_id)
        _version(item, expected_resource_version)
        name = _text(name, "Official name", 160)
        if item.name.strip() == name:
            return item
        return _save(
            item,
            {"name": name},
            context=context,
            action=getattr(actions, f"ORGANIZATION_{model.__name__.upper()}_UPDATED"),
            basis=reason,
        )


def rename_campus(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    target_id: UUID,
    expected_resource_version: int,
    name: str,
    basis: str,
) -> Campus:
    return _rename(
        Campus,
        actor=actor,
        actor_session=actor_session,
        context=context,
        target_id=target_id,
        expected_resource_version=expected_resource_version,
        name=name,
        basis=basis,
    )


def rename_college(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    target_id: UUID,
    expected_resource_version: int,
    name: str,
    basis: str,
) -> College:
    return _rename(
        College,
        actor=actor,
        actor_session=actor_session,
        context=context,
        target_id=target_id,
        expected_resource_version=expected_resource_version,
        name=name,
        basis=basis,
    )


def rename_program(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    target_id: UUID,
    expected_resource_version: int,
    name: str,
    basis: str,
) -> Program:
    return _rename(
        Program,
        actor=actor,
        actor_session=actor_session,
        context=context,
        target_id=target_id,
        expected_resource_version=expected_resource_version,
        name=name,
        basis=basis,
    )


def _active_parent(item):
    if (
        isinstance(item, College)
        and not item.campus.is_active
        or isinstance(item, Program)
        and (not item.college.is_active or not item.college.campus.is_active)
    ):
        raise CatalogError(
            "catalog_inactive_parent", "The complete parent hierarchy must be active."
        )


@dataclass(frozen=True, slots=True)
class CatalogIssue:
    code: str
    count: int


@dataclass(frozen=True, slots=True)
class CatalogImpact:
    target_id: UUID
    resource_version: int
    observed_at: datetime
    can_deactivate: bool
    blockers: tuple[CatalogIssue, ...]
    warnings: tuple[CatalogIssue, ...]
    counts: dict[str, int]
    preserved_categories: tuple[str, ...]


def _impact(item):
    from compass.good_moral.models import GoodMoralRequest
    from compass.graduate_tracer.models import GraduateTracerResponse
    from compass.guidance_followups.models import GuidanceFollowUp
    from compass.guidance_messages.models import GuidanceThread
    from compass.inventory.models import StudentInventory

    is_program = isinstance(item, Program)
    colleges = (
        College.objects.filter(campus_id=item.pk)
        if isinstance(item, Campus)
        else College.objects.filter(pk=item.pk)
        if isinstance(item, College)
        else College.objects.none()
    )
    programs = (
        Program.objects.filter(pk=item.pk)
        if is_program
        else Program.objects.filter(college_id__in=colleges.values("pk"))
    )
    affiliations = StudentAffiliation.objects.filter(college_id__in=colleges.values("pk"))
    inventories = StudentInventory.objects.filter(program_id__in=programs.values("pk"))
    threads = GuidanceThread.objects.filter(routing_college_id__in=colleges.values("pk"))
    gm = GoodMoralRequest.objects.filter(
        Q(inventory__program_id__in=programs.values("pk"))
        | Q(student_id__in=affiliations.values("student_id"))
    )
    tracers = GraduateTracerResponse.objects.filter(
        Q(graduated_program_id__in=programs.values("pk"))
        | Q(graduated_college_id__in=colleges.values("pk"))
    )
    counts = {
        "child_colleges": colleges.count() if isinstance(item, Campus) else 0,
        "active_child_colleges": colleges.filter(is_active=True).count()
        if isinstance(item, Campus)
        else 0,
        "child_programs": programs.count() if not is_program else 0,
        "active_child_programs": programs.filter(is_active=True).count() if not is_program else 0,
        "student_affiliations": affiliations.count(),
        "active_student_affiliations": affiliations.filter(
            student__is_active=True, student__role__code="STUDENT"
        ).count(),
        "inactive_account_affiliations": affiliations.filter(student__is_active=False).count(),
        "counselor_responsibilities": CounselorResponsibility.objects.filter(
            college_id__in=colleges.values("pk")
        ).count(),
        "draft_inventories": inventories.filter(submitted_at__isnull=True).count(),
        "submitted_inventories": inventories.filter(submitted_at__isnull=False).count(),
        "graduate_tracer_references": tracers.count(),
        "open_office_threads": threads.filter(kind="OFFICE", status="OPEN").count(),
        "resolved_threads": threads.filter(status="RESOLVED").count(),
        "pending_good_moral": gm.filter(status__in=["REQUESTED", "READY_FOR_ISSUANCE"]).count(),
        "pending_f4": gm.filter(
            variant="CURRENT_STUDENT", status__in=["REQUESTED", "READY_FOR_ISSUANCE"]
        ).count(),
        "issued_good_moral": gm.filter(status="ISSUED").count(),
        "pending_operational_followups": GuidanceFollowUp.objects.filter(
            student_id__in=affiliations.values("student_id"),
            visibility="OPERATIONAL",
            status="PENDING",
        ).count(),
    }
    blocker_keys = []
    if not is_program:
        blocker_keys = [
            "active_student_affiliations",
            "counselor_responsibilities",
            "open_office_threads",
            "pending_operational_followups",
        ]
        blocker_keys += (
            ["active_child_colleges"] if isinstance(item, Campus) else ["active_child_programs"]
        )
    warning_keys = ["inactive_account_affiliations", "draft_inventories", "pending_good_moral"]
    blockers = tuple(CatalogIssue(k, counts[k]) for k in blocker_keys if counts[k])
    return CatalogImpact(
        item.pk,
        item.resource_version,
        timezone.now(),
        not blockers,
        blockers,
        tuple(CatalogIssue(k, counts[k]) for k in warning_keys if counts[k]),
        counts,
        (
            "submitted_inventory_facts",
            "issued_certificate_snapshots",
            "graduate_tracer_references",
            "resolved_guidance_threads",
            "inactive_affiliations",
        ),
    )


def get_catalog_impact(
    *, actor: User, model: type[Campus] | type[College] | type[Program], target_id: UUID
) -> CatalogImpact:
    with catalog_gate():
        require_catalog_manager(actor=actor)
        return _impact(_get(model, target_id))


def _status(
    model, *, actor, actor_session, context, target_id, expected_resource_version, is_active, basis
):
    with _mutation(
        actor=actor, actor_session=actor_session, context=context, basis=basis
    ) as reason:
        item = _locked(model, target_id)
        _version(item, expected_resource_version)
        active = _boolean(is_active)
        if item.is_active == active:
            return item
        if active:
            _active_parent(item)
            if isinstance(item, Program):
                _activation_policy(item)
        else:
            impact = _impact(item)
            if not impact.can_deactivate:
                raise CatalogError(
                    "catalog_deactivation_blocked",
                    "Resolve blockers before retirement: "
                    + ", ".join(i.code for i in impact.blockers)
                    + ".",
                    details={
                        "blockers": [{"code": i.code, "count": i.count} for i in impact.blockers]
                    },
                )
        action = getattr(
            actions, f"ORGANIZATION_{model.__name__.upper()}_{'ENABLED' if active else 'DISABLED'}"
        )
        return _save(item, {"is_active": active}, context=context, action=action, basis=reason)


def set_campus_active(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    target_id: UUID,
    expected_resource_version: int,
    is_active: bool,
    basis: str,
) -> Campus:
    return _status(
        Campus,
        actor=actor,
        actor_session=actor_session,
        context=context,
        target_id=target_id,
        expected_resource_version=expected_resource_version,
        is_active=is_active,
        basis=basis,
    )


def set_college_active(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    target_id: UUID,
    expected_resource_version: int,
    is_active: bool,
    basis: str,
) -> College:
    return _status(
        College,
        actor=actor,
        actor_session=actor_session,
        context=context,
        target_id=target_id,
        expected_resource_version=expected_resource_version,
        is_active=is_active,
        basis=basis,
    )


def set_program_active(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    target_id: UUID,
    expected_resource_version: int,
    is_active: bool,
    basis: str,
) -> Program:
    return _status(
        Program,
        actor=actor,
        actor_session=actor_session,
        context=context,
        target_id=target_id,
        expected_resource_version=expected_resource_version,
        is_active=is_active,
        basis=basis,
    )


def update_program_policy(
    *,
    actor: User,
    actor_session: AuthSession,
    context: AuditContext,
    target_id: UUID,
    expected_resource_version: int,
    academic_classification: str | None,
    year_level_policy_status: str,
    applicable_year_levels: list[int] | None,
    basis: str,
) -> Program:
    with _mutation(
        actor=actor, actor_session=actor_session, context=context, basis=basis
    ) as reason:
        item = _locked(Program, target_id)
        _version(item, expected_resource_version)
        changes = _policy(academic_classification, year_level_policy_status, applicable_year_levels)
        if all(getattr(item, k) == v for k, v in changes.items()):
            return item
        impact = _impact(item)
        if impact.counts["pending_f4"]:
            raise CatalogError(
                "catalog_pending_f4_policy_decision_required",
                "Pending F4 requests require an institutional policy decision "
                "before changing this policy.",
            )
        if item.is_active and (
            academic_classification is None or year_level_policy_status != "CONFIGURED"
        ):
            raise CatalogError(
                "catalog_policy_approval_required",
                "Retire the Program before storing incomplete policy; "
                "incomplete activation remains blocked.",
            )
        return _save(
            item,
            changes,
            context=context,
            action=actions.ORGANIZATION_PROGRAM_POLICY_CHANGED,
            basis=reason,
        )


def get_catalog_history(
    *,
    actor: User,
    model: type[Campus] | type[College] | type[Program],
    target_id: UUID,
    page: int = 1,
    page_size: int = 20,
):
    require_catalog_manager(actor=actor)
    _get(model, target_id)
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 50:
        raise _invalid("Use a positive page and page_size 1–50.")
    allowed = {
        getattr(actions, f"ORGANIZATION_{model.__name__.upper()}_{suffix}")
        for suffix in ("CREATED", "UPDATED", "ENABLED", "DISABLED")
    }
    if model is Program:
        allowed.add(actions.ORGANIZATION_PROGRAM_POLICY_CHANGED)
    rows = list(
        AuditEvent.objects.filter(
            target_type=f"organization.{model._meta.model_name}",
            target_id=str(target_id),
            action__in=allowed,
            outcome="SUCCESS",
            metadata__catalog_change=1,
        ).order_by("-occurred_at", "-id")[(page - 1) * page_size : page * page_size + 1]
    )
    # Deliberate projection; no IP, UA, request ID, actor email or arbitrary metadata.
    keys = (
        "code",
        "parent_id",
        "changed_fields",
        "resource_version_before",
        "resource_version_after",
        "before",
        "after",
        "basis",
    )
    return {
        "items": [
            {
                "id": r.pk,
                "occurred_at": r.occurred_at,
                "actor_id": r.actor_user_id,
                "action": r.action,
                **{k: r.metadata.get(k) for k in keys if k not in {"before", "after"}},
                **{
                    k: {
                        field: value
                        for field, value in r.metadata.get(k, {}).items()
                        if field
                        in {
                            "name",
                            "is_active",
                            "academic_classification",
                            "year_level_policy_status",
                            "applicable_year_levels",
                        }
                    }
                    for k in ("before", "after")
                },
            }
            for r in rows[:page_size]
        ],
        "page": page,
        "page_size": page_size,
        "has_next": len(rows) > page_size,
    }
