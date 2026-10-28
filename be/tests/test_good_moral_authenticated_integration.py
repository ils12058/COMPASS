"""GM-OR-4: persisted opaque sessions/CSRF and optional real Next/Django/PG flow.

The browser cases require an explicitly supplied loopback Next build proxying to
pytest's live_server. They never intercept API responses or contact deployed data.
Synthetic sessions use the application's session service; login/MFA is not bypassed
in application code, and is not claimed as covered by this domain harness.
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from threading import Barrier
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone
from pypdf import PdfReader

from compass.accounts.models import User
from compass.audit.models import AuditEvent
from compass.common.institutional_time import institution_today
from compass.feedback.models import FeedbackOpportunity
from compass.good_moral import receipt_fee_policy as fees
from compass.good_moral.models import (
    GoodMoralReceiptAssignment as Assignment,
)
from compass.good_moral.models import (
    GoodMoralReceiptIdentity as Identity,
)
from compass.good_moral.models import (
    GoodMoralReceiptMutation as Mutation,
)
from compass.good_moral.models import (
    GoodMoralReceiptVerification as Verification,
)
from compass.good_moral.models import GoodMoralRequest
from compass.notifications.models import Notification
from tests.test_good_moral import (
    auth_client,
    csrf,
    make_academic_year,
    make_affiliation,
    make_inventory,
    make_user,
    sync_policy,
)
from tests.test_good_moral_receipts import activate, person
from tests.test_good_moral_verification import grant, synthetic_fee

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def approved(monkeypatch):
    monkeypatch.setattr(fees, "resolve_approved_fee", synthetic_fee)


@pytest.fixture
def actors(approved):
    sync_policy()
    student = make_user(f"gm4-{uuid4()}@example.test", lifecycle="CURRENT")
    make_affiliation(student)
    make_inventory(student, make_academic_year())
    inspector = person("gm4-inspector", "GUIDANCE_SERVICES_STAFF")
    counselor = person("gm4-issuer", "COUNSELOR")
    grant(inspector)
    activate()
    return student, inspector, counselor


def send(client, method, path, body, **headers):
    return getattr(client, method)(
        path, data=body, content_type="application/json", **csrf(client), **headers
    )


def create(client, variant):
    body = (
        {"semester": "First Semester"}
        if variant == "CURRENT_STUDENT"
        else {
            "degree": "Bachelor of Science in Information Systems",
            "graduation_date": "2020-01-01",
        }
    )
    route = "current-student" if variant == "CURRENT_STUDENT" else "graduate"
    response = send(
        client,
        "post",
        f"/api/v1/good-moral/me/requests/{route}",
        body,
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
    )
    assert response.status_code == 201, response.content
    item = response.json()
    assert item["official_receipt_number"] == ""
    assert item["official_receipt_date"] is None and item["official_receipt_amount"] is None
    return item


def record(client, item, number=None):
    path = f"/api/v1/good-moral/requests/{item['id']}"
    saved = client.get(path).json()
    response = send(
        client,
        "patch",
        path,
        {
            "official_receipt_number": number or f"GM4-{uuid4()}",
            "official_receipt_date": institution_today().isoformat(),
            "official_receipt_amount": "80.00",
            "expected_resource_version": saved["actions"]["request_version"],
            "expected_receipt_revision": saved["receipt_identity"]["revision_id"],
            "receipt_operation_id": str(uuid4()),
        },
    )
    assert response.status_code == 200, response.content
    return response.json()


def verification_intent(item):
    return {
        "expected_resource_version": item["actions"]["request_version"],
        "assignment_id": item["receipt_identity"]["revision_id"],
        "operation_id": str(uuid4()),
        "method": "PHYSICAL_OR_INSPECTION",
    }


def facts():
    return (
        list(GoodMoralRequest.objects.order_by("pk").values()),
        list(Assignment.objects.order_by("pk").values()),
        list(Identity.objects.order_by("pk").values()),
        list(Mutation.objects.order_by("pk").values()),
        list(Verification.objects.order_by("pk").values()),
        list(AuditEvent.objects.order_by("pk").values()),
        Notification.objects.count(),
        FeedbackOpportunity.objects.count(),
    )


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
def test_authenticated_api_full_workflow_exact_provenance_and_owned_pdf(actors, variant):
    student, inspector, counselor = actors
    student_client, staff, issuer = map(auth_client, actors)
    created = create(student_client, variant)
    item = record(staff, created)
    path = f"/api/v1/good-moral/requests/{item['id']}"
    assert not Verification.objects.exists()
    claim = Assignment.objects.get(pk=item["receipt_identity"]["revision_id"])
    assert claim.is_current and claim.identity.bound_request_id == claim.request_id
    intent = verification_intent(item)
    result = send(staff, "post", path + "/receipt/verify", intent)
    assert result.status_code == 200, result.content
    verified = result.json()
    evidence = Verification.objects.get(pk=verified["receipt_inspection"]["verification_id"])
    assert evidence.verified_by_id == inspector.pk
    assert timezone.is_aware(evidence.verified_at)
    assert evidence.expected_amount == Decimal("80.00")
    assert Verification.objects.filter(invalidated_at__isnull=True).count() == 1
    prepared = send(
        staff,
        "post",
        path + "/prepare",
        {
            "expected_resource_version": verified["actions"]["request_version"],
        },
    )
    assert prepared.status_code == 200, prepared.content
    review = issuer.get(path).json()
    issue_body = {
        "expected_resource_version": review["actions"]["request_version"],
        "expected_preparation_version": review["actions"]["preparation_version"],
        "expected_receipt_revision": review["receipt_identity"]["revision_id"],
        "expected_receipt_verification": review["receipt_inspection"]["verification_id"],
    }
    issued = send(issuer, "post", path + "/issue", issue_body)
    assert issued.status_code == 200, issued.content
    row = GoodMoralRequest.objects.get(pk=created["id"])
    assert row.issued_by_id == counselor.pk
    assert row.issued_receipt_assignment_id == claim.pk
    assert row.issued_receipt_verification_id == evidence.pk
    assert FeedbackOpportunity.objects.filter(source_id=row.pk).count() == 1
    assert Notification.objects.filter(recipient=student).exists()
    before = facts()
    assert send(issuer, "post", path + "/issue", issue_body).status_code == 200
    assert facts() == before
    safe_path = f"/api/v1/good-moral/me/{row.pk}"
    safe = student_client.get(safe_path).json()
    assert not {
        "receipt_identity",
        "receipt_inspection",
        "receipt_verification_result",
        "receipt_mutation_result",
        "actions",
    }.intersection(safe)
    outsider = auth_client(person("other-student"))
    assert outsider.get(safe_path).status_code == 404
    assert outsider.get(safe_path + "/pdf").status_code == 404
    pdf = student_client.get(safe_path + "/pdf")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    content = b"".join(pdf.streaming_content) if pdf.streaming else pdf.content
    assert content.startswith(b"%PDF")
    text = " ".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)
    normalized = re.sub(r"\s+", "", text)
    assert row.official_receipt_number in normalized
    assert re.sub(r"\s+", "", row.issued_by_name_snapshot).casefold() in normalized.casefold()


@pytest.mark.parametrize(
    "case",
    [
        "student-correction",
        "student-verify",
        "student-prepare",
        "student-issue",
        "ungranted-gss",
        "gss-issue",
        "ungranted-counselor",
        "it-verify",
        "it-issue",
        "head-without-grant",
        "revoked",
        "expired",
        "inactive",
        "missing-dependency",
        "forged-fields",
        "cross-request",
        "missing-csrf",
        "invalid-csrf",
        "missing-session",
    ],
)
def test_real_session_denials_leave_all_receipt_and_outcome_facts_unchanged(actors, case):
    student, inspector, counselor = actors
    staff = auth_client(inspector)
    created = create(auth_client(student), "GRADUATE")
    item = record(staff, created)
    actor = inspector
    if case.startswith("student"):
        actor = student
    elif case == "ungranted-gss":
        actor = person("ungranted", "GUIDANCE_SERVICES_STAFF")
    elif case == "ungranted-counselor":
        actor = counselor
    elif case.startswith("it"):
        actor = person("admin", "IT_ADMIN")
        grant(actor)
        grant(actor, "good_moral.issue")
    elif case == "head-without-grant":
        from compass.accounts.models import Designation, UserDesignation

        actor = counselor
        UserDesignation.objects.create(
            user=actor, designation=Designation.objects.get(code="HEAD_GUIDANCE_COUNSELOR")
        )
    elif case == "revoked":
        grant(actor, effect="REVOKE")
    elif case == "expired":
        from compass.accounts.models import UserCapabilityOverride

        UserCapabilityOverride.objects.filter(user=actor).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
    elif case == "inactive":
        User.objects.filter(pk=actor.pk).update(is_active=False)
    elif case == "missing-dependency":
        grant(actor, "good_moral.prepare", effect="REVOKE")
    client = Client(enforce_csrf_checks=True)
    client.cookies = auth_client(actor).cookies
    body = verification_intent(item)
    method, suffix = "post", "/receipt/verify"
    if case == "student-correction":
        method, suffix = "patch", ""
        body = {"official_receipt_number": "FORGED"}
    elif case.endswith("prepare"):
        suffix, body = "/prepare", {"expected_resource_version": item["actions"]["request_version"]}
    elif case.endswith("issue"):
        suffix, body = "/issue", {"expected_preparation_version": timezone.now().isoformat()}
    elif case == "forged-fields":
        body.update(
            verified_by_id=str(counselor.pk),
            verified_at=timezone.now().isoformat(),
            fee_policy_id="FORGED",
        )
    elif case == "cross-request":
        other = record(staff, create(auth_client(student), "GRADUATE"))
        body["assignment_id"] = other["receipt_identity"]["revision_id"]
    elif case == "missing-session":
        client = Client()
    headers = csrf(client)
    if case == "missing-csrf":
        headers = {}
    elif case == "invalid-csrf":
        headers = {"HTTP_X_CSRFTOKEN": "invalid"}
    before = facts()
    response = getattr(client, method)(
        f"/api/v1/good-moral/requests/{item['id']}" + suffix,
        data=body,
        content_type="application/json",
        **headers,
    )
    expected = {
        "inactive": 401,
        "missing-session": 401,
        "forged-fields": 422,
        "cross-request": 409,
    }.get(case, 403)
    assert response.status_code == expected, response.content
    assert facts() == before


@pytest.mark.parametrize("failure", ["feedback", "issuance-notification", "invitation"])
def test_issuance_outcome_failure_is_atomic_and_deliberate_retry_is_exactly_once(
    actors, monkeypatch, failure
):
    from compass.good_moral import services
    from tests.test_good_moral_verification import issue, prepare, verify

    student, inspector, counselor = actors
    staff = auth_client(inspector)
    saved = record(staff, create(auth_client(student), "GRADUATE"))
    item = GoodMoralRequest.objects.get(pk=saved["id"])
    verify(item, inspector)
    prepare(item, inspector)
    before = facts()
    notification = services.create_notification_for_event

    def fail_feedback(**kwargs):
        raise RuntimeError("Synthetic feedback failure")

    def fail_notification(**kwargs):
        target = (
            "good_moral.issued" if failure == "issuance-notification" else "feedback.invitation"
        )
        if kwargs["event"] == target:
            raise RuntimeError("Synthetic notification failure")
        return notification(**kwargs)

    with monkeypatch.context() as patch:
        if failure == "feedback":
            patch.setattr(services, "ensure_feedback_opportunity", fail_feedback)
        else:
            patch.setattr(services, "create_notification_for_event", fail_notification)
        with pytest.raises(RuntimeError, match="Synthetic"):
            issue(item, counselor)
    assert facts() == before
    issue(item, counselor)
    committed = facts()
    issue(item, counselor)
    assert facts() == committed
    assert FeedbackOpportunity.objects.filter(source_id=item.pk).count() == 1
    assert (
        AuditEvent.objects.filter(action="good_moral.issued", target_id=str(item.pk)).count() == 1
    )


@pytest.mark.parametrize("cancellation_first", [False, True])
def test_real_postgresql_cancellation_and_preparation_preserve_one_terminal_history(
    actors, cancellation_first
):
    from compass.audit.context import AuditContext
    from compass.good_moral.services import cancel_request, prepare_request
    from tests.test_good_moral_verification import verify
    from tests.test_good_moral_verification_concurrency import serial_race

    student, inspector, counselor = actors
    saved = record(auth_client(inspector), create(auth_client(student), "GRADUATE"))
    item = GoodMoralRequest.objects.get(pk=saved["id"])
    verify(item, inspector)
    item.refresh_from_db()
    version = item.updated_at.isoformat()

    def prepare():
        return prepare_request(
            actor=inspector,
            request_id=item.pk,
            context=AuditContext.user(inspector),
            expected_resource_version=version,
        )

    def cancel():
        return cancel_request(
            actor=counselor,
            request_id=item.pk,
            reason="Synthetic race",
            self_service=False,
            context=AuditContext.user(counselor),
        )

    results = serial_race(item, *((cancel, prepare) if cancellation_first else (prepare, cancel)))
    item.refresh_from_db()
    assert item.status == "CANCELLED"
    assert Verification.objects.get().invalidated_at is not None
    assert Identity.objects.get().bound_request_id == item.pk
    assert (
        AuditEvent.objects.filter(
            action="good_moral.request.cancelled", target_id=str(item.pk)
        ).count()
        == 1
    )
    assert not FeedbackOpportunity.objects.exists()
    assert results[0][0] == "committed"
    assert results[1][0] == ("GoodMoralPreparationChanged" if cancellation_first else "committed")


def test_real_postgresql_replacement_racing_old_number_reuse_keeps_reservation(actors):
    from tests.test_good_moral_receipts import edit
    from tests.test_good_moral_verification_concurrency import outcome, worker

    student, inspector, _ = actors
    staff = auth_client(inspector)
    first = record(staff, create(auth_client(student), "GRADUATE"), "GM4-OLD")
    second = create(auth_client(student), "CURRENT_STUDENT")
    original = GoodMoralRequest.objects.get(pk=first["id"])
    other = GoodMoralRequest.objects.get(pk=second["id"])
    before = AuditEvent.objects.count()
    barrier = Barrier(2)

    def change(item, number):
        barrier.wait(timeout=10)
        return outcome(lambda: edit(item, inspector, {"official_receipt_number": number}))

    with ThreadPoolExecutor(max_workers=2) as pool:
        replacement = pool.submit(worker, lambda: change(original, "GM4-NEW"))
        reuse = pool.submit(worker, lambda: change(other, " gm4-old "))
        assert replacement.result(timeout=20)[0] == "committed"
        assert reuse.result(timeout=20)[0] == "ReceiptConflict"
    assert set(Identity.objects.values_list("normalized_key", flat=True)) == {"GM4-OLD", "GM4-NEW"}
    assert Identity.objects.filter(bound_request=original).count() == 2
    assert Assignment.objects.filter(request=original).count() == 2
    assert Assignment.objects.get(request=original, is_current=True).display_number == "GM4-NEW"
    assert not Assignment.objects.filter(request=other).exists()
    assert Mutation.objects.count() == 2
    assert AuditEvent.objects.count() == before + 2  # Receipt revision and ordinary correction.


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
def test_real_browser_next_django_postgres_workflow(actors, live_server, variant):
    origin = os.environ.get("COMPASS_GM_REAL_FRONTEND_URL")
    if not origin:
        pytest.skip("Opt-in loopback Next build/live-server proxy required")
    assert urlparse(origin).hostname in {"localhost", "127.0.0.1"}
    from playwright.sync_api import expect, sync_playwright

    student, inspector, counselor = actors
    tokens = {
        actor.pk: auth_client(actor).cookies[settings.AUTH_SESSION_COOKIE_NAME].value
        for actor in actors
    }
    from tests.test_good_moral_verification_concurrency import worker

    with ThreadPoolExecutor(max_workers=1) as database, sync_playwright() as playwright:

        def db(fn):
            return database.submit(worker, fn).result(timeout=20)

        browser = playwright.chromium.launch()
        contexts = []

        def page_for(actor):
            context = browser.new_context(service_workers="block")
            contexts.append(context)
            context.add_init_script(
                "window.__gmPrintCalls=0; window.print=()=>window.__gmPrintCalls++"
            )
            # Persisted real opaque session; browser credentials remain HttpOnly.
            token = tokens[actor.pk]
            context.add_cookies(
                [
                    {
                        "name": settings.AUTH_SESSION_COOKIE_NAME,
                        "value": token,
                        "url": origin,
                        "httpOnly": True,
                        "sameSite": "Lax",
                    }
                ]
            )
            context.route(
                "**/*",
                lambda route: (
                    route.continue_()
                    if urlparse(route.request.url).hostname in {"localhost", "127.0.0.1"}
                    else route.abort()
                ),
            )
            return context.new_page()

        def api(page, method, path, body=None):
            # Same-origin browser fetches, including actual CSRF bootstrap; no route fulfilment.
            result = page.evaluate(
                """async ({method,path,body}) => {
              const csrf = await fetch('/api/v1/auth/csrf').then(r=>r.json());
              const r = await fetch(path, {method, credentials:'include', headers: {
                'Content-Type':'application/json', 'X-CSRFToken':csrf.csrf_token,
                'Idempotency-Key':crypto.randomUUID()},
                ...(body ? {body:JSON.stringify(body)} : {})});
              return {status:r.status, body:await r.json()};
            }""",
                {"method": method, "path": path, "body": body},
            )
            assert result["status"] in {200, 201}, result
            return result["body"]

        try:
            student_page = page_for(student)
            student_page.goto(origin + "/portal")
            route = "current-student" if variant == "CURRENT_STUDENT" else "graduate"
            body = (
                {"semester": "First Semester"}
                if variant == "CURRENT_STUDENT"
                else {
                    "degree": "Bachelor of Science in Information Systems",
                    "graduation_date": "2020-01-01",
                }
            )
            created = api(student_page, "POST", f"/api/v1/good-moral/me/requests/{route}", body)
            assert created["official_receipt_number"] == ""
            student_page.goto(origin + f"/portal/good-moral/{created['id']}")
            expect(student_page.get_by_text(re.compile("UCN Cashier")).first).to_be_visible()
            staff_page = page_for(inspector)
            path = f"/api/v1/good-moral/requests/{created['id']}"
            staff_page.goto(origin + f"/portal/good-moral/{created['id']}")
            staff_page.get_by_role("button", name="Correct certificate details", exact=True).click()
            number = f"GM4-BROWSER-{uuid4()}"
            staff_page.get_by_label("Receipt number", exact=True).fill(number)
            staff_page.get_by_label("Receipt date", exact=True).fill(
                institution_today().isoformat()
            )
            staff_page.get_by_label("Receipt amount", exact=True).fill("80.00")
            staff_page.get_by_role("button", name="Save changes", exact=True).click()
            expect(
                staff_page.get_by_role("button", name="Verify receipt", exact=True)
            ).to_be_visible()
            assert not db(lambda: Verification.objects.exists())
            assert (
                db(
                    lambda: str(
                        Identity.objects.get(normalized_key=number.upper()).bound_request_id
                    )
                )
                == created["id"]
            )
            staff_page.get_by_role("button", name="Verify receipt", exact=True).click()
            dialog = staff_page.get_by_role("alertdialog")
            expect(dialog.get_by_role("checkbox")).not_to_be_checked()
            expect(dialog.get_by_role("button", name="Verify receipt", exact=True)).to_be_disabled()
            dialog.get_by_role("checkbox").check()
            dialog.get_by_role("button", name="Verify receipt", exact=True).click()
            expect(
                staff_page.get_by_role("heading", name="Receipt inspection recorded", exact=True)
            ).to_be_visible()
            staff_page.get_by_role("button", name="Done", exact=True).click()
            evidence = db(lambda: Verification.objects.get())
            assert evidence.verified_by_id == inspector.pk
            staff_page.get_by_role("button", name="Mark ready for issuance", exact=True).click()
            # Existing preparation is an explicit confirmation.
            ready_dialog = staff_page.get_by_role("alertdialog")
            ready_dialog.get_by_role("button", name="Mark ready", exact=True).click()
            expect(staff_page.get_by_text("Ready for issuance", exact=True).first).to_be_visible()
            ready_dialog.get_by_role("button", name="Done", exact=True).click()
            staff_page.get_by_role("button", name="Correct certificate details", exact=True).click()
            staff_page.get_by_label("Receipt number", exact=True).fill(number + "-R")
            staff_page.get_by_role("button", name="Save changes", exact=True).click()
            expect(
                staff_page.get_by_role("button", name="Verify receipt", exact=True)
            ).to_be_visible()
            assert db(lambda: Verification.objects.get(pk=evidence.pk).invalidated_at) is not None
            assert db(lambda: Identity.objects.filter(normalized_key=number.upper()).exists())
            staff_page.get_by_role("button", name="Verify receipt", exact=True).click()
            dialog = staff_page.get_by_role("alertdialog")
            expect(dialog.get_by_role("checkbox")).not_to_be_checked()
            dialog.get_by_role("checkbox").check()
            dialog.get_by_role("button", name="Verify receipt", exact=True).click()
            expect(
                staff_page.get_by_role("heading", name="Receipt inspection recorded", exact=True)
            ).to_be_visible()
            staff_page.get_by_role("button", name="Done", exact=True).click()
            evidence = db(lambda: Verification.objects.get(invalidated_at__isnull=True))
            assert db(lambda: Verification.objects.count()) == 2
            assert staff_page.evaluate("window.__gmPrintCalls") == 0
            staff_page.get_by_role("button", name="Mark ready for issuance", exact=True).click()
            staff_page.get_by_role("alertdialog").get_by_role(
                "button", name="Mark ready", exact=True
            ).click()
            expect(staff_page.get_by_text("Ready for issuance", exact=True).first).to_be_visible()
            issuer_page = page_for(counselor)
            issuer_page.goto(origin + f"/portal/good-moral/{created['id']}")
            issuer_page.get_by_role("button", name="Issue certificate", exact=True).click()
            issuer_page.get_by_role("alertdialog").get_by_role(
                "button", name="Issue certificate", exact=True
            ).click()
            expect(issuer_page.get_by_text("Issued", exact=True).first).to_be_visible()
            row = db(lambda: GoodMoralRequest.objects.get(pk=created["id"]))
            assert row.issued_receipt_verification_id == evidence.pk
            assert db(lambda: FeedbackOpportunity.objects.filter(source_id=row.pk).count()) == 1
            assert (
                db(
                    lambda: AuditEvent.objects.filter(
                        action="good_moral.issued", target_id=str(row.pk)
                    ).count()
                )
                == 1
            )
            response = issuer_page.context.request.get(origin + path + "/pdf")
            assert response.status == 200 and response.body().startswith(b"%PDF")
            safe = api(student_page, "GET", f"/api/v1/good-moral/me/{row.pk}")
            assert "receipt_inspection" not in safe and "receipt_identity" not in safe
            assert safe["status"] == "ISSUED"
        finally:
            for context in contexts:
                context.close()
            browser.close()
