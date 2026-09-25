from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from compass.accounts.models import Role, StudentLifecycleStatus, User
from compass.audit.context import AuditContext
from compass.counseling.services import create_encounter
from compass.service_catalog.services import set_service_active
from tests.canonical_service_helpers import legacy_counseling_service


def sync_policy() -> None:
    call_command("sync_identity_policy", verbosity=0)


def make_user(email: str, role: str) -> User:
    return User.objects.create_user(
        email=email,
        password="a-test-password",
        role=Role.objects.get(code=role),
        first_name=email.split("@")[0].title(),
        last_name="User",
    )


def context(actor: User) -> AuditContext:
    return AuditContext.user(actor)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [StudentLifecycleStatus.GRADUATED, StudentLifecycleStatus.FORMER],
)
def test_walk_in_counseling_remains_recordable_without_current_inventory(status):
    sync_policy()
    admin = make_user("admin@example.edu", "IT_ADMIN")
    counselor = make_user("counselor@example.edu", "COUNSELOR")
    student = make_user("student@example.edu", "STUDENT")
    service = legacy_counseling_service(
        code="COUNSELING",
        name="Counseling",
        appointment_policy="OPTIONAL",
        default_duration_minutes=60,
        cancellation_cutoff_minutes=30,
        requires_current_inventory=True,
        delivery_modes=["IN_PERSON"],
        provider_roles=["COUNSELOR"],
        context=context(admin),
    )
    set_service_active(service_id=service.pk, is_active=True, context=context(admin))
    student.student_lifecycle_status = status
    student.save(update_fields=["student_lifecycle_status", "updated_at"])
    ended_at = timezone.now() - timedelta(minutes=1)

    item = create_encounter(
        counselor=counselor,
        student_id=student.pk,
        entry_mode="WALK_IN",
        delivery_mode="IN_PERSON",
        started_at=ended_at - timedelta(minutes=35),
        ended_at=ended_at,
        context=context(counselor),
    )

    assert item.student_id == student.pk
    assert item.entry_mode == "WALK_IN"
