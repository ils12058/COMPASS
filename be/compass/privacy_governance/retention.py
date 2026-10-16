"""Retired in-app retention operations for the legacy disposition ledger.

COMPASS no longer manages retention rules, places holds, approves disposition or executes it
(ADR-114). Their routes are removed (ADR-115); these services remain as a fail-closed fallback
until PG-1A PR 3. Every one refuses unconditionally, before any lock, write, provider call, audit
event or task dispatch, so no capability grant or override can make one succeed. The legacy rule,
case and hold tables stay intact as internal historical evidence.
"""

from compass.common.errors import APIError

from .retention_models import (
    DispositionAction,
    RetentionCategory,
    RetentionTrigger,
)

DECOMMISSIONED_CODE = "retention_decommissioned"
DECOMMISSIONED_MESSAGE = (
    "Retention rule changes and disposition operations are no longer available in COMPASS."
)

# Historical contract vocabulary, kept only so legacy rules and cases remain describable.
SUPPORTED = {
    RetentionCategory.GRADUATE_TRACER: (RetentionTrigger.SUBMITTED_AT, DispositionAction.ANONYMIZE),
    RetentionCategory.ECOUNSELING_RECORDING: (
        RetentionTrigger.MEDIA_READY_AT,
        DispositionAction.DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE,
    ),
    RetentionCategory.ECOUNSELING_TRANSCRIPT: (
        RetentionTrigger.MEDIA_READY_AT,
        DispositionAction.DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE,
    ),
}
SUPPORTED_CONTRACTS = {(category, 1): treatment for category, treatment in SUPPORTED.items()}
SUPPORTED_CONTRACTS.update(
    {
        (category, 2): (
            RetentionTrigger.MEDIA_READY_AT,
            DispositionAction.DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE,
        )
        for category in (
            RetentionCategory.ECOUNSELING_RECORDING,
            RetentionCategory.ECOUNSELING_TRANSCRIPT,
        )
    }
)


def decommissioned():
    raise APIError(409, DECOMMISSIONED_CODE, DECOMMISSIONED_MESSAGE)


def create_rule(*, actor, values, context):
    decommissioned()


def update_rule(*, actor, rule_id, expected_revision, values, context):
    decommissioned()


def transition_rule(*, actor, rule_id, expected_revision, activate, context):
    decommissioned()


def change_hold(*, actor, case_id, expected_revision, reason, release, context):
    decommissioned()


def approve_case(*, actor, case_id, expected_revision, context, retry=False):
    decommissioned()
