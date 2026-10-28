# ruff: noqa: F811
"""Additive populated upgrade, zero fabricated evidence, disposable reversal safety."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from compass.good_moral.models import GoodMoralReceiptVerification as Verification
from compass.good_moral.models import GoodMoralRequest
from tests.test_good_moral import sync_policy
from tests.test_good_moral_receipts import activate, person
from tests.test_good_moral_verification import approved, scene, verify  # noqa: F401

BASE = ("good_moral", "0002_receipt_identity_and_history")
TARGET = ("good_moral", "0003_receipt_verification")
pytestmark = pytest.mark.django_db(transaction=True)


def test_populated_upgrade_preserves_all_source_and_legacy_claims_and_reapply():
    sync_policy()
    actor = person("historical-issuer", "COUNSELOR")
    student = person("historical")
    try:
        apps = MigrationExecutor(connection).loader.project_state([BASE]).apps
        Request = apps.get_model("good_moral", "GoodMoralRequest")
        from django.utils import timezone

        now = timezone.now()
        from compass.audit.context import AuditContext
        from compass.good_moral.services import issue_request, prepare_request
        from tests.test_good_moral_receipts import request_for

        rows = []
        for number, amount in [
            ("DUPLICATE", Decimal("250")),
            ("duplicate", Decimal("0")),
            ("", None),
        ]:
            item = request_for(
                student=student,
                official_receipt_number=number,
                official_receipt_amount=amount,
                official_receipt_date=date(2001, 1, 1),
            )
            prepare_request(actor=actor, request_id=item.pk, context=AuditContext.user(actor))
            rows.append(
                issue_request(actor=actor, request_id=item.pk, context=AuditContext.user(actor))
            )
        rows.append(
            Request.objects.create(
                student_id=student.pk,
                variant="GRADUATE",
                status="CANCELLED",
                cancelled_at=now,
                cancelled_by_id=actor.pk,
                cancellation_reason="Historical",
            )
        )
        activate()
        before = {r.pk: Request.objects.filter(pk=r.pk).values().get() for r in rows}
        Assignment = apps.get_model("good_moral", "GoodMoralReceiptAssignment")
        claims = list(Assignment.objects.order_by("id").values())
        MigrationExecutor(connection).migrate([BASE])
        MigrationExecutor(connection).migrate([TARGET])
        assert not Verification.objects.exists()
        for r in rows:
            assert (
                GoodMoralRequest.objects.filter(pk=r.pk).values(*before[r.pk]).get() == before[r.pk]
            )
            latest = GoodMoralRequest.objects.get(pk=r.pk)
            assert latest.issued_receipt_assignment_id is None
            assert latest.issued_receipt_verification_id is None
            assert latest.prepared_receipt_verification_id is None
        assert list(Assignment.objects.order_by("id").values()) == claims
        # Verification expansion alone can reverse; GM-OR-1 evidence remains intact.
        MigrationExecutor(connection).migrate([BASE])
        MigrationExecutor(connection).migrate([TARGET])
        assert not Verification.objects.exists()
    finally:
        MigrationExecutor(connection).migrate([TARGET])


def test_inspection_evidence_prevents_destructive_reverse(scene):
    actor, item = scene
    verification = verify(item, actor).receipt_verification_result
    with pytest.raises(RuntimeError, match="inspection history"), transaction.atomic():
        MigrationExecutor(connection).migrate([BASE])
    assert TARGET in MigrationExecutor(connection).loader.applied_migrations
    assert Verification.objects.get(pk=verification.pk).verified_by_id == actor.pk
