# GM-OR-2 handoff

GM-OR-1 provides identity reservations, immutable revisions, exact review tokens, durable correction replay, source observations and a database writer boundary. It deliberately provides **no physical inspection attestation, verification capability, PHP 80 comparison, mandatory receipt-completeness gate, payment state or Registrar tracking**.

GM-OR-2 should:

1. Confirm the actual Cashier numbering scope/normalization before any real population. Complete separately authorized count inventory, quarantine/alias review, source reconciliation and production writer fencing. The current import command is disposable-only and is not authorization for a live cutover.
2. Add an exact-assignment-revision physical inspection record with actual verifier, aware time, method and invalidation provenance. Import `recorded_at` is observation time; neither it nor request/preparation/issue/receipt dates proves inspection. Never backfill fictional verification.
3. Add the focused `good_moral.verify_receipt` capability only after an approved inspector grant matrix, with current GCO role/dependency boundaries. Preserve GSS clerical rights, Counselor-only final issuance and existing account governance. Head Guidance/IT do not gain transfer or inspection authority automatically.
4. Implement a separate intentional Verify action. Saving receipt facts does not verify them; a physical-inspection claim does not mean independent Cashier-ledger confirmation.
5. Require complete valid number/date/amount, unique eligible current ownership, no dispute/ambiguity, exact active inspection and an applicable approved fee decision before new READY/ISSUED transitions. Recheck under the existing request/identity transaction fence and final review tokens. Old issued downloads/print remain available.
6. Invalidate inspection on substantive receipt revision. Preserve unchanged receipt inspection across unrelated certificate correction, while preserving the existing READY→REQUESTED preparation reset. Bind final issue provenance to the exact revision/attestation/policy. Keep issue replay notification/feedback effects exactly once.
7. Treat PHP 80.00 for both F4/F6 as **team-reported practice until institutionally confirmed**. Use a versioned code-owned expected policy initially, with approved applicability/reference date and captured decision evidence. No effective date, waiver, refund, excess-payment or exception rule is established by this PR. Preserve historical paid amounts.
8. Agree on existing READY transition/re-review and unresolved legacy receipt treatment before activating gates. Do not grandfather unrecorded physical inspection, invent duplicate owners, or revoke historical certificates automatically.

Exceptional disputed-identity reconciliation remains a separate, unimplemented authority/workflow requiring institutional approval and durable review/evidence. Existing ordinary services cannot rebind/release identity rows; future reconciliation needs a separately reviewed database/service change rather than an IT override or hidden bypass.

GM-OR-3 owns the full receipt entry/inspection/history and Student Cashier/GCO next-step interface. GM-OR-1 changed only the existing correction contract/stale-state handling. Existing issue confirmation, finalized PDF preview/download and browser printing remain in place; dry sealing is external.

GM-OR-4 still needs integrated authorized migration rehearsal, true data-volume evidence, inspection/fee race tests, historical PDF comparisons, browser/accessibility/UAT and separate release approval. Passing this foundation's tests does not approve institutional policy or prove deployed-data cleanliness.
