"""Real PostgreSQL lock waits for verification and concurrent Referral changes."""

import pytest

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.organization.services import set_counselor_responsibility
from compass.referrals import services, timing_services
from compass.referrals.services import ReferralNotFound
from compass.referrals.timing_models import ReferralSchedulingStatement
from tests.faculty_referral_helpers import submit
from tests.referral_administration_helpers import make_world, transition
from tests.test_faculty_referral_concurrency import ordered_race
from tests.test_referral_timing import statement_today

pytestmark = pytest.mark.django_db(transaction=True)


def setup(monkeypatch):
    world = make_world(monkeypatch)
    pk = submit(world, scheduling_statement=statement_today())[0]["id"]
    facts = timing_services.get_timing(actor=world.counselor, referral_id=pk)
    from datetime import datetime

    args = dict(
        actor=world.counselor,
        actor_session=world.counselor_issued.session,
        referral_id=pk,
        expected_latest_verification_id=None,
        expected_referral_updated_at=datetime.fromisoformat(facts["referral_updated_at"]),
        answer_kind="NO_SUITABLE_TIME",
        confirmation_source="OFFICE_RECORD",
        windows=[],
        note="Synthetic scheduling constraint",
        context=AuditContext.user(world.counselor),
    )
    return world, pk, args


def test_two_verifiers_with_the_same_review_append_once(monkeypatch):
    world, pk, args = setup(monkeypatch)
    original = ReferralSchedulingStatement.objects.get(referral_id=pk).content_ciphertext
    first, second = ordered_race(
        lambda: timing_services.record_verification(**args),
        lambda: timing_services.record_verification(
            **{
                **args,
                "actor": world.staff,
                "actor_session": world.staff_issued.session,
                "context": AuditContext.user(world.staff),
            }
        ),
    )
    assert len(first["verifications"]) == 1
    assert isinstance(second, timing_services.ReferralTimingChanged)
    assert AuditEvent.objects.filter(action="referral.timing_verified").count() == 1
    assert ReferralSchedulingStatement.objects.get(referral_id=pk).content_ciphertext == original


@pytest.mark.parametrize("void_first", [False, True])
def test_verification_and_void_serialize_in_both_orders(monkeypatch, void_first):
    world, pk, args = setup(monkeypatch)
    original = ReferralSchedulingStatement.objects.get(referral_id=pk).content_ciphertext

    def void():
        return services.void_referral(
            actor=world.counselor,
            referral_id=pk,
            reason="Synthetic",
            context=AuditContext.user(world.counselor),
        )

    def verify():
        return timing_services.record_verification(**args)

    _, second = ordered_race(void if void_first else verify, verify if void_first else void)
    facts = timing_services.get_timing(actor=world.counselor, referral_id=pk)
    assert facts["can_verify"] is False
    assert len(facts["verifications"]) == (0 if void_first else 1)
    assert (
        isinstance(second, timing_services.ReferralTimingChanged)
        if void_first
        else not isinstance(second, Exception)
    ), type(second).__name__
    assert ReferralSchedulingStatement.objects.get(referral_id=pk).content_ciphertext == original


def test_closure_during_review_requires_recheck_then_allows_verification(monkeypatch):
    world, pk, args = setup(monkeypatch)
    transition(world, pk)
    facts = timing_services.get_timing(actor=world.counselor, referral_id=pk)
    from datetime import datetime

    args["expected_referral_updated_at"] = datetime.fromisoformat(facts["referral_updated_at"])
    _, second = ordered_race(
        lambda: transition(world, pk, close=True),
        lambda: timing_services.record_verification(**args),
    )
    assert isinstance(second, timing_services.ReferralTimingChanged)
    facts = timing_services.get_timing(actor=world.counselor, referral_id=pk)
    assert facts["referral_closed"] and facts["can_verify"]
    args["expected_referral_updated_at"] = datetime.fromisoformat(facts["referral_updated_at"])
    assert len(timing_services.record_verification(**args)["verifications"]) == 1


def test_scope_change_before_waiting_verification_denies_the_write(monkeypatch):
    world, pk, args = setup(monkeypatch)
    _, second = ordered_race(
        lambda: set_counselor_responsibility(
            college_id=world.ccms.pk,
            counselor_id=world.other_counselor.pk,
            context=AuditContext.user(world.admin),
        ),
        lambda: timing_services.record_verification(**args),
    )
    assert isinstance(second, ReferralNotFound)
    assert not AuditEvent.objects.filter(action="referral.timing_verified").exists()
