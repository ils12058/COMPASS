"""Demo account provisioning through the canonical User manager and system audit path.

Administrative Account Management services require a live administrator session with recent MFA,
which a management command must not fabricate. Provisioning therefore follows ``create_it_admin``:
``User.objects.create_user`` plus a SYSTEM ``account.created`` event. Designation, lifecycle, and
disable helpers mirror the Account Management invariants (role compatibility, STUDENT-only
lifecycle, auth-state invalidation on disable) and record the same audit actions.

Existing demo accounts are never modified: passwords, verification, activity, and state that live
demonstrations change survive ordinary reruns.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Q

from compass.accounts.models import Designation, Role, StudentLifecycleStatus, User, UserDesignation
from compass.accounts.policy import designation_role_compatible
from compass.audit.actions import (
    ACCOUNT_CREATED,
    ACCOUNT_DESIGNATION_ASSIGNED,
    ACCOUNT_DISABLED,
    ACCOUNT_STUDENT_LIFECYCLE_CHANGED,
)
from compass.audit.models import AuditOutcome
from compass.audit.services import record_event
from compass.authentication.security import invalidate_auth_state_after_authority_change

from .cast import CAST, AuthState, Persona, StudentPersona, email_for
from .config import DemoConfig, DemoConfigurationError
from .support import DemoSeedConflict, SeedSession


@dataclass(frozen=True)
class AccountPlan:
    persona: Persona
    email: str
    existing: User | None


def _candidate(persona: Persona, email: str) -> User:
    return User(
        email=email,
        institutional_id=persona.institutional_id,
        first_name=persona.first_name,
        middle_name=persona.middle_name,
        last_name=persona.last_name,
    )


def validate_demo_password(config: DemoConfig) -> None:
    """Apply the normal Django password policy against every ready persona's attributes."""

    for persona in CAST:
        if persona.auth_state != AuthState.READY:
            continue
        email = email_for(
            persona,
            domain=config.email_domain,
            onboarding_email=config.onboarding_email,
        )
        try:
            validate_password(config.password, _candidate(persona, email))
        except ValidationError as exc:
            raise DemoConfigurationError(
                f"DEMO_ACCOUNT_PASSWORD does not meet the COMPASS password policy for "
                f"{persona.label}: " + " ".join(exc.messages)
            ) from None


def plan_accounts(config: DemoConfig) -> tuple[AccountPlan, ...]:
    """Match each persona to an existing account by institutional ID and email, or fail closed."""

    plans: list[AccountPlan] = []
    seen_emails: set[str] = set()
    for persona in CAST:
        email = email_for(
            persona,
            domain=config.email_domain,
            onboarding_email=config.onboarding_email,
        )
        if email in seen_emails:
            raise DemoConfigurationError(
                f"Demo email {email} would be shared by two personas; check DEMO_ONBOARDING_EMAIL."
            )
        seen_emails.add(email)
        matches = list(
            User.objects.select_related("role")
            .filter(Q(institutional_id__iexact=persona.institutional_id) | Q(email__iexact=email))
            .order_by("pk")
        )
        if not matches:
            plans.append(AccountPlan(persona=persona, email=email, existing=None))
            continue
        user = matches[0]
        if (
            len(matches) > 1
            or (user.institutional_id or "").upper() != persona.institutional_id
            or user.email != email
        ):
            raise DemoSeedConflict(
                f"{persona.label} ({persona.institutional_id}) conflicts with an existing account. "
                "Keep DEMO_EMAIL_DOMAIN and DEMO_ONBOARDING_EMAIL stable between runs and do not "
                "reuse demo identifiers for real accounts."
            )
        if user.role.code != persona.role:
            raise DemoSeedConflict(
                f"{persona.label} ({persona.institutional_id}) exists with role "
                f"{user.role.code}; the demo dataset requires {persona.role}."
            )
        if (user.first_name, user.middle_name, user.last_name) != (
            persona.first_name,
            persona.middle_name,
            persona.last_name,
        ):
            raise DemoSeedConflict(
                f"{persona.key} ({persona.institutional_id}) has a different canonical name; "
                "review the identity conflict. Existing identity and credentials were preserved."
            )
        plans.append(AccountPlan(persona=persona, email=email, existing=user))
    return tuple(plans)


def _assign_designation_at_provisioning(
    session: SeedSession, user: User, designation_code: str
) -> None:
    if not designation_role_compatible(designation_code=designation_code, role_code=user.role.code):
        raise DemoSeedConflict(
            f"designation {designation_code} is incompatible with role {user.role.code}"
        )
    designation = Designation.objects.get(code=designation_code)
    _assignment, created = UserDesignation.objects.get_or_create(
        user=user,
        designation=designation,
    )
    if created:
        # A newly provisioned account starts with this authority, so there is no prior access to
        # invalidate and no "access changed" security alert to raise.
        record_event(
            context=session.system(),
            action=ACCOUNT_DESIGNATION_ASSIGNED,
            outcome=AuditOutcome.SUCCESS,
            target_type="accounts.user",
            target_id=user.pk,
            metadata={"designation": designation_code},
        )


def _create_account(session: SeedSession, plan: AccountPlan, config: DemoConfig) -> User:
    persona = plan.persona
    ready = persona.auth_state == AuthState.READY
    user = User.objects.create_user(
        email=plan.email,
        password=config.password if ready else None,
        role=Role.objects.get(code=persona.role),
        first_name=persona.first_name,
        middle_name=persona.middle_name,
        last_name=persona.last_name,
        institutional_id=persona.institutional_id,
        is_active=True,
    )
    if ready:
        user.email_verified_at = session.started_at
        user.save(update_fields=["email_verified_at", "updated_at"])
    record_event(
        context=session.system(),
        action=ACCOUNT_CREATED,
        outcome=AuditOutcome.SUCCESS,
        target_type="accounts.user",
        target_id=user.pk,
        metadata={"role": persona.role},
    )
    for designation_code in persona.designations:
        _assign_designation_at_provisioning(session, user, designation_code)
    return user


def provision_accounts(
    session: SeedSession,
    plans: tuple[AccountPlan, ...],
    config: DemoConfig,
) -> None:
    for plan in plans:
        if plan.existing is not None:
            session.users[plan.persona.key] = plan.existing
            session.record("Accounts", created=False)
        else:
            session.users[plan.persona.key] = _create_account(session, plan, config)
            session.record("Accounts", created=True)
        session.emails[plan.persona.key] = plan.email


def set_student_lifecycle(session: SeedSession, persona: StudentPersona, status: str) -> None:
    """Mirror Account Management's lifecycle change for a synthetic Student."""

    user = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .get(pk=session.users[persona.key].pk)
    )
    if user.role.code != "STUDENT":
        raise DemoSeedConflict(f"{persona.label} is not a STUDENT account")
    if status not in StudentLifecycleStatus.values:
        raise DemoSeedConflict(f"unsupported Student lifecycle {status}")
    if user.student_lifecycle_status == status:
        return
    previous = user.student_lifecycle_status
    user.student_lifecycle_status = status
    user.save(update_fields=["student_lifecycle_status", "updated_at"])
    record_event(
        context=session.system(),
        action=ACCOUNT_STUDENT_LIFECYCLE_CHANGED,
        outcome=AuditOutcome.SUCCESS,
        target_type="accounts.user",
        target_id=user.pk,
        metadata={"from_status": previous, "to_status": status},
    )


def disable_account(session: SeedSession, persona: Persona) -> bool:
    """Mirror Account Management's disable for a departed synthetic staff member."""

    user = (
        User.objects.select_for_update(of=("self",))
        .select_related("role")
        .get(pk=session.users[persona.key].pk)
    )
    if user.role.code == "IT_ADMIN":
        raise DemoSeedConflict("the demo seeder never disables an IT administrator")
    if not user.is_active:
        return False
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    invalidate_auth_state_after_authority_change(
        user_id=user.pk,
        context=session.system(),
        reason="account_disabled",
        invalidate_email_security_challenges=True,
    )
    record_event(
        context=session.system(),
        action=ACCOUNT_DISABLED,
        outcome=AuditOutcome.SUCCESS,
        target_type="accounts.user",
        target_id=user.pk,
        metadata={},
    )
    return True


__all__ = [
    "AccountPlan",
    "disable_account",
    "plan_accounts",
    "provision_accounts",
    "set_student_lifecycle",
    "validate_demo_password",
]
