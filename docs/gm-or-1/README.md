# GM-OR-1 — Permanent receipt identity and assignment history

Base: `integration/ux15-modernization`, fetched at **`7f0c75e970f26cc832158f4609295f0dd40938c5`**. Feature branch: `feature/gm-or-1-receipt-identity-history`. This implements the merged [GM-OR-0 Option C design](../gm-or-0/README.md).

**Runtime status: DORMANT by default.** The additive migration installs empty ledger tables and a dormant writer-control row. It does not import receipt data, enforce a new fee, require a receipt for preparation/issuance, or activate an operational writer transition. Existing receipt correction behavior remains compatible while dormant. Permanent non-reuse applies to identities reserved by the activated ledger; do not claim protection for overwritten/unobserved old numbers or dormant writes.

Implemented:

- `GoodMoralReceiptIdentity`: globally unique `GM_OR_V1` key, permanent request binding/reservation and explicit legacy ambiguity.
- `GoodMoralReceiptAssignment`: immutable fact revisions, one-way closure, exact predecessor/sequence and protected current-claim indexes.
- `GoodMoralReceiptMutation`: durable operation UUID/fingerprint/result reference, including no-op receipts.
- `GoodMoralReceiptImportBatch` and singleton `GoodMoralReceiptLedger`: resumable source observations and database-owned DORMANT → FENCED → ACTIVE transition.
- PostgreSQL ownership, immutability, projection and cutover guards; atomic versioned corrections; content-minimized Audit events and safe conflicts.
- Synthetic-only inventory/import command and restricted operational API summaries. Minimal existing-form adaptation sends active receipt review tokens, preserves stale drafts and requires deliberate review.

The three support tables are a documented refinement of the two core models: durable operation replay, resumable source identity, and a database writer fence cannot safely be represented by a process flag or mutable receipt facts on the identity. No payment or verification subsystem was added.

| Document | Contents |
| --- | --- |
| [Identity and normalization](identity-and-normalization.md) | Exact equality algorithm, scope and assumptions |
| [Assignment revisions](assignment-revisions.md) | Model invariants, correction and snapshot ownership |
| [Import and cutover](legacy-import-and-cutover.md) | Disposable rehearsal, source writers, quarantine and rollback |
| [Concurrency and Audit](concurrency-and-audit.md) | Transactions, replay and race proofs |
| [Migration validation](migration-validation.md) | Additive migration, guards and rehearsal |
| [GM-OR-2 handoff](gm-or-2-handoff.md) | Future inspection/fee/issuance work |
| [Validation](validation.md) | Executed checks, failures/fixes and limits |

Institutional approval of the complete printed numbering scope, ASCII/case policy, authorized data inventory and operational cutover remains outstanding. No live database, SSH, deployment, real-data inspection, live migration/backfill, fee-policy activation or automatic merge is part of this slice.
