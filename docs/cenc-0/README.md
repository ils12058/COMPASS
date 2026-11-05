# CENC-0 — Counseling Encounter Lifecycle audit

**Status:** documentation-only, read-only audit. No implementation, schema, seed, generated artifact,
runtime or Git change was made.
**Audit base:** `integration/ux15-modernization` at
`04d2581baae3350eb25cc301ea36755775c1b98a`, 2026-11-05.
**Proposal reviewed:** *COMPASS — Counseling Encounter Lifecycle and Session Completion Integration*,
`/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md`,
lines 6649–7866. The proposal's reference baseline is `staging` at `0a843dae` on 2026-10-21
(proposal line 6657). It explicitly asks for re-audit before implementation (proposal lines 6726–6728,
6803–6805).
**Claim labels:** every substantive claim below is **Verified** (static evidence with `path:line`),
**Inferred** (reasoned from verified code), or **Unknown** (evidence or command still required).
Proposal text is never used as evidence of current behavior.
**Data handling:** no Student PII, secret, credential, production record or staging state is
reproduced. No database, migration, seed, test, dev-server, browser or deployment command was
executed against application data.

## Why this audit exists

COMPASS deliberately separates a scheduled **Appointment** (an administrative reservation and its
status) from a **Counseling Encounter** (a Counselor-confirmed record that an interaction actually
happened, with its own actual start/end). At HEAD those two records are written by two independent
services and two independent staff actions. Nothing composes them, and neither domain verifies that
the other is eventually consistent.

Proposal #9 proposes `Finish Counseling`: one Counselor-confirmed server-side operation that records
or reconciles the single Encounter and completes the Appointment atomically, with deterministic
Routine Interview linking, one Feedback opportunity, preserved provenance, and no duplicate side
effects. That direction is a workflow and privacy change, not merely a UI shortcut. CENC-0 establishes
what the code verifiably does today, which states are reachable today, who can do what, and which
GCO decisions must be answered before CENC-1 writes code.

The proposal's own CENC-0 slice requires a "Verified current-state map, action matrix, lock/notification
inventory, operational decisions" (proposal line 7621). This package supplies those. It does **not**
supply GCO approval, UAT execution, privacy sign-off or clinical validation.

## Package map

| File | Question answered |
|---|---|
| [`current-state.md`](current-state.md) | What exists today: models, statuses, services, locks, callers, APIs, frontend and counts |
| [`action-matrix.md`](action-matrix.md) | Which Appointment × Encounter states are reachable, which actions each permits, and which actors may perform them |
| [`cross-domain.md`](cross-domain.md) | What Appointments, Counseling, Routine Interviews, Feedback, Notifications, E-Counseling, Audit, FUP, FAC and CONT each own; where a Finish operation would cross a boundary |
| [`ux-journeys.md`](ux-journeys.md) | Current staff journeys, truthful copy, observed gaps, and proposed UAT journeys (labeled proposed) |
| [`decisions.md`](decisions.md) | D-CENC-01..22 with options, provisional recommendations, owners, blockers and Open status; D-CENC-01..20 map 1:1 to proposal §25 decisions D01–D20 |
| [`implementation-plan.md`](implementation-plan.md) | The smallest safe CENC-1 backend slice: exact files, endpoint, contract, lock order, idempotency, migration decision, compatibility, rollback and test plan |
| [`risks.md`](risks.md) | Risk register with likelihood, impact, mitigation and review trigger |
| [`validation.md`](validation.md) | Method, inspected scope, commands run and deliberately not run, evidence limits and definition-of-done result |

## Static counts at the audit base

| Object | Count | Evidence |
|---|---:|---|
| Appointment lifecycle statuses | 4 (`SCHEDULED`, `CANCELLED`, `COMPLETED`, `NO_SHOW`) | `be/compass/appointments/models.py:13-17` |
| Counseling entry modes | 4 (`APPOINTMENT`, `WALK_IN`, `CALLED_IN`, `REFERRED`) | `be/compass/counseling/models.py:14-18` |
| Delivery modes | 2 (`IN_PERSON`, `ONLINE`) | `be/compass/service_catalog/models.py` `DeliveryMode`; consumed at `counseling/models.py:47` and `appointments/models.py:58` |
| Core lifecycle models | 2 (`Appointment`, `CounselingEncounter`), plus `StudentSessionSummary`, Appointment change/reminder models | `appointments/models.py:39,166,239,277`; `counseling/models.py:21,93` |
| Appointment migrations | 2 | `be/compass/appointments/migrations/` |
| Counseling migrations | 5 | `be/compass/counseling/migrations/` |
| `counseling*` OpenAPI operations in module | 13 | `be/compass/counseling/api.py`, `operation_id="counseling…"` |
| `appointments*` OpenAPI operations in module | 19 | `be/compass/appointments/api.py`, `operation_id="appointments…"` |
| Counseling capabilities | 2 (`counseling.view_assigned`, `counseling.manage_assigned`) | `be/compass/accounts/policy.py:316` and role grants `:658-759` |
| Appointment capabilities | 3 (`appointments.view_self`, `appointments.manage_self`, `appointments.manage`) | `be/compass/accounts/policy.py:296-306` |
| Encounter feedback sources | 1 (`COUNSELING_ENCOUNTER`) used by Counseling | `be/compass/feedback/models.py:28-30`; `be/compass/counseling/services.py:378-381` |
| Appointment-completed notification event | 0 | `be/compass/notifications/policy.py:46-52` lists scheduling events only; no `appointment.completed` |
| Backend test functions in primary CENC files | 116 static | `test_counseling.py` 21, `test_counseling_context.py` 14, `test_counseling_downstream_lifecycle.py` 6, `test_counseling_frontend_readiness.py` 4, `test_appointments.py` 25, `test_appointment_action_projection.py` 6, `test_appointment_management_scope.py` 12, `test_routine_encounter_linking.py` 16, `test_cross_domain_lifecycle_reconciliation.py` 4, `test_final_api_lifecycle_completion.py` 8 |
| Frontend Counseling route pages | 7 | `fe/src/app/(portal)/portal/counseling/**/page.tsx`; E-Counseling adds `fe/src/app/(portal)/portal/e-counseling/[appointmentId]/page.tsx` |
| `Finish` / `already_finished` implementation | 0 | no matches under `be/compass`, `fe/src`, or `contracts/openapi.json` |
| `Needs documentation` / `requires_documentation` implementation | 0 | no matches under `be/compass`, `fe/src`, `contracts`, or `docs` |

All counts are static inspection, not test results. No test was run.

## Top 10 findings

| # | Finding | Claim | Evidence |
|---|---|---|---|
| 1 | **Appointment completion and Encounter recording are fully independent.** `complete_appointment` never imports, creates, links or checks `CounselingEncounter`; `create_encounter` never changes Appointment status. There is no composed service, endpoint, idempotency key or frontend chain. | **Verified** | `be/compass/appointments/services.py:1566-1618`; `be/compass/counseling/services.py:452-605`; caller inventory in `current-state.md`; no `finish` match in `contracts/openapi.json` |
| 2 | **A canonical Counseling Appointment is relationship-only.** The provider can manage it; another Counselor, the Head Guidance designation and GSS receive 404 or an empty list; IT Admin lacks the capability. The proposal's assumption that GSS may administratively complete Counseling Appointments is not true at HEAD. | **Verified** | `be/compass/appointments/access.py:24-27,47-72`; `be/tests/test_appointment_management_scope.py:365-440,444-476`; `be/compass/accounts/policy.py:698-723` (GSS has `appointments.manage` but no `counseling.*`) |
| 3 | **`SCHEDULED` + linked Encounter is reachable and is not treated as a conflict.** Encounter creation accepts a `SCHEDULED` Appointment, and the completion projection has no Encounter blocker, so a Counselor can still complete. Mark-no-show is blocked by the Encounter. | **Verified** | `counseling/services.py:294-298`; `appointments/services.py:1911-1915` (complete blockers omit encounter) vs `:1916-1922` (no-show includes it); `be/tests/test_appointment_action_projection.py:56-109` |
| 4 | **`COMPLETED` without an Encounter is an ordinary reachable state.** Completion is audit-only and does not infer attendance; the encounter candidate list explicitly includes `COMPLETED` Appointments so documentation can be added later. There is no reconciliation prompt or "Needs documentation" projection. | **Verified** | `appointments/services.py:1603-1617`; `counseling/services.py:664-672`; `appointments/services.py:1808-1923` |
| 5 | **An Encounter linked to an Appointment may carry a non-`APPOINTMENT` entry mode.** The DB constraint only enforces `APPOINTMENT → appointment_id`, not the converse; `create_encounter` and `update_encounter` both allow it. Counseling Context only counts `entry_mode=APPOINTMENT`, and Routine matching rejects anything else, so such a linked Encounter is audited as linked but not recognized as the Appointment's session. | **Verified** | `counseling/models.py:83-89`; `counseling/services.py:480-521,552-553`; `context_access.py:60-82`; `routine_interviews/matching.py:57-62`; `be/tests/test_counseling.py:794-827` |
| 6 | **Direct Encounter recording is Counselor-authenticated but not relationship-scoped.** Any active Counselor with `counseling.manage_assigned` may record an Encounter for any active Student found through an unscoped search, including students outside their College responsibility and graduated students. Encounter detail/list remain self-only. This is a privacy boundary the composed action must not widen. | **Verified** | `counseling/api.py:573-605`; `counseling/services.py:796-812`; `be/tests/test_counseling.py:1196-1265`; policy grants `accounts/policy.py:654-696` |
| 7 | **Feedback and invitation side effects are already atomic and idempotent per Encounter.** Encounter creation writes the Encounter, audit event, Feedback opportunity and `FEEDBACK_INVITATION` in one transaction; a synthetic notification failure rolls all of them back. Feedback identity is unique by `(source_type, source_id)`. | **Verified** | `counseling/services.py:322-382`; `feedback/models.py:59-64`; `feedback/services.py:217-285`; `be/tests/test_counseling.py:284-324` |
| 8 | **E-Counseling constraints are enforced by Appointment mutations, not by Encounter creation.** An open access window blocks complete/no-show; cancellation is blocked once the access period starts; a linked room blocks cancel/reassign. Encounter creation itself ignores E-Counseling state. A composed Finish operation must explicitly preserve the Appointment-side checks. | **Verified** | `appointments/services.py:1595-1602,1650-1656`; `ecounseling/services.py:127-163,201-239`; `appointments/services.py:1042-1124,1377-1393` |
| 9 | **The frontend has no Encounter state on Appointment Detail and no reconciliation journey.** It links to Counseling when context is available, shows generic Complete copy, and after context expiry the link disappears even if documentation is missing. The only fallback is the general Record Encounter form with an Appointment search that includes `COMPLETED` records. | **Verified** | `fe/src/features/appointments/appointment-detail-page.tsx:161-182,211-235,592-627,690-747`; `fe/src/features/counseling/counseling-workspace.tsx:328-352`; `fe/src/features/counseling/record-encounter-form.tsx:333-371` |
| 10 | **CENC-specific test coverage is absent.** No test exercises a composed Finish endpoint, needs-documentation projection, cross-domain concurrency for Finish, or the visibility consequence of a non-`APPOINTMENT` linked Encounter. Existing tests prove the components and some invariants, not the proposed contract. | **Verified** | No `finish`/`requires_documentation` matches under `be/tests`, `fe/tests`; `be/tests/test_appointments.py` has no Encounter-coupling assertion; `be/tests/test_appointment_action_projection.py:56-109` asserts the current permissive complete behavior |

## Proposal-vs-HEAD divergences

| # | Proposal claim | HEAD evidence | Disposition |
|---|---|---|---|
| 1 | Baseline is `staging` `0a843dae`, 2026-10-21 (line 6657) | Audit base is `integration/ux15-modernization` `04d2581b`, 2026-11-05 | **Verified divergence.** Re-verified every cited behavior at HEAD. No proposal claim is copied as evidence. |
| 2 | "A GCO staff member could have completed an Appointment administratively" and GSS may hold administrative completion for Counseling (lines 6702, 6795, 7702) | Counseling Appointments are `RELATIONSHIP_ONLY`; GSS/other Counselor/Head get 404 or empty lists. GSS has `appointments.manage` but cannot reach a Counseling Appointment. | **Verified divergence.** Policy decision D-CENC-03/D-CENC-04 must settle whether this changes. CENC-1 should not broaden access. |
| 3 | Student-directed summaries are "currently named `CounselingSharedSummary`" (line 6741) | HEAD model is `StudentSessionSummary` (encrypted content, separate publish lifecycle) | **Verified stale name.** Unrelated to CENC runtime; do not rename in CENC. |
| 4 | Counselor page offers "Record counseling encounter" (line 6783) | Page heading is "Counseling"; action is "Record"; panel title is "Record counseling encounter" | **Verified copy drift.** GCO copy approval remains open (D-CENC-18). |
| 5 | "Complete appointment" may be available to non-Counselor Appointment managers for Counseling (line 6754) | For canonical Counseling Appointments it is provider-only at HEAD | **Verified divergence.** See #2. |
| 6 | A `Needs documentation` indicator exists as a proposed derived projection (lines 6929–6940, 7229) | No backend projection, endpoint, query or frontend surface exists | **Verified absence.** CENC-1 plan excludes it; CENC-4 is the earliest slice. |
| 7 | Encounter creation implies Feedback invitation only; Appointment completion may notify (lines 6779, 7445–7447) | Encounter creation creates Feedback + invitation; Appointment completion creates audit only, no notification event | **Verified.** No `appointment.completed` notification event exists. |
| 8 | Encounter input may include `request_key` (line 7280) | No idempotency key exists for Encounter creation; only Appointment reminder batches use `request_key` | **Verified absence.** CENC-1 plan uses state-based replay and does not add a ledger. |
| 9 | A documented completed Appointment must preserve original `completed_by`/`completed_at` (lines 6888, 7342) | `complete_appointment` returns early when already `COMPLETED`, preserving provenance; the missing piece is only the Encounter | **Verified compatible.** CENC-1 can delegate to the existing early return. |
| 10 | Reassignment is refused once a Routine, Encounter or E-Counseling room exists (line 6797) | Verified guard exists and fails closed | **Verified compatible.** Finish must not bypass it. |

## Recommended smallest safe CENC-1 scope

One backend-only slice:

- a composed `finish_counseling_appointment(...)` application service in a new Counseling-owned
  integration module that calls the **existing** `create_encounter` and `complete_appointment`
  services inside one transaction, with a Routine-first lock order;
- one authenticated endpoint `POST /api/v1/counseling/appointments/{appointment_id}/finish`
  accepting actual start/end and a required confirmation flag, deriving all identity from the
  Appointment and the authenticated Counselor;
- state-based idempotent replay: an existing matching Encounter plus a `COMPLETED` Appointment returns
  the same result; contradictory actual times return a stable conflict and never overwrite; parallel
  requests serialize on the Appointment row;
- no new table, no new capability, no feature flag, no automatic Encounter from completion, no
  scheduled-time substitution, no bypass of E-Counseling or Feedback/Notification semantics;
- no frontend change; CENC-2 owns the one-action UX.

This is the smallest slice that removes the partial-success risk for the normal attended
Appointment, because it composes existing verified domain operations rather than duplicating their
rules. Details and exact files are in [`implementation-plan.md`](implementation-plan.md).

## What CENC-0 did not do

- No runtime, schema, migration, seed, fixture, backfill, settings, policy-provider, capability,
  feature-flag or deployment change.
- No application code, test, OpenAPI export, Orval regeneration or generated-client change.
- No database write, local `AuditEvent`, notification, Feedback or staging-seed execution.
- No full test suite, `pnpm build`, dev server or browser matrix.
- No commit, push, merge, rebase, stash, reset or branch change.
- No GCO approval, institutional sign-off, UAT result, privacy approval or clinical validation is
  claimed.