# Customer Feedback and CSM uncertainty recovery

## Existing error and backend contracts

Both one-time forms already retain an exact request body, its fingerprint, and an `Idempotency-Key` for supported retries. The backend validates that key and fingerprint, returns a completed same-key response when available, rejects a different fingerprint as `idempotency_key_conflict`, reports `idempotency_in_progress`, and returns `idempotency_unavailable` when it cannot safely reserve, complete, or release the replay boundary. Customer Feedback and CSM service transactions lock the Student-owned opportunity, reject a consumed instrument, save its response, and update the corresponding opportunity timestamp atomically.

The authorized opportunity read supplies separate `customer_feedback_submitted` / `can_submit_customer_feedback` and `csm_submitted` / `can_submit_csm` fields. A submitted flag proves that the matching opportunity/instrument is consumed. It does not identify which request body was received. No backend change was needed.

## Recovery behavior

Network failures, HTTP 408, and HTTP 5xx are treated as uncertain. The form keeps its original body/fingerprint/key, locks editing, and performs one fresh no-cache opportunity read. If the relevant form is submitted, it shows an accurate already-submitted state without claiming that the exact retained body was confirmed. If still unsubmitted and eligible, the user can deliberately replay the exact same intent/key. A failed status read retains the intent and exposes Check status; it does not claim success or create a new key.

Already-submitted conflicts and key conflicts also reconcile through the canonical read. When a key conflict is resolved by a fresh unsubmitted status, the old intent is discarded; the user must review and explicitly confirm a new intent with a new key. A deterministic invalid key is not presented as a retryable uncertainty. Authorization/not-found failures preserve unresolved intent and prevent unsafe retry. An in-flight guard prevents duplicate Submit, Check Status, and replay operations.

Customer Feedback and CSM use the correct independent flag for the same opportunity. Optional respondent identity stays blank unless the Student enters it. CSM retains valid numeric zero/N/A choices. Questionnaire wording, payloads, ownership, privacy safeguards, and one-time submission rules remain unchanged.

## Limits

The backend's idempotency store and transactional services were source-audited; there are no backend modifications in this branch. Synthetic frontend fixtures verify the UI decision paths, not a live Redis failure, database race, authorization backend, or deployment. Canonical opportunity state can establish that a particular instrument is submitted but cannot prove the exact response body. These limitations remain explicit in [follow-ups](followups.md).

## Validation

`fe/tests/ux15-feedback-csm.browser.mjs`: 27/27 Chromium and 27/27 WebKit checks passed. Coverage includes lost response after simulated commit, HTTP 408/500/503, idempotency in progress and key conflict, invalid key, same-body/key replay, status 503/403/404, correct already-submitted flags, duplicate clicks, optional identity, CSM zero, and non-confusion between the instruments. See [validation](validation.md) for the complete run record.
