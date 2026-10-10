"""Office-wide preparation and Counselor-only issuance remain separate authorities."""

from .models import GoodMoralRequest, GoodMoralStatus
from .services import GoodMoralNotPermitted, _validate_counselor, _validate_operational


def _prefix(*, status, waiting_field, limit):
    return tuple(
        GoodMoralRequest.objects.filter(status=status)
        .select_related("student")
        .only(
            "id",
            waiting_field,
            "student_id",
            "student__first_name",
            "student__middle_name",
            "student__last_name",
            "student__suffix",
        )
        .order_by(waiting_field, "id")[:limit]
    )


def preparation_requests(*, actor, limit):
    try:
        _validate_operational(actor, "good_moral.prepare")
    except GoodMoralNotPermitted:
        return ()
    return _prefix(status=GoodMoralStatus.REQUESTED, waiting_field="created_at", limit=limit)


def issuance_requests(*, actor, limit):
    try:
        _validate_counselor(actor, "good_moral.issue")
    except GoodMoralNotPermitted:
        return ()
    return _prefix(
        status=GoodMoralStatus.READY_FOR_ISSUANCE, waiting_field="prepared_at", limit=limit
    )
