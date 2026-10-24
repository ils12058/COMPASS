# Preparation and issuance

| Writer mode | Behavior |
| --- | --- |
| DORMANT | Existing optional-receipt preparation/issuance/corrections remain compatible; inspection action unavailable |
| FENCED | Inspection and new transitions refuse through the real database control fence |
| ACTIVE, no applicable approved decision | New inspection/READY/ISSUED transitions fail closed; no fallback to the reported fee |
| ACTIVE, approved synthetic decision | Complete exact-revision inspection and all existing certificate gates required |

Inspection checks pending lifecycle, exact resource/revision review, current claim and unique BOUND request ownership, complete number/date/amount, institutional nonfuture date, applicable approved decision and exact amount. Ambiguity/dispute/quarantine/superseded or another request's claim cannot authorize work.

Preparation uses `expected_resource_version`, locks/revalidates eligible receipt and active inspection, compares its fee snapshot, retains `prepared_receipt_verification`, and keeps certificate-specific completeness checks. Existing GSS/Counselor preparation authority remains. A preparer does not attest that they performed someone else's inspection.

Final issuance retains `expected_preparation_version` and, in ACTIVE, additionally requires `expected_resource_version`, `expected_receipt_revision`, `expected_receipt_verification`. It verifies READY, reviewed preparation, exact current inspection and prepared evidence, current applicable fee decision/amount, existing F4 Student CURRENT/Inventory provenance, F6 facts, active supported form, template and actual Counselor identity. Receipt evidence is referenced atomically with form/template/issuer snapshots and the existing Issue Audit/notification/feedback opportunity. Already-ISSUED replay returns before prospective receipt gates and never repeats side effects.

| Safe 409 blocker | Meaning |
| --- | --- |
| `good_moral_receipt_missing` | No number-bearing claim |
| `good_moral_receipt_incomplete` | Missing/invalid receipt facts or future date |
| `good_moral_receipt_unverified` | Exact current inspection absent |
| `good_moral_receipt_conflict` | Ownership/identity requires GCO review; no other Student disclosed |
| `good_moral_receipt_fee_mismatch` | Actual amount differs from approved expected amount |
| `good_moral_receipt_policy_unresolved` | Missing/inapplicable/changed approved decision |
| `good_moral_receipt_changed` | Reviewed resource/revision/inspection no longer matches |
| `good_moral_receipt_cutover_required` | Inspection unavailable in this writer state |
| `good_moral_receipt_already_verified` | Existing attributable inspection retained |
| `idempotency_key_conflict` | Operation UUID bound to another intent |

Malformed input uses 422, denied authority 403, absent request 404, existing preparation/form/Student conflicts keep their existing envelopes. Operational action flags suppress receipt-blocked preparation/issuance; service checks remain authoritative.

A legacy READY record gains no fictional inspection. Under ACTIVE it cannot issue without inspection **and re-preparation**. An explicit real inspection of READY deliberately returns it to REQUESTED, clears preparation references and records the return event, then an authorized preparer must act again. Synthetic F4/F6 rehearsals cover this path. No bulk queue rewrite or live transition command is exposed. GCO must accept the eventual queue impact and controlled cutover treatment first.

Receipt correction invalidates before closing its exact revision; unrelated correction preserves inspection and resets preparation. Cancellation invalidates eligibility without releasing reservations. Historical issued facts, renderer, PDF authorization/release Audit, print subsystem and external dry sealing are unchanged.
