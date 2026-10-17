"""Operational reassignment recovery; never grants confidential Follow-Up or source access."""

from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Q, UUIDField
from django.utils import timezone

from compass.accounts.models import (
    DesignationCapability,
    RoleCapability,
    User,
    UserCapabilityOverride,
)
from compass.organization.access_scope import (
    active_head_guidance_counselors,
    is_head_guidance,
    resolve_operational_responsibility_scope,
)
from compass.organization.models import CounselorResponsibility

from . import policy
from .errors import FollowUpInvalid
from .models import GuidanceFollowUp


def _capable_users(queryset, capability):
    overrides = UserCapabilityOverride.objects.filter(
        user_id=OuterRef("pk"), capability__code=capability
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    return (
        queryset.alias(
            _role_grants=Exists(
                RoleCapability.objects.filter(
                    role_id=OuterRef("role_id"), capability__code=capability
                )
            ),
            _designation_grants=Exists(
                DesignationCapability.objects.filter(
                    designation__user_assignments__user_id=OuterRef("pk"),
                    capability__code=capability,
                )
            ),
            _override_grant=Exists(overrides.filter(effect="GRANT")),
            _override_revoke=Exists(overrides.filter(effect="REVOKE")),
        )
        .filter(Q(_role_grants=True) | Q(_designation_grants=True) | Q(_override_grant=True))
        .filter(_override_revoke=False)
    )


def recoverable_queryset(*, actor):
    actor = policy.current_actor(actor, manage=True)
    rows = GuidanceFollowUp.objects.filter(
        visibility="OPERATIONAL",
        status="PENDING",
        student__is_active=True,
        student__role__code="STUDENT",
    )
    if not is_head_guidance(actor):
        rows = rows.filter(
            student__organization_student_affiliation__college_id__in=resolve_operational_responsibility_scope(
                actor
            ).college_ids,
            student__organization_student_affiliation__college__is_active=True,
            student__organization_student_affiliation__college__campus__is_active=True,
        )
    # Eligibility of the *current* owner, including capability dependency revocations, is decided
    # before pagination. These annotations read no protected content.
    candidates = User.objects.filter(is_active=True, role__code__in=policy.ROLES)
    # Distinct aliases retain both requirements when composing correlated capability predicates.
    for capability in ("guidance_followups.view", "guidance_followups.manage"):
        eligible = _capable_users(User.objects.all(), capability).values("pk")
        candidates = candidates.filter(pk__in=eligible)
    college = OuterRef("student__organization_student_affiliation__college_id")
    head = Q(
        role__code="COUNSELOR", designation_assignments__designation__code="HEAD_GUIDANCE_COUNSELOR"
    )
    scope = head | Q(
        role__code="COUNSELOR",
        organization_counselor_responsibilities__college_id=college,
        organization_counselor_responsibilities__college__is_active=True,
        organization_counselor_responsibilities__college__campus__is_active=True,
    )
    supervisor_colleges = (
        "organization_staff_supervision__supervisor__organization_counselor_responsibilities"
    )
    scope |= Q(
        role__code="GUIDANCE_SERVICES_STAFF",
        organization_staff_supervision__supervisor__is_active=True,
        organization_staff_supervision__supervisor__role__code="COUNSELOR",
        **{
            supervisor_colleges + "__college_id": college,
            supervisor_colleges + "__college__is_active": True,
            supervisor_colleges + "__college__campus__is_active": True,
        },
    )
    heads = list(active_head_guidance_counselors().values_list("pk", flat=True)[:2])
    if len(heads) == 1:
        valid_responsibility = CounselorResponsibility.objects.filter(
            counselor__is_active=True, counselor__role__code="COUNSELOR"
        )
        candidates = candidates.alias(
            _assigned_college=ExpressionWrapper(college, output_field=UUIDField()),
            _student_college_active=ExpressionWrapper(
                OuterRef("student__organization_student_affiliation__college__is_active"),
                output_field=BooleanField(),
            ),
            _student_campus_active=ExpressionWrapper(
                OuterRef("student__organization_student_affiliation__college__campus__is_active"),
                output_field=BooleanField(),
            ),
        )
        scope |= Q(
            role__code="GUIDANCE_SERVICES_STAFF",
            organization_staff_supervision__supervisor_id=heads[0],
            _assigned_college__isnull=False,
            _student_college_active=True,
            _student_campus_active=True,
        ) & ~Q(_assigned_college__in=valid_responsibility.values("college_id"))
    candidates = candidates.filter(scope, pk=OuterRef("assigned_to_id"))
    return rows.alias(_owner_eligible=Exists(candidates)).filter(_owner_eligible=False)


def list_recoverable(*, actor, page=1, page_size=20):
    if not 1 <= page <= 100 or not 1 <= page_size <= 50:
        raise FollowUpInvalid("The requested recovery page is unavailable.")
    rows = list(
        recoverable_queryset(actor=actor)
        .select_related("student", "assigned_to")
        .order_by("due_at", "id")[(page - 1) * page_size : page * page_size + 1]
    )
    return {
        "items": rows[:page_size],
        "page": page,
        "page_size": page_size,
        "has_next": len(rows) > page_size,
    }
