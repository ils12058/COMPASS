# ruff: noqa: F811
"""Inspection evidence survives refused receipt-schema downgrade."""

import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor

from compass.good_moral.models import GoodMoralReceiptVerification as Verification
from tests.test_good_moral_verification import approved, scene, verify  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


def test_inspection_evidence_is_preserved_when_downgrade_is_refused(scene):
    actor, item = scene
    inspection = verify(item, actor).receipt_verification_result
    before = Verification.objects.filter(pk=inspection.pk).values().get()
    with pytest.raises(IrreversibleError):
        MigrationExecutor(connection).migrate([("good_moral", "0002_receipt_identity_and_history")])
    assert Verification.objects.filter(pk=inspection.pk).values().get() == before
