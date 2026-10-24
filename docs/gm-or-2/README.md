# GM-OR-2 — Physical receipt inspection and guarded issuance

Verified base: `integration/ux15-modernization` at `ef2ba91777ce75391876c36211b2cde83f02188f` (2026-10-24 Asia/Manila). Isolated branch: `feature/gm-or-2-receipt-verification`. Builds on merged GM-OR-0 and GM-OR-1; those historical documents and migrations are unchanged.

The implementation records a personally attributable **physical Official Receipt inspection of one exact immutable assignment revision**. It does not independently authenticate Cashier payment, reconcile a ledger, confirm cleared funds, scan receipts or detect fraud. Saving receipt facts does not inspect them. Good Moral lifecycle statuses remain unchanged.

Implemented: protected verification evidence and issuance references; focused capability without baseline grants; explicit authenticated inspection action; code-owned approved-fee decision contract; exact-revision preparation/issuance gates; correction/cancellation invalidation; durable replay; PostgreSQL guards; restricted operational projections; API/Orval compatibility; synthetic policy, migration and race tests.

**Default runtime remains DORMANT.** The additive migration creates no inspections, imports no receipts, changes no writer mode and grants no inspector rights. The operational approved-fee provider returns `None`. DORMANT operations remain compatible. FENCED refuses changes. ACTIVE requires an approved applicable decision and an actual inspection before new readiness/issuance. Synthetic fixtures alone supply approved decisions for tests.

| Document | Purpose |
| --- | --- |
| [Verification domain](verification-domain.md) | Model, exact binding, history and replay |
| [Authorization](authorization-and-capabilities.md) | Role/capability/account fences and explicit grants |
| [Fee policy](fee-policy.md) | Reported amount versus approved decisions |
| [Preparation and issuance](preparation-and-issuance.md) | Gates, tokens, blockers and legacy READY |
| [Concurrency and Audit](concurrency-and-audit.md) | Locking, races, rollback and residual limits |
| [Migration and release](migration-and-release.md) | Additive schema, preservation and activation blockers |
| [GM-OR-3 handoff](gm-or-3-handoff.md) | Exact contracts and deferred UX |
| [Validation](validation.md) | Executed evidence, failures/fixes, counts and CI |

Institutional fee authority/applicability, inspector grants, Cashier identifier conventions, authorized legacy inventory/reconciliation, pending READY treatment and controlled writer cutover remain outstanding. Engineering validation does not approve them. No deployment, SSH, live-data access, real-data migration, operational activation or automatic merge is authorized by this slice.
