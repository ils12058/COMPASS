# Final architectural recommendation

CONT-0 is ready for architecture review and a documentation-only integration PR. It does **not** establish institutional permission or production readiness for new professional sharing.

Preserve the current Context resolver, defaults and legitimate cross-College exact-provider behavior. Remove automatic cross-author Student-facing Summary disclosure first. Rename the active resource completely to Student Session Summary in a separate coordinated cutover. Add a small Counseling-owned grant with exact Student/receiver/purpose/finite interval/selected sources, then domain-owned read adapters and an optional independent encrypted Handoff. Keep approval authority separate from content readership, and keep original record authorship unchanged.

## Risk owners and disposition

| Finding | Owner function | Disposition / gate |
| --- | --- | --- |
| CONT-F01 cross-author publication audience | Counseling backend/frontend + security reviewer | High-priority CONT-1A removal and direct API negatives before any continuity work |
| CONT-F02 Context identity/time distinction | Counseling owner | Preserve; regression checks in every affected slice |
| CONT-F03 full Inventory and sensitive indicators | Inventory/Support + GCO/privacy | Existing path retained; exclude wholesale reuse in grants; approve fields before adapters |
| CONT-F04 crypto/persisted-contract rename | Counseling + data/secret operator | CONT-1B rehearse scoped B+C or retain-data A; new binding/settings, immutable migration lineage and Audit preserved |
| CONT-F05 absent grant/Acting approval policy | GCO/UCN/privacy + backend | Foundation and formal delegation needed; no guessed institutional authority |
| CONT-F06 incompatible assignment semantics | Appointment/Routine/Follow-Up owners | No automatic reassignment; grant read cannot satisfy manage checks; separate audited mutations |
| CONT-F07 authority races/cache/header behavior | Backend/frontend/security | Required per-read checks, coordinated identity locks, no-store and browser/concurrency proof before new access |
| CONT-F08 malformed persisted-link projection | Counseling/Routine owner | Narrow independent regression/projection hardening task; normal writers already validate, no remote exploit established |

Threats T01–T24 and residual persistence are in [threat-model.md](threat-model.md). Policy decisions D01–D18 are unapproved and tracked in [institutional-decisions.md](institutional-decisions.md). High risks have a concrete slice/disposition; no risk is accepted merely because staging is non-production.

## Readiness and limits

Current source behavior is well supported by services, routes, models, current ADR refinements and inspected authorization tests. Executed: **55 database-free synthetic tests passed**, immutable migration registry integrity, disk-loaded graph with **28 COMPASS leaves**, model/graph state agreement, deterministic OpenAPI check, documentation reference/inventory checks and `git diff --check` (final results in validation). No database-backed authorization, fresh database migration, cutover rehearsal, browser, CI or live-runtime proof is claimed by these local checks.

The proposed default grant source matrix is deliberately narrow: selected Encounter metadata and finalized Routine Evaluation; explicitly approved relevant Referral/Follow-Up projections only. Full Intake/Inventory need separate category/field review. Assessments, Student Summary cross-author content, drafts, E-Counseling media/transcripts, messages, credentials and bulk exports are excluded. Approval screens use structural source metadata, never raw professional content. An unplanned absence can proceed without an original-author Handoff, provided a valid independent approver and approved metadata selection procedure exist.

Primary staging strategy is **conditional scoped destructive Summary cutover + synthetic regeneration**, with separately authorized execution and preservation of unrelated state/Audit. It is not an approval to reset staging. Any retained/unknown-status record requires data-preserving conversion. A cryptographic binding rename is not ordinary key rotation; final active runtime has only new configuration/codec/endpoint contracts, while historical migrations and immutable evidence can retain former identifiers.

## Precise next implementation task

Open **CONT-1A — Student Session Summary confidentiality correction**, based on latest integration in an isolated worktree. Remove the Context Summary-history endpoint/section/query/render and its cross-author positive expectation. Preserve Student self reads, author Encounter GET/PUT/publish, publication integrity and all other Context sections; keep the current encryption/model/ordinary endpoint names until CONT-1B. Start with negative direct-API/decrypt-spy tests for provider B, Head provider, cross-College/direct anchors, revoked capability and other Student/drafts. Retain author tools on Encounter detail, reachable from the current interaction. Export/check OpenAPI and regenerate frontend clients, then run focused affected tests/typecheck/browser validation. One focused PR; no automatic merge, new grant, reset or deployment.

After 1A: 1B coordinated naming/cutover preparation → 2A grant/state/approval foundation with no professional content → 2B individually approved source adapters → 3 optional encrypted Handoff and planned/unplanned workflows → 4 synthetic security/concurrency/browser/UAT and institutional release sign-off.

CONT-0 changed documentation only. No runtime changes, database connections/migrations/resets, live key operations, confidential record inspection, SSH, outbound messages, deployment or merge were performed.
