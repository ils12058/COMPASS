"""Issued F4/F6 PDFs and receipt fee facts remain preserved."""

import re
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from pypdf import PdfReader

from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.receipt_verification import operational_status
from tests.test_good_moral import auth_client, sync_policy
from tests.test_good_moral_receipts import person, request_for
from tests.test_good_moral_verification import issue, prepare, verify

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
def test_issued_pdf_and_fee_evidence_remain_stable(variant):
    sync_policy()
    counselor = person("issuer", "COUNSELOR")
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
    assert item.issued_receipt_verification.expected_amount == Decimal("80.00")
    assert item.issued_receipt_verification.currency == "PHP"
    client = auth_client(item.student)

    def pdf_content():
        response = client.get(f"/api/v1/good-moral/me/{item.pk}/pdf")
        assert response.status_code == 200
        body = b"".join(response.streaming_content) if response.streaming else response.content
        pages = PdfReader(BytesIO(body)).pages
        return [re.sub(r"\s+", " ", p.extract_text()).strip() for p in pages]

    original = pdf_content()
    assert pdf_content() == original
    assert GoodMoralRequest.objects.filter(pk=item.pk).values().get() == before
    status = operational_status(item, counselor)
    assert status["expected_amount"] == Decimal("80.00")
    assert status["currency"] == "PHP"
