"""Durable mutation retry receipts, independent from encrypted professional content."""

from functools import wraps

from django.db import transaction

from . import policy
from .errors import FollowUpConflict
from .models import GuidanceFollowUpMutation


def durable_mutation(function):
    @wraps(function)
    def execute(*, mutation_key=None, mutation_fingerprint=None, **kwargs):
        # Domain callers without transport identity still use optimistic concurrency. HTTP callers
        # always provide a durable key, including during retries after an uncertain response.
        if mutation_key is None:
            return function(**kwargs)
        from .services import _creation_key, _fingerprint, _load

        with transaction.atomic():
            actor = policy.current_actor(kwargs["actor"], manage=True, lock=True)
            digest = _creation_key(actor, mutation_key)
            fingerprint = _fingerprint(mutation_fingerprint)
            previous = GuidanceFollowUpMutation.objects.filter(key_digest=digest).first()
            if previous is not None:
                if (
                    previous.request_fingerprint != fingerprint
                    or previous.action != function.__name__
                    or previous.followup_id != kwargs["followup_id"]
                ):
                    raise FollowUpConflict(
                        "This confirmation was already used for another request."
                    )
                item = _load(previous.followup_id)
                if (
                    previous.action == "reassign_followup"
                    and item.visibility == "OPERATIONAL"
                    and policy.in_operational_scope(actor, item.student_id)
                ):
                    policy.valid_student(item.student_id)
                else:
                    policy.require_followup(actor, item, manage=True)
                if function.__name__ == "record_activity":
                    return item, item.events.get(revision=previous.revision)
                return item
            result = function(**{**kwargs, "actor": actor})
            item = result[0] if function.__name__ == "record_activity" else result
            GuidanceFollowUpMutation.objects.create(
                followup=item,
                actor=actor,
                key_digest=digest,
                request_fingerprint=fingerprint,
                action=function.__name__,
                revision=item.version,
            )
            return result

    return execute
