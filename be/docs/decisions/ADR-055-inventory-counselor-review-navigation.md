# ADR-055 — Individual Inventory Counselor Review, Controlled Reopen, and Collection Navigation

**Status:** Accepted  
**Date:** 2026-09-20

## Context

The Individual Inventory is an annual, source-faithful Student record that already uses `submitted_at` as the compatibility boundary between editable draft and official submitted/locked state. Guidance Counselors need a deliberate professional review surface and a bounded correction workflow without turning the Inventory into a generic case-management or form-editing tool.

Several operational collections also needed small navigation corrections. The correction must preserve domain-owned authorization and avoid a generic filtering, search, or pagination abstraction.

## Decision

### Inventory lifecycle and submission history

`StudentInventory.submitted_at` remains the current official-lock indicator:

- null means editable draft;
- non-null means submitted and locked.

Two historical facts are added:

- `first_submitted_at`: first successful submission, never rewritten by reopen/resubmit;
- `last_submitted_at`: most recent successful submission or resubmission.

Existing submitted rows are backfilled from their existing `submitted_at`. Existing drafts are not assigned fabricated submission history.

An append-only `InventoryReopenEvent` records the Inventory, Counselor, reopen timestamp, and required bounded reason. No Inventory answers or other sensitive source fields are duplicated into that event.

### Counselor authority and scope

The canonical Counselor baseline receives:

- `inventory.view`
- `inventory.reopen`

Students retain `inventory.view_self` and `inventory.manage_self`. Guidance Services Staff, IT Admin, DPO, and Institutional Officer receive no raw Inventory capability by default.

Inventory authorization is owned by the Inventory domain:

- Head Guidance Counselor: institution-wide;
- regular Counselor: Students whose current `StudentAffiliation` belongs to an active College currently assigned to that Counselor through active `CounselorResponsibility`.

The routing/default helper `effective_responsibility_colleges(...)` is not used as the authorization decision.

Historical Inventory academic context does not create permanent Counselor access. Current Student affiliation determines present review scope.

### Counselor read and reopen behavior

Counselors may see roster/status metadata for in-scope Students, including MISSING, DRAFT, SUBMITTED, and correction-pending state where authoritative.

Full raw Inventory content is available only while the Inventory is currently submitted. Never-submitted drafts and reopened correction drafts are not Counselor-readable.

Only a current Academic Year submitted Inventory may be reopened. Reopen:

1. locks the Inventory row;
2. re-checks current scope, state, Academic Year, and Student lifecycle;
3. appends one reopen event;
4. sets `submitted_at = NULL`;
5. preserves Inventory UUID, Academic Year, Form Revision, answers, `first_submitted_at`, and `last_submitted_at`;
6. records safe structural audit metadata;
7. creates the centralized Inventory-reopened notification intent.

Counselors never edit Student answers.

Student resubmission preserves `first_submitted_at`, updates `last_submitted_at` and `submitted_at`, and records `inventory.resubmitted`.

### Inventory roster

The Counselor collection is `GET /api/v1/inventory/students`.

It uses:

- page/page_size with default 20 and maximum 50;
- `has_next`, not a global count;
- explicit Academic Year, status, College, Program, year-level, and Student-identity search filters;
- deterministic Student-name ordering;
- authorization scope before filters, search, ordering, and pagination.

Search is restricted to canonical Student institutional ID and name components. Sensitive Inventory answers are never searched.

For the current Academic Year, authoritative current in-scope Students with no Inventory may appear as MISSING.

For historical Academic Years, only existing Inventory rows for currently in-scope Students are listed. Historical MISSING is rejected because COMPASS does not store authoritative historical enrollment/affiliation rosters.

### Student Support and Student Profiling

Reopen makes `submitted_at` null, so the in-progress correction is naturally excluded from Student Support's submitted projection and Student Profiling's official submitted population. Resubmission restores it to those submitted-only surfaces. No report math is redesigned.

### Collection navigation corrections

The following focused corrections are included:

- Organization StudentAffiliation: bounded pagination, identity search, student/College/Campus filters.
- Routine Interview: Counselor queue for records directly assigned to the authenticated Counselor, with typed filters, identity-only search, deterministic pagination.
- Call Slip: narrow Student identity / Student snapshot / linked Referral reference search after existing authorization scope.
- Good Moral: narrow Student identity search and explicit student filter while preserving existing authorization.

Small reference/configuration lists and structurally bounded Student self-history remain unpaginated. Existing adequately paginated operational collections are not rewritten.

No generic repository, list service, filtering DSL, full-text index, or frontend work is introduced.

### Identity-policy deployment synchronization

The existing staging deployment already runs `sync_identity_policy` after migration using the candidate image. This ADR preserves that behavior and does not add a duplicate deployment edit.

## Consequences

This slice introduces one Inventory schema migration and new OpenAPI surface, but does not alter unrelated workflow states.

The governing list invariant is:

> authenticate → capability → resource scope → explicit filters → safe search → deterministic ordering → pagination → serialization

The governing Inventory authority is:

> capability + current organizational resource scope + Inventory state/Academic Year eligibility = authorized action
