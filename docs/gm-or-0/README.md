# GM-OR-0 — Good Moral Official Receipt integrity audit

Audit date: **2026-10-24 (Asia/Manila)**. Documentation only; no runtime, schema, capability, UI, or contract changes.

## Baseline and evidence labels

Fetched `origin/integration/ux15-modernization` and inspected **`80b719eb7fbeb86646228b4c013314e8e909876a`**, matching the supplied last-observed HEAD. Work is isolated on `audit/gm-or-0-receipt-integrity`; PR target is `integration/ux15-modernization`. The original checkout and other worktrees were not edited.

Throughout this package:

- **VERIFIED CODE FACT** means observed in that exact commit, with pinned source references in [current-state-audit.md](current-state-audit.md).
- **TEAM-REPORTED OPERATIONAL PRACTICE** means supplied by the project team in this audit request, without signed institutional policy evidence.
- **PROPOSED DESIGN** means a future implementation recommendation, not deployed behavior.
- **INSTITUTIONAL CONFIRMATION REQUIRED** means a decision that this audit does not authorize on behalf of UCN/GCO.

Repository tests and synthetic PostgreSQL results are distinguished from deployed-data evidence. **No deployed-data counts or real payment records were obtained.**

## Findings and recommendation

**VERIFIED CODE FACT:** F4 and F6 share optional receipt number/date/amount fields. There is no receipt identity ledger, receipt uniqueness constraint, physical inspection record, required receipt completeness, or expected-fee comparison. Future receipt dates are already rejected on changed writes and at preparation/issuance. Corrections overwrite the stored facts; the audit records field names, not old receipt values. Issued and cancelled requests are immutable through ordinary correction. See [the evidence map](current-state-audit.md#receipt-and-lifecycle-evidence).

**TEAM-REPORTED OPERATIONAL PRACTICE:** each certificate request needs its own distinct physical OR, including F4 and F6; the reported fee is **PHP 80.00 for either variant**. The process is:

`Student request → UCN Cashier payment/physical OR → presentation at GCO → authorized inspection/recording → preparation → Counselor issuance/printing → Registrar dry seal`.

Initial request creation stays available without receipt details. Cashier processing and Registrar status tracking are outside COMPASS scope here.

**PROPOSED DESIGN:** use **Option C: a permanent identity reservation plus immutable receipt claim revisions**. Two core tables distinguish the unique identifier from the requests that historically claimed it. A separate verification record attests to physical inspection of one exact claim revision. An ambiguous legacy identity has several observed claims, no chosen owner, and is blocked against new use. This is the smallest recommended design that handles both strict ordinary non-reuse and unknown legacy duplicates without inventing ownership. A unique current field alone releases the old number on correction.

Normalization proposal: printable ASCII, outer space trimming, ASCII case folding to uppercase, maximum 96 characters; preserve prefixes, punctuation, internal spaces, and leading zeroes. **Case equivalence and actual Cashier numbering scope require confirmation before activation.** Unsupported legacy characters require protected review and a cutover blocker where collision safety cannot be established.

Use an explicit `Verify receipt` action, with a proposed focused `good_moral.verify_receipt` capability and the existing active Counselor/Guidance Services Staff role boundary. Do not infer verification from saving fields or silently grant the new capability. Final issuance remains Counselor-only. See [authority and fee policy](verification-and-fee-policy.md).

Start with a **versioned, code-owned expected-fee policy**, not a Cashier administration subsystem. Store the applied policy identifier/expected amount with future verification decisions. PHP 80.00 has **no evidenced effective date**; historical applicability and any exception procedure must be settled before enforcement. No fee table is justified yet.

## Package

| File | Purpose |
| --- | --- |
| [Current state](current-state-audit.md) | Source evidence, lifecycle, authorization, rendering, notifications, UX/copy inventory |
| [Receipt identity](receipt-identity-design.md) | Options A/B/C, schema, constraints, normalization, correction, concurrency |
| [Legacy data and migration](legacy-data-and-migration.md) | Count-only read-only procedure, duplicate handling, expand/migrate/contract, rollback |
| [Verification and fee](verification-and-fee-policy.md) | Inspection meaning, authority, invalidation, gates, fee/date semantics |
| [Implementation plan](implementation-plan.md) | Separate GM-OR-1 through GM-OR-4 slices and acceptance gates |
| [Open decisions](open-decisions.md) | Evidence, recommendations, decision owners and release blockers |
| [Validation](validation.md) | Newly executed commands, results and limits |

## Readiness and boundaries

The audit provides a concrete implementation handoff. **GM-OR-1 can proceed as additive identity/history work after agreement on normalization and legacy quarantine; enforcement rollout is conditional on the listed institutional decisions and authorized data inventory.** GM-OR-2 must not activate fee/verification gates before authority, fee applicability, and pending-record transition policy are approved. Each slice gets its own PR.

Newly executed validation: **162 tests passed**, migration drift check found no changes, and the OpenAPI contract check passed. These are baseline proofs, not proofs that the proposed receipt system exists. See [validation.md](validation.md).

No deployment, SSH, live database connection, real-data inspection, live migration/reset, or automatic merge occurred. Only an empty disposable local PostgreSQL cluster was initialized for tests. The audit PR must remain unmerged until reviewed.
