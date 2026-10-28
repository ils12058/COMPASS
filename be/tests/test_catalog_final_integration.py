"""ORG-4 additional integrated work, history and PostgreSQL race evidence."""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from threading import Event
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import close_old_connections, connection, transaction
from django.utils import timezone
from pypdf import PdfReader

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.guidance_followups import services as followups
from compass.guidance_followups.models import GuidanceFollowUp
from compass.guidance_messages import services as messages
from compass.guidance_messages.models import GuidanceThread
from compass.organization import catalog_services as cs
from compass.organization.models import (
    College,
    CounselorResponsibility,
    Program,
    StudentAffiliation,
)
from tests.catalog_test_helpers import authority, hierarchy, manager, run_serialized_race, student

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def work(settings):
    settings.GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    user, issued = manager()
    auth = authority(user, issued)
    c, k, p = hierarchy()
    Program.objects.filter(pk=p.pk).update(is_active=False)
    counselor, _ = manager("COUNSELOR", grant=False)
    s = student()
    StudentAffiliation.objects.create(student=s, college=k)
    CounselorResponsibility.objects.create(counselor=counselor, college=k)
    return auth, c, k, p, counselor, s


def new_work(kind, counselor, s):
    if kind == "office":
        return messages.open_office_thread(
            actor=s, client_message_id=uuid4(), body="Synthetic private Office body"
        )[0]
    return followups.create_followup(
        actor=counselor,
        student_id=s.pk,
        assigned_to_id=counselor.pk,
        category="ADMINISTRATIVE",
        due_at=timezone.now() + timedelta(days=1),
        source_kind=None,
        source_id=None,
        description="Synthetic private Follow-Up body",
        visibility="OPERATIONAL",
        idempotency_key=str(uuid4()),
        request_fingerprint="f" * 64,
        context=AuditContext.user(counselor),
    )


@pytest.mark.parametrize("kind", ["office", "followup"])
def test_new_operational_work_waits_before_catalog_retirement_recount(work, kind):
    auth, _, k, _, counselor, s = work
    item, error = run_serialized_race(
        lambda: new_work(kind, counselor, s),
        lambda: cs.set_college_active(
            **auth, target_id=k.pk, expected_resource_version=1, is_active=False
        ),
    )
    assert isinstance(error, cs.CatalogError) and error.code == "catalog_deactivation_blocked"
    key = "open_office_threads" if kind == "office" else "pending_operational_followups"
    assert {i["code"]: i["count"] for i in error.details["blockers"]}[key] == 1
    k.refresh_from_db()
    assert k.is_active and k.resource_version == 1
    assert type(item).objects.filter(pk=item.pk).exists()


@pytest.mark.parametrize("kind", ["office", "followup"])
def test_catalog_change_first_serializes_new_operational_work_without_lost_relationship(work, kind):
    auth, _, k, _, counselor, s = work
    _, item = run_serialized_race(
        lambda: cs.rename_college(
            **auth, target_id=k.pk, expected_resource_version=1, name="Official renamed College"
        ),
        lambda: new_work(kind, counselor, s),
    )
    assert not isinstance(item, Exception)
    assert StudentAffiliation.objects.get(student=s).college_id == k.pk
    impact = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
    assert (
        impact.counts[
            "open_office_threads" if kind == "office" else "pending_operational_followups"
        ]
        == 1
    )


@pytest.mark.parametrize("kind", ["office", "followup"])
def test_resolved_completed_work_and_encrypted_history_survive_retirement(work, kind):
    auth, _, k, _, counselor, s = work
    item = new_work(kind, counselor, s)
    if kind == "office":
        messages.set_status(actor=counselor, thread_id=item.pk, resolved=True)
        ciphertext = item.messages.get().body_ciphertext
    else:
        followups.complete_followup(
            actor=counselor,
            followup_id=item.pk,
            expected_version=1,
            outcome="Synthetic completed outcome",
            context=AuditContext.user(counselor),
        )
        item.refresh_from_db()
        ciphertext = item.description_ciphertext
    # Fixtures model an explicitly remediated scope: inactive retained Student and
    # removed responsibility. The test does not claim account administration approval.
    type(s).objects.filter(pk=s.pk).update(is_active=False)
    CounselorResponsibility.objects.filter(college=k).delete()
    impact = cs.get_catalog_impact(actor=auth["actor"], model=College, target_id=k.pk)
    assert impact.can_deactivate
    assert impact.counts["inactive_account_affiliations"] == 1
    cs.set_college_active(**auth, target_id=k.pk, expected_resource_version=1, is_active=False)
    assert StudentAffiliation.objects.get(student=s).college_id == k.pk
    if kind == "office":
        assert GuidanceThread.objects.get(pk=item.pk).status == "RESOLVED"
        assert item.messages.get().body_ciphertext == ciphertext
    else:
        saved = GuidanceFollowUp.objects.get(pk=item.pk)
        assert saved.status == "COMPLETED" and saved.description_ciphertext == ciphertext
    assert "Synthetic private" not in str(
        cs.get_catalog_history(actor=auth["actor"], model=College, target_id=k.pk)
    )


def test_duplicate_noop_intents_share_gate_without_version_or_audit(work):
    auth, _, _, p, _, _ = work
    before = AuditEvent.objects.filter(target_id=str(p.pk)).count()

    def noop():
        return cs.rename_program(**auth, target_id=p.pk, expected_resource_version=1, name=p.name)

    a, b = run_serialized_race(noop, noop)
    assert a.resource_version == b.resource_version == 1
    assert AuditEvent.objects.filter(target_id=str(p.pk)).count() == before


def test_history_reader_never_observes_uncommitted_catalog_event(work):
    auth, _, _, p, _, _ = work
    held, release = Event(), Event()

    def writer():
        close_old_connections()
        try:
            with transaction.atomic():
                cs.rename_program(
                    **auth, target_id=p.pk, expected_resource_version=1, name="Committed after read"
                )
                held.set()
                assert release.wait(15)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer)
        try:
            assert held.wait(15)
            assert (
                cs.get_catalog_history(actor=auth["actor"], model=Program, target_id=p.pk)["items"]
                == []
            )
            assert Program.objects.get(pk=p.pk).resource_version == 1
        finally:
            release.set()
        future.result(timeout=15)
    history = cs.get_catalog_history(actor=auth["actor"], model=Program, target_id=p.pk)
    assert history["items"][0]["resource_version_after"] == 2
    assert Program.objects.get(pk=p.pk).name == "Committed after read"


@pytest.mark.parametrize("parent_first", [True, False])
def test_parent_child_rename_orders_complete_without_lock_inversion(work, parent_first):
    auth, _, k, p, _, _ = work

    def parent():
        return cs.rename_college(
            **auth, target_id=k.pk, expected_resource_version=1, name="Renamed parent"
        )

    def child():
        return cs.rename_program(
            **auth, target_id=p.pk, expected_resource_version=1, name="Renamed child"
        )

    a, b = run_serialized_race(parent if parent_first else child, child if parent_first else parent)
    assert a.resource_version == b.resource_version == 2
    assert Program.objects.get(pk=p.pk).college_id == k.pk


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
def test_issued_f4_f6_pdf_facts_survive_protected_catalog_changes(work, variant):
    from compass.good_moral.models import GoodMoralRequest
    from compass.good_moral.services import (
        build_certificate_render_context,
        issue_request,
        prepare_request,
    )
    from tests.test_good_moral import auth_client
    from tests.test_good_moral_receipts import request_for

    auth, _, _, p, counselor, _ = work
    item = request_for(variant=variant)
    if variant == "CURRENT_STUDENT":
        p = item.inventory.program
    prepare_request(actor=counselor, request_id=item.pk, context=AuditContext.user(counselor))
    issue_request(actor=counselor, request_id=item.pk, context=AuditContext.user(counselor))
    item.refresh_from_db()
    before = GoodMoralRequest.objects.filter(pk=item.pk).values().get()
    facts = build_certificate_render_context(item)
    events = list(AuditEvent.objects.filter(action="good_moral.issued").values())
    client = auth_client(item.student)

    def pdf_facts():
        response = client.get(f"/api/v1/good-moral/me/{item.pk}/pdf")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        body = b"".join(response.streaming_content) if response.streaming else response.content
        pages = PdfReader(BytesIO(body)).pages
        return len(pages), [re.sub(r"\s+", " ", page.extract_text()).strip() for page in pages]

    original = pdf_facts()
    cs.rename_program(
        **auth, target_id=p.pk, expected_resource_version=1, name="Changed official Program name"
    )
    cs.update_program_policy(
        **auth,
        target_id=p.pk,
        expected_resource_version=2,
        academic_classification="DOCTORAL",
        year_level_policy_status="CONFIGURED",
        applicable_year_levels=[1, 3, 5],
    )
    # The work fixture's Program was an inactive draft; use actual current status,
    # avoiding a fabricated increment for a no-op retirement in the F6 case.
    cs.set_program_active(**auth, target_id=p.pk, expected_resource_version=3, is_active=False)
    item.refresh_from_db()
    assert GoodMoralRequest.objects.filter(pk=item.pk).values().get() == before
    assert build_certificate_render_context(item) == facts
    assert list(AuditEvent.objects.filter(action="good_moral.issued").values()) == events
    assert pdf_facts() == original


@pytest.mark.parametrize("kind", ["college", "program"])
def test_normalized_duplicate_child_codes_have_one_committed_identity(work, kind):
    auth, c, k, _, _, _ = work
    kwargs = {"name": "Additional definition", "is_active": True}
    if kind == "college":
        create = cs.create_college
        kwargs["campus_id"] = c.pk
    else:
        create = cs.create_program
        kwargs.update(
            college_id=k.pk,
            academic_classification="BACHELORS",
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1, 3],
        )
    a, b = run_serialized_race(
        lambda: create(**auth, code="DUP", **kwargs),
        lambda: create(**auth, code=" dup ", **kwargs),
    )
    assert isinstance(b, cs.CatalogError) and b.code == "catalog_duplicate_code"
    assert type(a).objects.filter(code="DUP").count() == 1


def test_two_complete_policy_changes_reject_stale_second_intent(work):
    auth, _, _, p, _, _ = work

    def policy(classification):
        return cs.update_program_policy(
            **auth,
            target_id=p.pk,
            expected_resource_version=1,
            academic_classification=classification,
            year_level_policy_status="CONFIGURED",
            applicable_year_levels=[1, 3],
        )

    a, b = run_serialized_race(lambda: policy("MASTERS"), lambda: policy("DOCTORAL"))
    assert a.resource_version == 2
    assert isinstance(b, cs.CatalogError) and b.code == "catalog_stale_version"
    assert Program.objects.get(pk=p.pk).academic_classification == "MASTERS"


def test_program_retirement_first_prevents_waiting_inventory_submission(work):
    from compass.inventory.models import StudentInventory
    from compass.inventory.services import InventoryConflict, submit_current_inventory
    from tests.test_catalog_concurrency import inventory_fixture

    auth, _, _, p, _, _ = work
    Program.objects.filter(pk=p.pk).update(is_active=True)
    s, _ = inventory_fixture(auth, p)
    _, error = run_serialized_race(
        lambda: cs.set_program_active(
            **auth, target_id=p.pk, expected_resource_version=1, is_active=False
        ),
        lambda: submit_current_inventory(student=s, context=AuditContext.user(s)),
    )
    assert isinstance(error, InventoryConflict)
    assert StudentInventory.objects.get(student=s).submitted_at is None


def test_mfa_expiry_after_real_audit_write_rolls_back_entire_mutation(work, monkeypatch):
    from compass.authentication.sessions import RecentMFARequired

    auth, _, _, p, _, _ = work
    original = cs.record_event
    later = timezone.now() + timedelta(hours=2)
    before = Program.objects.filter(pk=p.pk).values().get()
    with monkeypatch.context() as patch:

        def expire_after_audit(**kwargs):
            result = original(**kwargs)
            # Synthetic time injection, not a claim of an hours-long real-clock race.
            patch.setattr(timezone, "now", lambda: later)
            return result

        patch.setattr(cs, "record_event", expire_after_audit)
        with pytest.raises(RecentMFARequired):
            cs.rename_program(
                **auth, target_id=p.pk, expected_resource_version=1, name="Must roll back"
            )
    assert Program.objects.filter(pk=p.pk).values().get() == before
    assert not AuditEvent.objects.filter(target_id=str(p.pk), metadata__catalog_change=1).exists()
