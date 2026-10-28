"""Disposable canonical upgrade/reversal and frozen issued-document preservation."""

import pytest
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from compass.audit.context import AuditContext
from compass.documents.rendering import render_document_html
from compass.good_moral.models import GoodMoralRequest
from compass.good_moral.services import (
    build_certificate_render_context,
    issue_request,
    prepare_request,
)
from tests.test_good_moral import sync_policy
from tests.test_good_moral_receipts import activate, person, request_for

BASE = ("good_moral", "0001_canonical_baseline")
TARGET = ("good_moral", "0003_receipt_verification")


@pytest.mark.django_db(transaction=True)
def test_populated_canonical_upgrade_and_empty_history_reverse_reapply():
    sync_policy()
    student = person("historical")
    MigrationExecutor(connection).migrate([BASE])
    try:
        historical = (
            MigrationExecutor(connection)
            .loader.project_state([BASE])
            .apps.get_model("good_moral", "GoodMoralRequest")
        )
        item = historical.objects.create(
            student_id=student.pk,
            variant="GRADUATE",
            official_receipt_number="Old–Unicode",
            official_receipt_amount=250,
        )
        original = historical.objects.filter(pk=item.pk).values().get()
        MigrationExecutor(connection).migrate([TARGET])
        assert GoodMoralRequest.objects.filter(pk=item.pk).values(*original).get() == original
        with connection.cursor() as cursor:
            cursor.execute("SELECT mode FROM good_moral_goodmoralreceiptledger WHERE id=1")
            assert cursor.fetchone()[0] == "DORMANT"
        # No ledger evidence exists; a disposable reversal preserves the source request.
        MigrationExecutor(connection).migrate([BASE])
        MigrationExecutor(connection).migrate([TARGET])
        assert GoodMoralRequest.objects.filter(pk=item.pk).values(*original).get() == original
    finally:
        MigrationExecutor(connection).migrate([TARGET])


@pytest.mark.django_db(transaction=True)
def test_nonempty_import_history_refuses_destructive_migration_reverse():
    sync_policy()
    request_for(official_receipt_number="OR-1")
    activate()
    with pytest.raises(RuntimeError, match="history"), transaction.atomic():
        MigrationExecutor(connection).migrate([BASE])
    assert TARGET in MigrationExecutor(connection).loader.applied_migrations
    assert GoodMoralRequest.objects.get().official_receipt_number == "OR-1"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("variant", ["CURRENT_STUDENT", "GRADUATE"])
@pytest.mark.parametrize("receipt", [False, True])
def test_issued_snapshots_and_rendered_html_are_unchanged_by_import(variant, receipt):
    sync_policy()
    actor = person("issuer", "COUNSELOR")
    facts = (
        {"official_receipt_number": "OR-HISTORICAL", "official_receipt_amount": 250}
        if receipt
        else {}
    )
    item = request_for(variant=variant, **facts)
    prepare_request(actor=actor, request_id=item.pk, context=AuditContext.user(actor))
    issued = issue_request(actor=actor, request_id=item.pk, context=AuditContext.user(actor))
    before = GoodMoralRequest.objects.filter(pk=item.pk).values().get()
    context = build_certificate_render_context(issued)
    html = render_document_html(
        issued.document_template_key, issued.document_template_version, context=context
    )[0]
    activate()
    issued.refresh_from_db()
    assert GoodMoralRequest.objects.filter(pk=item.pk).values().get() == before
    assert build_certificate_render_context(issued) == context
    assert (
        render_document_html(
            issued.document_template_key, issued.document_template_version, context=context
        )[0]
        == html
    )
