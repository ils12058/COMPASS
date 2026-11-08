"""Explicit receipt recording and physical-inspection evidence for synthetic stories."""

from uuid import uuid4

from compass.good_moral.receipt_identity import latest_revision
from compass.good_moral.receipt_verification import METHOD, verify_receipt
from compass.good_moral.services import update_request


def record_and_inspect(*, actor, request_id, changes, context):
    from compass.good_moral.models import GoodMoralRequest

    item = GoodMoralRequest.objects.get(pk=request_id)
    item = update_request(
        actor=actor,
        request_id=item.pk,
        changes=changes,
        context=context,
        expected_resource_version=item.updated_at.isoformat(),
        expected_receipt_revision=getattr(latest_revision(item), "pk", None),
        operation_id=uuid4(),
    )
    return verify_receipt(
        actor=actor,
        request_id=item.pk,
        expected_resource_version=item.updated_at.isoformat(),
        assignment_id=latest_revision(item).pk,
        operation_id=uuid4(),
        method=METHOD,
        context=context,
    )
