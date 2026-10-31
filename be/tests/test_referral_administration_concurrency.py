"""Observed PostgreSQL waits: explicit transitions serialize with void and authority writers."""

import pytest
from django.utils import timezone

from compass.account_management.services import change_role, set_account_active
from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.authentication.sessions import create_auth_session
from compass.organization.integrity import catalog_gate
from compass.organization.services import (
    remove_staff_supervisor,
    set_counselor_responsibility,
    set_staff_supervisor,
    set_student_affiliation,
)
from compass.referrals import services
from compass.referrals.administrative_policy import AdministrativeReferralError
from compass.referrals.models import Referral
from compass.referrals.services import ReferralNotFound
from tests.faculty_referral_helpers import submit
from tests.referral_administration_helpers import make_world, transition
from tests.test_faculty_referral_concurrency import ordered_race

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("close", [False, True])
def test_duplicate_transition_serializes_once(monkeypatch, close):
    world = make_world(monkeypatch)
    pk = submit(world)[0]["id"]
    if close:
        transition(world, pk)
    a, b = ordered_race(
        lambda: transition(world, pk, close=close), lambda: transition(world, pk, close=close)
    )
    assert a["version"] == (3 if close else 2)
    assert isinstance(b, AdministrativeReferralError) and b.status == 409
    action = "referral.administratively_closed" if close else "referral.acknowledged"
    assert AuditEvent.objects.filter(action=action, target_id=str(pk)).count() == 1


@pytest.mark.parametrize("void_first", [False, True])
@pytest.mark.parametrize("close", [False, True])
def test_void_transition_both_orders_preserve_facts(monkeypatch, void_first, close):
    world = make_world(monkeypatch)
    pk = submit(world)[0]["id"]
    if close:
        transition(world, pk)

    def void():
        return services.void_referral(
            actor=world.counselor,
            referral_id=pk,
            reason="Synthetic",
            context=AuditContext.user(world.counselor),
        )

    def change():
        return transition(world, pk, close=close)

    _a, b = ordered_race(void if void_first else change, change if void_first else void)
    row = Referral.objects.get(pk=pk)
    assert row.voided_at is not None
    if void_first:
        assert isinstance(b, AdministrativeReferralError) and b.status == 409
        assert row.administrative_version == (2 if close else 1)
    else:
        assert not isinstance(b, Exception)
        assert row.administrative_version == (3 if close else 2)
    if close:
        assert row.received_at is not None


@pytest.mark.parametrize("close_first", [False, True])
def test_ack_and_close_both_orders_never_skip_prior_receipt(monkeypatch, close_first):
    world = make_world(monkeypatch)
    pk = submit(world)[0]["id"]

    # First failed closure is caught inside the winner transaction so the observer can wait.
    def close():
        with catalog_gate(exclusive=True):
            try:
                return transition(world, pk, close=True)
            except AdministrativeReferralError as exc:
                return exc

    _a, b = ordered_race(
        close if close_first else lambda: transition(world, pk),
        lambda: transition(world, pk) if close_first else close(),
    )
    row = Referral.objects.get(pk=pk)
    assert not isinstance(b, Exception)
    assert row.administrative_version == (2 if close_first else 3)


@pytest.mark.parametrize("change_first", [False, True])
@pytest.mark.parametrize(
    "change", ["role", "inactive", "responsibility", "supervision", "student_placement"]
)
def test_current_authority_changes_serialize_before_admission(monkeypatch, change_first, change):
    world = make_world(monkeypatch)
    pk = submit(world)[0]["id"]
    issued = create_auth_session(world.admin, mfa_verified_at=timezone.now())
    context = AuditContext.user(world.admin)

    def mutate():
        args = dict(actor=world.admin, actor_session=issued.session, context=context)
        if change == "role":
            remove_staff_supervisor(staff_id=world.staff.pk, context=context)
            return change_role(**args, target_id=world.staff.pk, role="INSTITUTIONAL_OFFICER")
        if change == "inactive":
            return set_account_active(**args, target_id=world.counselor.pk, is_active=False)
        if change == "responsibility":
            return set_counselor_responsibility(
                college_id=world.ccms.pk, counselor_id=world.other_counselor.pk, context=context
            )
        if change == "supervision":
            return set_staff_supervisor(
                staff_id=world.staff.pk, supervisor_id=world.other_counselor.pk, context=context
            )
        return set_student_affiliation(
            student_id=world.student.pk, college_id=world.cas.pk, context=context
        )

    def acknowledge():
        extra = (
            dict(actor=world.staff, actor_session=world.staff_issued.session)
            if change in {"supervision", "role"}
            else {}
        )
        return transition(world, pk, **extra)

    _a, b = ordered_race(
        mutate if change_first else acknowledge, acknowledge if change_first else mutate
    )
    row = Referral.objects.get(pk=pk)
    if change_first:
        assert isinstance(b, (AdministrativeReferralError, ReferralNotFound))
        assert row.received_at is None
    else:
        assert not isinstance(b, Exception)
        assert row.received_at is not None
