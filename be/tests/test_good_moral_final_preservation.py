"""Issued F4/F6 PDFs and fee evidence preserve the historical definition."""

import re
from dataclasses import replace
from io import BytesIO

import pytest
from pypdf import PdfReader

from compass.good_moral import receipt_fee_policy as fees
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.receipt_verification import operational_status
from tests.test_good_moral import auth_client, sync_policy
from tests.test_good_moral_receipts import person, request_for
from tests.test_good_moral_verification import issue, prepare, verify

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
@pytest.mark.parametrize("replacement", ["unavailable", "new_definition"])
def test_issued_pdf_and_provisional_evidence_survive_current_policy_change(
    monkeypatch, variant, replacement
):
    sync_policy()
    counselor = person("issuer", "COUNSELOR")
    from datetime import date
    from decimal import Decimal

    item = request_for(
        variant=variant,
        official_receipt_number="OR-HISTORICAL",
        official_receipt_date=date(2020, 1, 1),
        official_receipt_amount=Decimal("80.00"),
    )
    verify(item, counselor)
    prepare(item, counselor)
    item = issue(item, counselor)
    before = GoodMoralRequest.objects.filter(pk=item.pk).values().get()
    decision = fees.resolve_approved_fee(item=item, assignment=item.issued_receipt_assignment)
    assert item.issued_receipt_verification.fee_decision["status"] == "PROVISIONAL"
    client = auth_client(item.student)

    def pdf_content():
        response = client.get(f"/api/v1/good-moral/me/{item.pk}/pdf")
        assert response.status_code == 200
        body = b"".join(response.streaming_content) if response.streaming else response.content
        pages = PdfReader(BytesIO(body)).pages
        return [re.sub(r"\s+", " ", p.extract_text()).strip() for p in pages]

    original = pdf_content()
    successor = (
        None if replacement == "unavailable" else replace(decision, version="2", status="APPROVED")
    )
    monkeypatch.setattr(fees, "resolve_approved_fee", lambda **_: successor)
    assert pdf_content() == original
    assert GoodMoralRequest.objects.filter(pk=item.pk).values().get() == before
    assert operational_status(item, counselor)["fee_status"] == "PROVISIONAL"
    assert item.issued_receipt_verification.fee_decision["version"] == "1"
