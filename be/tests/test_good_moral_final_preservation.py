"""GM-OR-4: issued F4/F6 content survives populated schema upgrade/import.

Actual authorized PDF responses are rendered before/after; normalized extracted
content is compared because PDF metadata/binary identity is not deterministic.
"""

import re
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from pypdf import PdfReader

from compass.audit.context import AuditContext
from compass.audit.models import AuditEvent
from compass.good_moral.models import GoodMoralReceiptIdentity as Identity
from compass.good_moral.models import GoodMoralReceiptVerification as Verification
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import (
    build_certificate_render_context,
    issue_request,
    prepare_request,
)
from tests.test_good_moral import auth_client, sync_policy
from tests.test_good_moral_receipts import activate, person, request_for

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
@pytest.mark.parametrize("legacy", ["blank", "non80", "duplicate"])
def test_historical_issued_pdf_and_source_facts_survive_upgrade_and_import(variant, legacy):
    sync_policy()
    counselor = person("historical-counselor", "COUNSELOR")
    number = "" if legacy == "blank" else "HISTORICAL-000123"
    amount = None if legacy == "blank" else Decimal("250.00")
    item = request_for(
        variant=variant,
        official_receipt_number=number,
        official_receipt_date=None if legacy == "blank" else date(2001, 1, 1),
        official_receipt_amount=amount,
    )
    prepare_request(actor=counselor, request_id=item.pk, context=AuditContext.user(counselor))
    issue_request(actor=counselor, request_id=item.pk, context=AuditContext.user(counselor))
    if legacy == "duplicate":
        # Same canonical key in the other variant, another Student, no arbitrary owner.
        request_for(
            variant="GRADUATE" if variant == "CURRENT_STUDENT" else "CURRENT_STUDENT",
            official_receipt_number=" historical-000123 ",
            official_receipt_date=date(2002, 1, 1),
            official_receipt_amount=Decimal("0.00"),
        )
    item.refresh_from_db()
    before = GoodMoralRequest.objects.filter(pk=item.pk).values().get()
    context = build_certificate_render_context(item)
    events = list(AuditEvent.objects.filter(action="good_moral.issued").values())
    client = auth_client(item.student)

    def pdf_content():
        response = client.get(f"/api/v1/good-moral/me/{item.pk}/pdf")
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "application/pdf"
        body = b"".join(response.streaming_content) if response.streaming else response.content
        document = PdfReader(BytesIO(body))
        return len(document.pages), [
            re.sub(r"\s+", " ", p.extract_text()).strip() for p in document.pages
        ]

    original_pdf = pdf_content()
    target = ("good_moral", "0003_receipt_verification")
    try:
        MigrationExecutor(connection).migrate([("good_moral", "0001_canonical_baseline")])
        MigrationExecutor(connection).migrate([target])
        activate()
        item.refresh_from_db()
        assert GoodMoralRequest.objects.filter(pk=item.pk).values().get() == before
        assert build_certificate_render_context(item) == context
        assert list(AuditEvent.objects.filter(action="good_moral.issued").values()) == events
        assert not Verification.objects.exists()
        assert item.issued_receipt_assignment_id is None
        assert item.issued_receipt_verification_id is None
        assert pdf_content() == original_pdf
        if legacy == "duplicate":
            identity = Identity.objects.get(normalized_key="HISTORICAL-000123")
            assert identity.state == "LEGACY_AMBIGUOUS" and identity.bound_request_id is None
    finally:
        MigrationExecutor(connection).migrate([target])
