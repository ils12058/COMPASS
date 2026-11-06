# CENC-4 — Reconciliation and Needs-documentation worklist

**Status:** implemented in the working tree, **not committed, not pushed**. Base is
`integration/ux15-modernization` at `494a7e2a` (`Add CENC-3 E-Counseling Finish counseling and record
parity`), verified before editing. Implementation date 2026-11-06.
**Decision status:** D-CENC-08, D-CENC-14 and D-CENC-21 are carried as **engineering-provisional**;
D-CENC-05, D-CENC-09, D-CENC-25 and D-CENC-03 keep the options earlier CENC slices already carried.
None is GCO-approved, and no GCO, institutional, security, privacy, clinical or UAT approval is
claimed or implied. CENC-5 UAT may revise the copy in [`implementation.md`](implementation.md).
**Availability:** the worklist and the corrected Detail facts ship enabled. There is no feature flag,
availability toggle, provisional-gating environment variable, or disabled-route shim.

## What this slice adds

A derived, read-only **Needs documentation** worklist on the Counseling landing, plus the one fact
Appointment Detail was missing: whether *any* Encounter is linked to the Appointment. Together they
make the documentation state truthful — a linked-but-non-matching Encounter is named as needing
review instead of being reported as "Not recorded", and the dead-end **Finish counseling** offer on
that state is gone. Reconciliation of the ordinary "recorded but still SCHEDULED" case uses the
existing authorized **Complete appointment** action; nothing here creates a second Encounter, a new
status, a review table, a persisted flag, or a new write.

| Surface | What a Counselor now sees |
|---|---|
| Counseling landing (`/portal/counseling`) | A `Needs documentation` panel above the encounters list: their own Appointments that may need a record or a reconciliation, one row per Appointment, with the reason, the session window, `Review appointment`, and `View encounter` only when that Encounter is theirs to read. Paginated by its own `review_page`, never cached. |
| Appointment Detail — fact | `Counseling encounter` reads `Recorded`, `Linked, needs review`, or `Not recorded` (previously only the first and last). |
| Appointment Detail — COMPLETED + linked but non-matching | The mismatch notice, **no** "no Counseling Encounter is recorded" sentence, and **no** `Finish counseling` button (that request 409s by construction). |
| Appointment Detail — SCHEDULED + recorded | An informational notice pointing at `Complete appointment`, whose confirmation now says the recorded Encounter will be kept. |
| API | `GET /api/v1/counseling/documentation-review` (read-only projection) and `counseling_encounter_linked` on `AppointmentDetailResponse`. |

Tracked diff for the slice: **654 insertions, 22 deletions** across nine modified files, plus four new
files (`be/tests/test_counseling_documentation_review.py`,
`fe/src/features/counseling/documentation-review.ts`,
`fe/src/features/counseling/documentation-review-panel.tsx`,
`fe/tests/counseling-documentation-review.test.mjs`). The contract change is 203/1 of that total and
is generated, not hand-edited.

## The gap this slice closes

`counseling_encounter_recorded` answers the identity rule (student, counselor, service, delivery mode,
`entry_mode=APPOINTMENT`; times excluded). Because `CounselingEncounter.appointment` is a one-to-one
link that predates that rule, a linked Encounter can fail it — Detail then said "Not recorded" and,
when the Appointment was COMPLETED, offered **Finish counseling**. Finish on that state cannot
succeed: `_encounter_matches` finds no exact match, and the create path refuses because the link is
already taken, so the request 409s. The E-Counseling workspace already called this state `MISMATCH`;
`docs/cenc-3/README.md:102-103` handed that surface to CENC-4.

Detail now carries the second fact (`counseling_encounter_linked`), so the three states are
distinguishable, and the UI suppresses an offer the server would refuse. **This is display truth, not
enforcement** — the write services, lock order, audits, Feedback and notifications are untouched, and
`POST /api/v1/counseling/appointments/{id}/finish` still revalidates everything it did before.

## Provisional decisions implemented

| ID | Decision | How it ships |
|---|---|---|
| D-CENC-08 | **C, provisional** — a derived read-only projection; no persisted state, no "No Counseling occurred" reason, no age/overdue threshold | `list_documentation_review` computes every row from current records; `be/tests/test_counseling_documentation_review.py::test_worklist_reads_and_never_writes` snapshots `CounselingEncounter`, `RoutineInterview`, `FeedbackOpportunity`, `Notification` and `AuditEvent` around a full read. GCO has not defined "overdue", so nothing here sorts or labels by age. |
| D-CENC-14 | **C, provisional** — the worklist lives on the Counseling landing and is scoped to `provider_id = actor` | No global Student listing, no GSS or administrative view; the endpoint is COUNSELOR-only with `counseling.view_assigned`. |
| D-CENC-21 | **stays C** — a linked Encounter that fails the rule is reported, not rewritten | `LINKED_CONFLICT` reason + the Detail mismatch notice + Finish suppression. No write-side rejection, no DB check, no data migration: a mismatched link still needs administrative review and cannot be corrected from these surfaces. |
| D-CENC-05 | **A stays** — reconciliation uses the existing authorized action | SCHEDULED + recorded is reconciled with **Complete appointment** (`appointments.manage`, server-rechecked), not a second Finish path and not a new label. Only the confirmation description changes, and only when an Encounter is already recorded. |
| D-CENC-09 | Unchanged | CANCELLED and NO_SHOW Appointments are excluded from the worklist; legacy correction of administratively completed records stays out of scope. |
| D-CENC-25 | Unchanged | "Recorded" still means identity-without-times. A time-only difference is `Recorded`, not a conflict, and never appears in the worklist. |
| D-CENC-03 | Unchanged | The endpoint is COUNSELOR-only. GSS still cannot see or complete canonical Counseling Appointments; `403` is asserted for `STUDENT`, `GUIDANCE_SERVICES_STAFF` and `IT_ADMIN`. |

Engineering-provisional sub-rules (all implemented and tested):

- **Scope**: `provider_id = actor`, `student__is_active=True`, `student__role__code="STUDENT"`, the
  canonical COUNSELING Service row resolved with `require_active=False` so historical Appointments
  survive service deactivation, and `status__in=(SCHEDULED, COMPLETED)`.
- **`LINKED_CONFLICT` requires `starts_at <= now`**, so a future Appointment whose link is
  administrative never produces noise.
- **`encounter_id` is exposed only when the linked Encounter's `counselor_id` is the actor**, because
  Encounter reads are assigned-only (`get_encounter_for_actor`). The conflict is still reported; the
  identifier of someone else's Encounter is not.
- **Inactive Students' historical Appointments are excluded**, consistent with
  `list_appointment_candidates`. The Appointment itself remains reachable directly — recorded as a
  limitation below.
- **Finish suppression is display-only.** The server still revalidates; nothing in
  `be/compass/counseling/finish_service.py` changed.

## Files changed

| File | Change |
|---|---|
| `be/compass/counseling/services.py` | **Modified** (191/16) — one `_encounter_identity_q` definition used by both readers; `_encounter_fact_exposed` extracted; `appointment_encounter_linked`; the reason enum, two page dataclasses, `_documentation_review_reason` and `list_documentation_review` |
| `be/compass/counseling/api.py` | **Modified** (73/0) — `CounselingDocumentationReviewReason`, item and page schemas, `GET /documentation-review` (`operationId counselingListDocumentationReview`) |
| `be/compass/appointments/api.py` | **Modified** (10/1) — `counseling_encounter_linked: bool \| None` on `AppointmentDetailResponse` and its serialization; the list schema is unchanged |
| `be/tests/test_counseling_documentation_review.py` | **New** (602 lines, 14 tests) — reason matrix, exclusions, online window, precedence, scope, reassigned link, deactivation, ordering/paging, read-only proof, role/authz matrix, recorded↔linked parity |
| `be/tests/test_openapi_contract.py` | **Modified** (80/0) — operation registry entry, path/schema pins, nullable-boolean Detail field, `AppointmentResponse` negative pin |
| `contracts/openapi.json` | **Regenerated** (203/1) |
| `fe/src/features/counseling/documentation-review.ts` | **New** (69 lines) — reason copy, the two notices, the reconciliation confirmation description, `reviewPageFromParam`, `reviewHref`, both hrefs |
| `fe/src/features/counseling/documentation-review-panel.tsx` | **New** (175 lines) — the panel: pending, error, empty, stale-refresh and row states |
| `fe/src/features/counseling/counselor-encounters.tsx` | **Modified** (7/0) — mounts the panel and preserves `review_page` across filter submits |
| `fe/src/features/counseling/finish-counseling-availability.ts` | **Modified** (4/1) — linked-but-not-recorded returns `UNAVAILABLE` |
| `fe/src/features/appointments/appointment-detail-page.tsx` | **Modified** (25/3) — third fact value, mismatch and reconciliation notices, Finish suppression, reconciliation-aware confirmation copy |
| `fe/tests/counseling-documentation-review.test.mjs` | **New** (242 lines, 7 tests) — copy/param purity and panel static renders |
| `fe/tests/counseling-finish.test.mjs` | **Modified** (61/0, append-only) — 4 cases for linked suppression and the two Detail notices |

No model, migration, setting, capability, policy provider, seed, audit action constant, notification
policy, Orval config or generated-client source was edited.
`be/compass/counseling/finish_service.py`, `be/compass/counseling/encounter_services.py`,
`be/compass/appointments/services.py`, `fe/src/features/ecounseling/**`,
`encounter-section-state.ts`, `counseling-workspace.tsx`, the call runtime, capture and consent flows,
`docs/cenc-0/`–`docs/cenc-3/` and `outputs/paper-screenshots/` are untouched.

## Known limitations

- **Inactive Students never appear in the worklist.** Their historical Appointments can still be
  missing a record; they are reachable directly on the Appointment surfaces.
- **A conflict whose Encounter belongs to another Counselor reports no `encounter_id`.** The row says
  review is needed; the review navigation is deliberately absent rather than a link the reader cannot
  open (`get_encounter_for_actor` would refuse it).
- **Time-only differences stay invisible.** Per D-CENC-25 an Encounter that matches identity but has
  different actual times is `Recorded`, not a conflict, and is not in the worklist.
- **Nothing here corrects a mismatched link.** D-CENC-21 remains open: enforcement, migration or a
  correction surface is a separate decision.
- The worklist has no age, overdue or "No Counseling occurred" dimension (D-CENC-08), and no metrics
  (D-CENC-15). Follow-Up creation and automatic linkage (7526/7538) are unchanged.

## Reading order

1. [`implementation.md`](implementation.md) — the three reasons and their precedence, the online
   boundary, endpoint and schema shape, the frontend surfaces, the verbatim copy inventory, and the
   plan/code reconciliations.
2. [`validation.md`](validation.md) — exact commands, results, first-run failures verbatim, contract
   and migration evidence, static checks, and the explicit not-run list.
