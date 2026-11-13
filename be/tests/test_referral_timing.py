"""CW-5 validation, immutable envelopes, audience boundaries and legacy compatibility."""

import json
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from pypdf import PdfReader

from compass.accounts.models import Capability, UserCapabilityOverride
from compass.audit.models import AuditEvent
from compass.notifications.models import EmailDelivery, Notification
from compass.referrals import timing_services
from compass.referrals.confidential_content import ReferralConfidentialContentUnavailable
from compass.referrals.faculty_services import get_own_submission
from compass.referrals.models import Referral
from compass.referrals.services import (
    create_referral,
    render_referral_pdf,
    update_status_note,
    void_referral,
)
from compass.referrals.timing_content import read_timing_content
from compass.referrals.timing_models import (
    ReferralSchedulingStatement,
    ReferralSchedulingVerification,
)
from compass.referrals.timing_rules import (
    InvalidReferralTiming,
    project_window,
    validate_timing_content,
)
from tests.faculty_referral_helpers import confirm, submit
from tests.referral_administration_helpers import make_world, transition
from tests.test_referrals import auth_client, context, csrf, ensure_referral_form_revision

NOW = datetime(2026, 11, 13, 2, 0, tzinfo=UTC)
NOTE = "PRIVATE-CW5-SCHEDULING-NOTE café 🌱"


def specific(**changes):
    value = {
        "information_type": "STUDENT_AVAILABLE",
        "pattern": "SPECIFIC_DATE",
        "date": "2026-11-13",
        "start_time": "10:00",
        "end_time": "11:00",
    }
    value.update(changes)
    return value


def recurring(**changes):
    value = {
        "information_type": "CLASS_RELEASE",
        "pattern": "RECURRING_WEEKDAY",
        "weekday": "MONDAY",
        "valid_until": "2026-11-20",
        "start_time": "09:00",
        "end_time": "10:00",
    }
    value.update(changes)
    return value


def valid(**changes):
    value = {"answer_kind": "KNOWN", "windows": [specific(), recurring()], "note": NOTE}
    value.update(changes)
    return value


def check(value, **kwargs):
    return validate_timing_content(**value, now=NOW, **kwargs)


@pytest.mark.parametrize(
    "windows",
    [
        [specific()],
        [recurring()],
        [specific(), recurring()],
        [specific(start_time="10:15", end_time="10:45"), specific()],
        [
            recurring(weekday=day)
            for day in ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "SATURDAY"]
        ],
    ],
)
def test_known_accepts_mixed_overlapping_and_one_to_five_windows(windows):
    assert len(check(valid(windows=windows))["windows"]) == len(windows)


@pytest.mark.parametrize(
    "window,field",
    [
        (specific(date="2026-11-12"), "date"),
        (specific(date="2026-02-30"), "date"),
        (specific(date=None), "date"),
        (specific(start_time="11:00"), "end_time"),
        (specific(end_time="09:59"), "end_time"),
        (specific(start_time="bad"), "start_time"),
        (specific(start_time="10:00+08:00"), "start_time"),
        (specific(weekday="MONDAY"), "pattern"),
        (specific(valid_until="2026-11-20"), "pattern"),
        (specific(pattern="OTHER"), "pattern"),
        (specific(information_type="OTHER"), "information_type"),
        (recurring(weekday="SUNDAY"), "weekday"),
        (recurring(weekday=None), "weekday"),
        (recurring(valid_until=None), "valid_until"),
        (recurring(valid_until="2026-11-12"), "valid_until"),
        (recurring(valid_until="2027-05-13"), "valid_until"),
        (recurring(date="2026-11-13"), "date"),
    ],
)
def test_validation_attaches_errors_without_echoing_input(window, field):
    with pytest.raises(InvalidReferralTiming) as error:
        check(valid(windows=[window]))
    assert error.value.details[0]["loc"][-1] == field
    assert NOTE not in json.dumps(error.value.details)


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"answer_kind": "OTHER"}, "answer_kind"),
        ({"windows": []}, "windows"),
        ({"windows": [specific()] * 6}, "windows"),
        ({"windows": [specific(), specific()]}, "start_time"),
        ({"windows": [recurring(), recurring()]}, "start_time"),
        ({"note": "a" * 501}, "note"),
        ({"note": "bad\x00text"}, "note"),
        ({"note": "\ud800"}, "note"),
        ({"answer_kind": "UNKNOWN"}, "windows"),
    ],
)
def test_statement_collection_and_note_boundaries(changes, field):
    with pytest.raises(InvalidReferralTiming) as error:
        check(valid(**changes))
    assert error.value.details[0]["loc"][-1] == field


def test_unknown_is_zero_windows_and_note_unicode_limit_is_characters():
    assert check(valid(answer_kind="UNKNOWN", windows=[], note="")) == {"windows": [], "note": ""}
    assert check(valid(note="🌱" * 500))["note"] == "🌱" * 500
    with pytest.raises(InvalidReferralTiming):
        check(valid(answer_kind="UNKNOWN", windows=[], note=NOTE))


def test_midnight_and_180_days_use_manila_not_runtime_timezone(settings):
    settings.TIME_ZONE = "UTC"
    before = datetime(2026, 11, 12, 15, 59, 59, tzinfo=UTC)
    after = before + timedelta(seconds=1)
    old = valid(windows=[specific(date="2026-11-12")])
    validate_timing_content(**old, now=before)
    with pytest.raises(InvalidReferralTiming):
        validate_timing_content(**old, now=after)
    until = date(2026, 11, 13) + timedelta(days=180)
    assert check(valid(windows=[recurring(valid_until=until.isoformat())]))
    with pytest.raises(InvalidReferralTiming):
        check(valid(windows=[recurring(valid_until=(until + timedelta(days=1)).isoformat())]))


def test_read_time_expiry_keeps_windows_and_validity_day_is_inclusive():
    content = check(valid())
    assert project_window(content["windows"][0], now=NOW)["expired"] is False
    assert project_window(content["windows"][0], now=NOW + timedelta(hours=1))["expired"] is True
    until_end = datetime(2026, 11, 20, 15, 59, 59, tzinfo=UTC)
    assert not project_window(content["windows"][1], now=until_end)["expired"]
    assert project_window(content["windows"][1], now=until_end + timedelta(seconds=1))["expired"]
    assert check(valid(), historical=True)["windows"] == content["windows"]


@pytest.fixture
def world(db, monkeypatch):
    value = make_world(monkeypatch)
    ensure_referral_form_revision()
    return value


def statement_today():
    from compass.common.institutional_time import institution_today

    today = institution_today()
    return valid(
        windows=[
            specific(date=today.isoformat()),
            recurring(valid_until=(today + timedelta(days=7)).isoformat()),
        ]
    )


def gco(world, statement=None):
    from compass.common.institutional_time import institution_today

    return create_referral(
        actor=world.counselor,
        student_id=world.student.pk,
        course_year_block="BSIS 4A",
        reason="Synthetic original reason",
        referrer_name="Actual paper referrer",
        referred_on=institution_today(),
        received_at=None,
        idempotency_key=str(uuid4()),
        request_fingerprint="f" * 64,
        context=context(world.counselor),
        scheduling_statement=statement,
    )


def verification_body(client, pk, **changes):
    response = client.get(f"/api/v1/referrals/{pk}/timing")
    assert response.status_code == 200
    facts = response.json()
    body = {
        "expected_latest_verification_id": facts["latest_verification_id"],
        "expected_referral_updated_at": facts["referral_updated_at"],
        "answer_kind": "KNOWN",
        "confirmation_source": "STUDENT_CONFIRMED",
        "windows": statement_today()["windows"],
        "note": NOTE,
    }
    body.update(changes)
    return body


def post_verification(client, pk, body):
    return client.post(
        f"/api/v1/referrals/{pk}/timing/verifications",
        data=json.dumps(body),
        content_type="application/json",
        **csrf(client),
    )


def test_verification_version_round_trip_retains_microseconds_and_refuses_nearby_time(world):
    item = gco(world, statement_today())
    exact = item.updated_at.replace(microsecond=123456)
    Referral.objects.filter(pk=item.pk).update(updated_at=exact)
    client = auth_client(world.counselor)
    body = verification_body(client, item.pk)
    assert body["expected_referral_updated_at"] == exact.isoformat()
    stale = {
        **body,
        "expected_referral_updated_at": (exact - timedelta(microseconds=1)).isoformat(),
    }
    assert post_verification(client, item.pk, stale).status_code == 409
    assert not item.scheduling_verifications.exists()
    assert post_verification(client, item.pk, body).status_code == 201


def test_atomic_statement_creation_and_gco_provenance(world, monkeypatch):
    item = gco(world, statement_today())
    row = item.scheduling_statement
    assert row.submission_channel == "GCO_RECORDED"
    assert row.author_id == world.counselor.pk
    assert row.author_name_snapshot == world.counselor.get_full_name()
    assert read_timing_content(row)["note"] == NOTE and NOTE not in row.content_ciphertext
    assert row.window_count == 2
    original = timing_services.record_event

    def fail(**kwargs):
        if kwargs["action"] == "referral.timing_recorded":
            raise RuntimeError("Synthetic audit failure")
        return original(**kwargs)

    monkeypatch.setattr(timing_services, "record_event", fail)
    before = Referral.objects.count()
    with pytest.raises(RuntimeError), transaction.atomic():
        gco(world, statement_today())
    assert Referral.objects.count() == before


def test_faculty_own_detail_only_statement_and_lists_only_marker(world, monkeypatch):
    result, _ = submit(world, scheduling_statement=statement_today())
    pk = result["id"]
    assert result["scheduling_statement"]["author_name"] == world.faculty.get_full_name()
    staff = auth_client(world.counselor)
    saved = post_verification(staff, pk, verification_body(staff, pk))
    assert saved.status_code == 201
    # Own detail must not even consult the verification envelope.
    original = timing_services.read_timing_content

    def own_only(row):
        assert isinstance(row, ReferralSchedulingStatement)
        return original(row)

    monkeypatch.setattr(timing_services, "read_timing_content", own_only)
    faculty = auth_client(world.faculty)
    own = faculty.get(f"/api/v1/faculty/referrals/{pk}")
    assert own.status_code == 200
    assert own.json()["scheduling_statement"]["note"] == NOTE
    assert "verifications" not in own.json()
    listed = faculty.get("/api/v1/faculty/referrals").json()["items"][0]
    assert listed["timing_status"] == "KNOWN"
    assert "scheduling_statement" not in listed and NOTE not in json.dumps(listed)
    for outsider in (world.other_faculty, world.student, world.other_counselor, world.admin):
        client = auth_client(outsider)
        expected = 404 if outsider == world.other_faculty else 403
        assert client.get(f"/api/v1/faculty/referrals/{pk}").status_code == expected
        assert client.get(f"/api/v1/referrals/{pk}/timing").status_code in {403, 404}
        assert post_verification(
            client,
            pk,
            {
                "expected_latest_verification_id": None,
                "expected_referral_updated_at": saved.json()["referral_updated_at"],
                "answer_kind": "NO_SUITABLE_TIME",
                "confirmation_source": "OFFICE_RECORD",
                "windows": [],
                "note": "",
            },
        ).status_code in {403, 404}
    assert faculty.get(f"/api/v1/faculty/referrals/{uuid4()}").status_code == 404
    assert staff.get(f"/api/v1/referrals/{uuid4()}/timing").status_code == 404


def test_status_void_ack_and_closure_never_change_statement_bytes(world):
    pk = submit(world, scheduling_statement=statement_today())[0]["id"]
    original = ReferralSchedulingStatement.objects.get(referral_id=pk).content_ciphertext
    update_status_note(
        actor=world.counselor,
        referral_id=pk,
        status_note="Synthetic status",
        context=context(world.counselor),
    )
    transition(world, pk)
    transition(world, pk, close=True)
    assert ReferralSchedulingStatement.objects.get(referral_id=pk).content_ciphertext == original
    client = auth_client(world.counselor)
    facts = client.get(f"/api/v1/referrals/{pk}/timing").json()
    assert facts["referral_closed"] is True and facts["can_verify"] is True
    assert post_verification(client, pk, verification_body(client, pk)).status_code == 201
    void_referral(
        actor=world.counselor,
        referral_id=pk,
        reason="Synthetic void",
        context=context(world.counselor),
    )
    assert ReferralSchedulingStatement.objects.get(referral_id=pk).content_ciphertext == original
    assert post_verification(client, pk, verification_body(client, pk)).status_code == 409
    assert client.get(f"/api/v1/referrals/{pk}/timing").json()["can_verify"] is False


def test_verifications_are_newest_first_append_only_and_stale_write_is_refused(world):
    item = gco(world, statement_today())
    client = auth_client(world.staff)
    first_body = verification_body(client, item.pk)
    first = post_verification(client, item.pk, first_body)
    assert first.status_code == 201
    first_id = first.json()["latest_verification_id"]
    first_bytes = ReferralSchedulingVerification.objects.get(pk=first_id).content_ciphertext
    assert post_verification(client, item.pk, first_body).status_code == 409
    second = post_verification(
        client,
        item.pk,
        verification_body(
            client,
            item.pk,
            answer_kind="NO_SUITABLE_TIME",
            windows=[],
            confirmation_source="OFFICE_RECORD",
        ),
    )
    assert second.status_code == 201
    ids = [row["id"] for row in second.json()["verifications"]]
    assert ids == [second.json()["latest_verification_id"], first_id]
    assert ReferralSchedulingVerification.objects.get(pk=first_id).content_ciphertext == first_bytes
    assert second.json()["reported"]["answer_kind"] == "KNOWN"
    for model in (ReferralSchedulingStatement, ReferralSchedulingVerification):
        row = model.objects.filter(referral=item).first()
        with pytest.raises(ValidationError):
            row.save()
        with pytest.raises(ValidationError):
            model.objects.filter(pk=row.pk).update(content_ciphertext="overwrite")
        with pytest.raises(ValidationError):
            row.delete()
        with pytest.raises(ValidationError):
            model.objects.filter(pk=row.pk).delete()
        with pytest.raises(ValidationError):
            model.objects.bulk_create(
                [row],
                update_conflicts=True,
                update_fields=["content_ciphertext"],
                unique_fields=["id"],
            )
        replacement = model(
            **{field.attname: getattr(row, field.attname) for field in model._meta.concrete_fields}
        )
        replacement.content_ciphertext = "overwrite"
        with pytest.raises(IntegrityError), transaction.atomic():
            replacement.save()
        assert model.objects.get(pk=row.pk).content_ciphertext == row.content_ciphertext
    denied = client.patch(
        f"/api/v1/referrals/{item.pk}/timing", data="{}", content_type="application/json"
    )
    assert denied.status_code == 405


def test_row_binding_rejects_copied_ciphertext_and_other_envelope_types(world):
    first, second = gco(world, statement_today()), gco(world, statement_today())
    copied = second.scheduling_statement
    copied.content_ciphertext = first.scheduling_statement.content_ciphertext
    with pytest.raises(ReferralConfidentialContentUnavailable):
        read_timing_content(copied)
    client = auth_client(world.counselor)
    result = post_verification(client, first.pk, verification_body(client, first.pk))
    row = ReferralSchedulingVerification.objects.get(pk=result.json()["latest_verification_id"])
    row.content_ciphertext = first.scheduling_statement.content_ciphertext
    with pytest.raises(ReferralConfidentialContentUnavailable):
        read_timing_content(row)


def test_read_only_staff_can_read_but_cannot_write_and_revoked_session_denied(world):
    item = gco(world, statement_today())
    client = auth_client(world.counselor)
    body = verification_body(client, item.pk)
    UserCapabilityOverride.objects.create(
        user=world.counselor,
        capability=Capability.objects.get(code="referrals.manage"),
        effect="REVOKE",
        reason="Synthetic read-only",
    )
    response = client.get(f"/api/v1/referrals/{item.pk}/timing")
    assert response.status_code == 200 and response.json()["can_verify"] is False
    assert post_verification(client, item.pk, body).status_code == 403
    assert not item.scheduling_verifications.exists()
    assert Client().get(f"/api/v1/referrals/{item.pk}/timing").status_code == 401


@pytest.mark.parametrize("expired", [False, True])
def test_lost_session_during_verification_is_a_401_without_any_record(world, expired, monkeypatch):
    from compass.common.errors import APIError
    from compass.referrals.api import _raise

    item = gco(world, statement_today())
    session = world.counselor_issued.session
    from django.utils import timezone

    if expired:
        # Advance past a valid expiry; storing expiry before creation violates the
        # session's database constraint and never exercises service authorization.
        monkeypatch.setattr(timezone, "now", lambda: session.expires_at + timedelta(seconds=1))
    else:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])
    with pytest.raises(timing_services.ReferralTimingSessionUnavailable) as error:
        timing_services.record_verification(
            actor=world.counselor,
            actor_session=session,
            referral_id=item.pk,
            expected_latest_verification_id=None,
            expected_referral_updated_at=item.updated_at,
            answer_kind="NO_SUITABLE_TIME",
            confirmation_source="OFFICE_RECORD",
            windows=[],
            note="",
            context=context(world.counselor),
        )
    with pytest.raises(APIError) as mapped:
        _raise(error.value)
    assert mapped.value.status_code == 401
    assert not item.scheduling_verifications.exists()


def test_verification_requires_csrf_and_cannot_override_provenance(world):
    from django.conf import settings

    item = gco(world, statement_today())
    client = Client(enforce_csrf_checks=True)
    client.cookies[settings.AUTH_SESSION_COOKIE_NAME] = world.counselor_issued.token
    body = verification_body(client, item.pk)
    assert (
        client.post(
            f"/api/v1/referrals/{item.pk}/timing/verifications",
            json.dumps(body),
            content_type="application/json",
        ).status_code
        == 403
    )
    assert (
        post_verification(
            client, item.pk, {**body, "author_id": str(world.other_counselor.pk)}
        ).status_code
        == 422
    )
    assert not item.scheduling_verifications.exists()


def test_timing_never_enters_lists_audit_logs_notifications_or_pdf(world, caplog):
    item = gco(world, statement_today())
    client = auth_client(world.counselor)
    counts = Notification.objects.count(), EmailDelivery.objects.count()
    assert post_verification(client, item.pk, verification_body(client, item.pk)).status_code == 201
    listed = client.get("/api/v1/referrals").json()
    assert listed["items"][0]["timing_status"] == "KNOWN"
    assert NOTE not in json.dumps(listed)
    assert "windows" not in json.dumps(listed) and "verifications" not in json.dumps(listed)
    events = list(
        AuditEvent.objects.filter(
            action__in=["referral.timing_recorded", "referral.timing_verified"]
        ).values("metadata")
    )
    assert len(events) == 2 and NOTE not in json.dumps(events)
    assert all(
        set(event["metadata"])
        <= {"referral_id", "answer_kind", "submission_channel", "confirmation_source"}
        for event in events
    )
    assert counts == (Notification.objects.count(), EmailDelivery.objects.count())
    pdf = render_referral_pdf(item)
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    assert NOTE not in text and "Known times" not in text and "Verified availability" not in text
    assert NOTE not in caplog.text


def test_optional_statement_preserves_legacy_endpoints_and_absent_is_not_unknown(world):
    legacy, unknown = gco(world), gco(world, {"answer_kind": "UNKNOWN"})
    client = auth_client(world.counselor)
    assert client.get(f"/api/v1/referrals/{legacy.pk}/timing").json()["reported"] is None
    assert (
        client.get(f"/api/v1/referrals/{legacy.pk}/timing").json()["timing_status"]
        == "NOT_PROVIDED"
    )
    assert (
        client.get(f"/api/v1/referrals/{unknown.pk}/timing").json()["reported"]["answer_kind"]
        == "UNKNOWN"
    )
    assert client.get(f"/api/v1/referrals/{legacy.pk}").status_code == 200
    assert client.get(f"/api/v1/referrals/{legacy.pk}/pdf").status_code == 200
    assert (
        client.patch(
            f"/api/v1/referrals/{legacy.pk}/status",
            data=json.dumps({"status_note": "Legacy still works"}),
            content_type="application/json",
        ).status_code
        == 200
    )
    result = submit(world)[0]
    detail = get_own_submission(
        actor=world.faculty, actor_session=world.issued.session, referral_id=result["id"]
    )
    assert detail["scheduling_statement"] is None and detail["timing_status"] == "NOT_PROVIDED"
    transition(world, result["id"])
    transition(world, result["id"], close=True)
    assert client.get(f"/api/v1/referrals/{result['id']}/administration").status_code == 200


def test_invalid_creation_rolls_back_and_api_field_errors_identify_window(world):
    from compass.common.institutional_time import institution_today

    client = auth_client(world.counselor)
    statement = statement_today()
    statement["windows"][0]["end_time"] = "09:00"
    body = {
        "student_id": str(world.student.pk),
        "course_year_block": "BSIS 4A",
        "reason": "Synthetic",
        "referrer_name": "Paper referrer",
        "referred_on": institution_today().isoformat(),
        "scheduling_statement": statement,
    }
    before = Referral.objects.count()
    response = client.post(
        "/api/v1/referrals",
        data=json.dumps(body),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == [
        "body",
        "scheduling_statement",
        "windows",
        "0",
        "end_time",
    ]
    assert Referral.objects.count() == before


def test_submission_idempotency_includes_timing_but_legacy_replay_remains_compatible(world):
    from compass.referrals.services import ReferralCreationConflict

    ticket = confirm(world)["confirmation"]
    result, created = submit(world, confirmation=ticket, scheduling_statement=statement_today())
    same, replay = submit(world, confirmation=ticket, scheduling_statement=statement_today())
    assert created and not replay and same == result
    with pytest.raises(ReferralCreationConflict):
        submit(world, confirmation=ticket, scheduling_statement={"answer_kind": "UNKNOWN"})
    assert ReferralSchedulingStatement.objects.count() == 1
    old, _ = submit(world, confirmation=ticket, idempotency_key="legacy")
    assert submit(world, confirmation=ticket, idempotency_key="legacy")[0] == old


def test_nested_window_parse_error_keeps_the_field_without_echoing_input(world):
    from compass.common.institutional_time import institution_today

    statement = statement_today()
    statement["windows"][0]["start_time"] = "PRIVATE-CW5-INVALID-TIME"
    response = auth_client(world.counselor).post(
        "/api/v1/referrals",
        data=json.dumps(
            {
                "student_id": str(world.student.pk),
                "course_year_block": "BSIS 4A",
                "reason": "Synthetic",
                "referrer_name": "Paper referrer",
                "referred_on": institution_today().isoformat(),
                "scheduling_statement": statement,
            }
        ),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert details[0]["loc"][-4:] == ["scheduling_statement", "windows", "0", "start_time"]
    assert "PRIVATE-CW5-INVALID-TIME" not in json.dumps(details)
    assert not Referral.objects.exists()
