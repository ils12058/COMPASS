# Concurrency, operation replay and Audit

Active receipt corrections run inside the existing `update_request` transaction. They lock the request, freshly validate the actor's active GCO role/capability and Audit attribution, validate exact request/fact-revision review tokens, then lock existing identities in canonical-key order before revision rows. Existing assisted creation/issuance Student locks remain unchanged; receipt correction introduces no Student lock. The database control shared lock prevents an import transition from overtaking in-flight source writes.

An absent proposed key cannot be locked in advance. The named unique identity index arbitrates insertion under a nested savepoint. Only `gm_receipt_identity_key_uniq` maps to `good_moral_receipt_conflict` with safe text: “Official Receipt number already recorded. Check the number or ask GCO for review.” Other IntegrityErrors are not disguised as duplicate receipts. All losing request/revision/identity/Audit changes roll back.

`GoodMoralReceiptMutation.operation_id` is globally unique. Its fingerprint binds actor, request, correction operation type, original request version, intended receipt revision and full correction payload. Exact replay is checked before stale/terminal rejection, so an already committed request can be acknowledged without a second claim/event or revived edit. A UUID reused for another actor/request/payload conflicts. Concurrent reuse on different requests rolls back the losing identity as well as its operation.

The response preserves the existing canonical request detail and adds `receipt_mutation_result` with the original result revision and request version. This is a deliberate compatibility refinement: after a later correction/cancellation/issue, an old replay identifies its committed result while the surrounding resource shows **current** state. It never overwrites the resource with its old result. No-op mutations also have durable replay receipts but create no claim or success Audit event.

For active receipt input, PATCH accepts `expected_resource_version`, `expected_receipt_revision` (UUID or explicit null), and `receipt_operation_id`. Omitted fields are rejected only for active receipt mutations; dormant and existing non-receipt corrections stay compatible. Operational detail adds bounded receipt mode/state/revision/history. No global lookup or Student write endpoint exists. Safe new 409 codes are receipt conflict, changed review, paused cutover and existing idempotency-key conflict; malformed/missing active intent uses the existing 422 envelope.

Minimal form adaptation retains an operation UUID for unchanged intent, submits the reviewed tokens only when ledger-owned receipt fields change, and keeps `retry:false`. A stale/uncertain result refreshes saved state while keeping the draft, shows the latest receipt separately, disables Save until deliberate review and never automatically replays the correction. Duplicate errors keep input and display controlled copy.

## PostgreSQL evidence

New tests use independent connections, barriers and request-lock events. They assert one committed identity/revision/operation/event, safe losers and final lifecycle—not just HTTP codes—for same absent key (including cross-variant), same-request competing edits, replacement, exact concurrent replay, conflicting operation UUID reuse, correction versus preparation/cancellation/issuance, source-write versus import fence, active writer versus import, and lock timeout followed by deliberate recovery. Stale request and receipt tokens are independently tested. Constraint and Audit failures leave no partial reservation/history/projection.

A lock timeout is a transaction failure; this slice does not silently rerun consequential mutations. The caller refreshes and deliberately retries. Database-owner tampering and arbitrary DROP/TRUNCATE are outside ordinary-write guarantees; deployment roles/backups still require governance.

## Audit

New actions: `good_moral.receipt_assigned`, `good_moral.receipt_revised`, `good_moral.receipt_removed`, `good_moral.receipt_legacy_imported`. Metadata is limited to revision/batch references, sequence, transition classification and prior-revision reference. Existing `good_moral.request_updated` / return-to-preparation events remain. Actor provenance comes from the authenticated operator; import uses SYSTEM and observation time, never a fabricated historical inspector.

Raw numbers, amounts, payment facts, Student identities and arbitrary reasons are not put in general Audit metadata. Restricted claim rows contain the actual historical facts. Recording and projection changes share one transaction; a synchronous Audit failure rolls them all back. No new Email/Notification event is emitted for receipt edits; genuine issuance keeps its existing notification/feedback behavior.
