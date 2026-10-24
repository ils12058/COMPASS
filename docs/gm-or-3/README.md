# GM-OR-3 — Receipt inspection and Student experience

Verified starting integration: **`09c7fd82fb1d77cdc1f47d9435d122a2a853ca56`**. Isolated branch `feature/gm-or-3-receipt-experience`, targeting `integration/ux15-modernization`. This consumes the merged GM-OR-1/2 contract; no backend, capability, migration, fee provider or OpenAPI contract changes.

The existing Good Moral detail now presents saved OR facts, backend inspection status/blockers, approved expected fee when supplied, actual inspector account reference/time and bounded change metadata. An authorized backend action opens an explicit personal physical-inspection confirmation. Entry and inspection remain separate. Current request/revision/facts and operation UUID are frozen for review; uncertainty never causes automatic resubmission.

Existing correction, preparation and Counselor issuance remain on the same page. Corrections explain inspection invalidation versus preserved unchanged inspection; stale drafts remain available through transient refresh failure. Final issuance retains the exact review tokens and frozen reviewed facts. PDF preview/download/native print components are unchanged.

Pending Student F4/F6 detail gives concise Cashier → physical OR → GCO → request-status guidance. No amount is advertised without an approved Student-safe contract; no receipt/payment fields or online payment step are added to creation. Internal receipt history, inspector references and runtime mode remain operational-only.

**Operational state remains DORMANT.** No Verify action appears in DORMANT or FENCED; existing dormant processing stays compatible. ACTIVE uses backend `can_verify`, preparation/issue flags and blockers, with no client pricing or privilege authority. The unavailable approved-fee provider and absent real inspector grants are unchanged.

| Document | Purpose |
| --- | --- |
| [Staff workflow](staff-receipt-workflow.md) | Entry, inspection, history, correction, preparation/issuance |
| [Student guidance](student-guidance.md) | Safe next steps and receipt-free creation |
| [State and safety](frontend-state-and-safety.md) | Review identity, replay, refresh and account boundaries |
| [Accessibility and responsive](accessibility-and-responsive.md) | Dialog, keyboard, focus, status and layout evidence |
| [GM-OR-4 handoff](gm-or-4-handoff.md) | Integration/UAT and institutional release blockers |
| [Validation](validation.md) | Executed checks, distinct counts, fixes and evidence limits |

No automatic merge, deployment, SSH, institutional records, live import/migration, inspector grant or policy activation is part of this slice.
