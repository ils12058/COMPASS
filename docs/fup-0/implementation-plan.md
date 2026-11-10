> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# Implementation plan — FUP-1 and FUP-2

**Status:** proposed. Not approved, not scheduled, not started.
**Audit base:** `integration/ux15-modernization` at `5224256a76c07f4503b5e3d98fea65c4ed84f2a9`.
**Scope:** this plan names future work. FUP-0 itself changed no `be/`, `fe/`, contract, generated,
migration, seed, fixture or dependency file, and ran no test or runtime command.

All slices below are gated by the decisions in [`decisions.md`](decisions.md). A slice may not start
until its gate is recorded as approved by the named owner. The provisional sequencing is:

| Slice | Purpose | Gate | Size |
|---|---|---|---|
| FUP-1A | Characterization tests for existing source-invalidity behavior | none (test-only) | S |
| FUP-1B | Truthful detail/context copy, no schema, no authorization change | D-FUP-01 (Option A) + D-FUP-07 | S |
| FUP-1C | Optional list/report source indicator | D-FUP-01 + D-FUP-07 | M — **not recommended for the smallest slice** |
| FUP-1D | Optional server-enforced review gate | D-FUP-01 Option B + D-FUP-07 | L — schema and contract change |
| FUP-2A | Further-action copy only | D-FUP-03 + D-FUP-07 | S |
| FUP-2B | Explicit "create next follow-up" using the existing endpoint | D-FUP-03 Option B + D-FUP-04 | M |
| FUP-2C | Linked predecessor lineage | D-FUP-03 Option C + D-FUP-04 | L — schema and contract change |
| FUP-3A | Faculty-originated Referral bridge | FAC-D1..D10 + FAC providers | Unknown until FAC |
| FUP-3B | Continuity coverage bridge | CONT runtime policy + CONT decisions | Unknown until CONT |
| FUP-3C | SAR academic-scope verification | none (already code-complete) | S — verification only |
| FUP-4 | Full regression and UAT execution | FUP-1/2/3 approved scope | L |

**Smallest safe first release: FUP-1A + FUP-1B.** It makes the existing state truthful and proves the
behavior without adding persistence, endpoints or authority.

## 1. Guardrails

These apply to every slice below:

1. **No schema before D-FUP-01/D-FUP-03.** Adding a review flag, predecessor column or resolution
   field before the decision is a stop condition (risk R-FUP-10).
2. **No automatic source-driven action.** Do not auto-cancel, auto-complete, auto-hide, auto-close or
   auto-relink a task when a Referral, Encounter or Routine changes.
3. **No cross-domain write.** Follow-Up code must not mutate a Referral, Encounter or Routine; those
   domains own their state and audit.
4. **No client-supplied authority.** Never accept `visibility`, `student_scope`, `source_name` or an
   assignee override from a query parameter; derive them server-side (risk R-FUP-03).
5. **No confidential recovery widening** without D-FUP-02 and CONT approval (risk R-FUP-02).
6. **No generated-file drift.** FUP-1 changes no OpenAPI operation or schema, so
   `contracts/openapi.json` and `fe/src/lib/api/generated/**` must remain untouched. Any future
   contract change requires an explicit OpenAPI export plus Orval regeneration in the same slice.
7. **No test claims without execution.** Each slice runs its own targeted tests; the full suite runs
   only in FUP-4, consistent with the repository's slice policy.
8. **No protected content in new copy, logs, notifications or test output.** Use synthetic fixtures
   already present in `be/tests/test_guidance_followups.py` and `fe/tests/guidance-followups.browser.mjs`.

## 2. FUP-1 — source truthfulness and regression proof

### 2.1 Objective

Make the already-authorized state legible: a pending task whose source became unavailable must be
explained truthfully on the task detail and on the source page, and the existing behavior must be
covered by tests. No new authority, persistence or endpoint.

### 2.2 FUP-1A — characterization tests (no production behavior change)

**File:** `be/tests/test_guidance_followups.py`.

Add tests that assert the behavior proven in [`source-lifecycle.md`](source-lifecycle.md). Proposed
names and assertions:

| Proposed test | Asserts |
|---|---|
| `test_referral_void_preserves_operational_task_across_workspaces` | After voiding the source Referral: the task remains in `guidanceFollowupsList`, in `guidanceFollowupsReport` counts, and in the current My Work/notification projection; detail returns `source: null`, `source_unavailable: true`; `update`, `reassign`, `record_activity`, `complete` and `cancel` still succeed; no Follow-Up event or audit is written by the Referral void. |
| `test_referral_void_makes_source_filter_and_context_unavailable` | The source-filtered list and `guidanceFollowupsGetContext` return not-found for the voided Referral; no Student name, source title or task existence is exposed by the error. |
| `test_confidential_source_loss_orphans_task_without_recovery` | After the source stops being readable for its Counselor: detail and mutations are not found; the task is absent from list/report/My Work; `guidanceFollowupsRecoverable` excludes it; Head Guidance recovery also excludes it; the row remains `PENDING` in the database fixture. |
| `test_head_operational_list_remains_assignment_scoped` | Head Guidance sees only assigned operational tasks in the ordinary list even though Head may recover any operational task; confidential rows never appear. |
| `test_completion_does_not_change_referral_state` | Completing a Referral-linked task leaves the Referral's status, administrative state and audit untouched; only the Follow-Up and its own event change. |
| `test_source_loss_does_not_create_material_notification` | A Referral void writes no Follow-Up material event and therefore does not refresh notification currentness; any existing in-app notice remains governed by the currentness rule. Characterization only — policy is D-FUP-06. |

Follow the existing fixtures and helpers in the file (`world`, `client`, `settings`); do not add a new
test database, seed file or factory. Keep tests transactional like the current suite.

**Frontend tests (only if FUP-1B adds copy):**

- `fe/tests/guidance-followups.test.mjs` — add a small presentation/access assertion if a shared copy
  helper is introduced. This file currently has 3 tests and is the right place for pure helpers.
- `fe/tests/guidance-followups.browser.mjs` — extend the synthetic `world()` fixture with a
  `sourceUnavailable` option; assert the approved detail copy appears, no broken source link is
  rendered, and the task remains actionable. The harness already supplies synthetic-only accounts and
  HTTP handlers (`fe/tests/guidance-followups.browser.mjs:1-41`).

**Exit criteria:** new tests pass against unchanged production code; if any test reveals behavior that
contradicts this audit, stop and record the divergence before changing code.

### 2.3 FUP-1B — approved detail and context copy

Gate: D-FUP-01 Option A and D-FUP-07 approved wording.

**File:** `fe/src/features/guidance-followups/followups-detail.tsx`

- The source panel is at `followups-detail.tsx:108`. Keep the existing three branches:
  source readable, `source_unavailable`, and never linked.
- In the `source_unavailable` branch, replace the current short sentence with approved copy that states:
  the related record is no longer available to the account; the task remains open and independently
  owned; staff should review whether the work is still needed; completing or cancelling the task
  records a reason but does not change the related record.
- Do **not** add a new mutation button, review checkbox or status change in FUP-1B. The existing
  actions remain the only actions.

**File:** `fe/src/features/guidance-followups/followups-context.tsx`

- Current behavior: `if (context.isError || context.isPending) return null` (`followups-context.tsx:21`).
  Keep the pending branch as `null`; change only the error branch to a compact panel message such as
  "Linked follow-ups are not available for this record." Do not render a count, task link, source
  title or "create" link.
- Rationale: the component renders only on an already-authorized source page, and the Follow-Up context
  call deliberately returns not-found for an ineligible/voided source. A generic message removes the
  silent disappearance without becoming a source-existence oracle. See risk R-FUP-13.

**File:** `fe/src/features/guidance-followups/followups-help.tsx`

- Add one section describing what happens when the related record becomes unavailable: the task keeps
  its own status; only the source link is removed; completion does not close the source record.

**File:** `fe/src/features/guidance-followups/followups-shared.tsx` (only if needed)

- If the same sentence is used on detail, list and report, add one exported copy constant here rather
  than duplicating strings. Do not add logic or new authorization helpers.

**No backend change in FUP-1B.** `source_unavailable` already exists in the detail contract
(`be/compass/guidance_followups/api.py:173-183,253-263`).

**Exit criteria:** approved copy is visible in the browser test; no new endpoint, field, migration or
generated artifact exists; keyboard and screen-reader checks pass in the existing browser harness.

### 2.4 FUP-1C — optional list/report source indicator

**Recommendation: defer or drop.** The list summary deliberately carries no source identity
(`be/compass/guidance_followups/api.py:134-157`), and the report is aggregate-only
(`workspace.py:150-187`). A per-row "source unavailable" boolean requires a backend projection change,
a new contract field, OpenAPI regeneration and Orval regeneration, plus a batch source-visibility check
that must not leak source identity or introduce N+1 queries.

If GCO explicitly requires it:

1. Add a nullable/boolean safe field to `FollowUpSummary` in `be/compass/guidance_followups/api.py`.
2. Compute it in `_summary`/`list_followups` from a batch, actor-scoped source check; never return the
   source UUID, title or kind in the summary.
3. Regenerate `contracts/openapi.json` and `fe/src/lib/api/generated/**` through the repository's
   normal export/Orval commands.
4. Update `fe/src/features/guidance-followups/followups-list.tsx` and `followups-report.tsx` with
   approved, non-alarming copy.
5. Add list/report tests in `be/tests/test_guidance_followups.py` and
   `fe/tests/guidance-followups.browser.mjs`.

This is a **separate approval**, not part of the smallest FUP-1.

### 2.5 FUP-1D — optional server-enforced review gate

Only if D-FUP-01 chooses Option B. This is **not** the recommended first slice.

Required artifacts, all gated on the approved policy:

- a deliberate persistence model (review state/outcome/actor/time, or an equivalent approved event
  convention) and a new migration under `be/compass/guidance_followups/migrations/`;
- a service gate in `be/compass/guidance_followups/services.py` that enforces review before completion
  or cancellation inside the same transaction;
- a contract change in `api.py` and the OpenAPI/Orval regeneration;
- frontend review UI in `followups-detail.tsx` and copy in `followups-help.tsx`;
- tests for review-required, review-recorded, concurrent completion and source loss before review.

Do not simulate review with an activity note: an activity note is not a decision record and is not
enforced.

### 2.6 FUP-1 verification

Commands for the future slice (not run in FUP-0):

| Purpose | Command |
|---|---|
| Backend targeted | `cd be && pytest tests/test_guidance_followups.py -q` |
| Frontend unit | `cd fe && pnpm test` |
| Follow-Up browser | `cd fe && node tests/guidance-followups.browser.mjs` and `cd fe && COMPASS_UI_BROWSER=webkit node tests/guidance-followups.browser.mjs` |
| Static contract check | confirm `git diff -- contracts/openapi.json fe/src/lib/api/generated` is empty for FUP-1B |

Exact runner conventions are recorded in `fe/package.json:14-16` and the test harness; FUP-1 should use
the existing scripts rather than introducing new ones. Full suite and WebKit/Chromium matrix are FUP-4.

### 2.7 FUP-1 acceptance criteria

- The six proposed backend tests pass on PostgreSQL where the existing suite requires it.
- Detail and context copy are approved by GCO and visible in the browser harness.
- No migration, no OpenAPI change, no generated-client change, no new endpoint, no authorization change.
- No auto-close/auto-hide/relink behavior.
- `validation.md`-style evidence is recorded by the slice owner, including exact commands and results.

### 2.8 FUP-1 rollback

Copy-only changes are reverted by reverting the frontend commit; tests are additive. No data rollback,
migration reversal or cache invalidation is required. If FUP-1C/FUP-1D are approved, their migration
and contract changes require a separate rollback plan before merge.

## 3. FUP-2 — further action after completion

### 3.1 Gate and meaning

FUP-2 may not start until D-FUP-03 defines what "further action" means and D-FUP-04 defines who may
initiate it. The three possible meanings produce materially different slices:

| D-FUP-03 outcome | Slice | Persistence |
|---|---|---|
| Guidance only — "consider whether another follow-up is needed" | FUP-2A | None |
| Explicit new task, created by the user through the existing create flow | FUP-2B | None |
| Explicit lineage between predecessor and successor | FUP-2C | New field/table + migration |

### 3.2 FUP-2A — copy only

**Files:** `fe/src/features/guidance-followups/followups-detail.tsx` (completion panel) and
`followups-help.tsx`.

Add approved copy on completed tasks: "Completing this follow-up ends this task. It does not close the
related record. If more work is needed, create a new follow-up." No action, no link, no backend change.
This is the smallest FUP-2 and is compatible with any D-FUP-03 outcome.

### 3.3 FUP-2B — explicit "create next follow-up" (provisional recommendation)

Use the **existing** create endpoint; no schema change.

**Files:**

- `fe/src/features/guidance-followups/followups-detail.tsx` — on `COMPLETED`, show a secondary action
  "Create next follow-up" when the actor has `guidance_followups.manage` and the create context is
  available. For a source-linked task, build the existing query-string contract
  (`source_kind`, `source_id`) only when the source is still readable; otherwise use the existing
  standalone parameters (`student_id`, `student_name`). Reuse
  `fe/src/features/guidance-followups/followups-create.tsx:27-41`, which already supports both forms
  and re-derives category/visibility from `guidanceFollowupsGetContext`.
- `fe/src/features/guidance-followups/followups-help.tsx` — explain that a new task is independent,
  gets its own owner and due date, and does not inherit a confidential classification unless the
  source is live and re-derived.
- `fe/src/features/guidance-followups/followups-create.tsx` — only if a prefill gap is found; prefer no
  change because `initialStudentId`/`initialStudentName` already exist.
- `be/compass/guidance_followups/api.py` / `services.py` — **no change**; `guidanceFollowupsCreate`
  already requires an explicit student, assignee, category and due date and derives visibility from
  the live source.
- Tests: `be/tests/test_guidance_followups.py` already covers delegated creation and classification;
  add a test only if the UI relies on a new query combination. Add a browser assertion in
  `fe/tests/guidance-followups.browser.mjs` that the action appears only for an authorized manager and
  a completed task.

**Critical constraints:**

- Never auto-create on completion; the user must open and submit the create form.
- Never copy `COUNSELOR_CONFIDENTIAL` from the predecessor. If the source is not live/readable, the new
  task must be standalone operational or not offered.
- Never prefill a different assignee or hide the assignee choice.
- Keep the existing Idempotency-Key and step-up behavior.

### 3.4 FUP-2C — predecessor lineage (only if required)

If D-FUP-03 requires provable lineage, add:

- `predecessor_followup_id` (nullable, immutable after creation, same-Student constraint) to
  `GuidanceFollowUp` in `be/compass/guidance_followups/models.py`, or a dedicated link model if
  multiple predecessors are required;
- migration `0003_...` with a backfill of `NULL` only;
- create-contract field in `api.py`, validation in `services.py`, and an audit/event reference;
- OpenAPI export and Orval regeneration;
- detail rendering that distinguishes "new task" from "continuation" and never claims the predecessor
  is resolved;
- tests for same-Student enforcement, cross-Counselor rejection, deletion/retention behavior and
  idempotent replay.

This is a **large** slice and should not be bundled with FUP-1. It does not by itself solve the
confidential orphan (D-FUP-02).

### 3.5 FUP-2 verification

Targeted backend tests for any changed service/API behavior; `cd fe && pnpm test`; the Follow-Up
browser test; and, if the contract changed, the repository's OpenAPI export plus
`pnpm api:generate` with a clean generated diff. Full regression stays in FUP-4.

## 4. FUP-3 slices

### 4.1 FUP-3A — Faculty-originated Referral bridge

**Blocked.** FAC institutional decisions FAC-D1..D10 are pending and the default providers return
`None` (`be/compass/referrals/faculty_policy.py:147-152`,
`be/compass/referrals/administrative_policy.py:109-122`; `docs/fac-5/readiness.md:8-12`). The existing
Faculty Referral submit/list APIs and administrative states do not need a Follow-Up field: Follow-Up is
an internal staff task and no current response schema exposes it
(`be/compass/referrals/faculty_api.py:54-61`). Do not add a Follow-Up bridge until FAC approves who may
initiate, what Faculty can see, and what the Referral state means. See
[`cross-proposal-readiness.md`](cross-proposal-readiness.md).

### 4.2 FUP-3B — Continuity coverage bridge

**Blocked.** The Continuity runtime policy returns `None`, so `require_policy` denies
(`be/compass/counseling/continuity_policy.py:99-109`). A source **read** grant must not be treated as a
Follow-Up **manage** grant. When CONT is approved, the adapter must check the grant's scope, time
bounds, receiving Counselor and revocation state, and must not expose protected descriptions to a
reader who is not the assignee. Do not implement before CONT approval; no current file should be
changed speculatively.

### 4.3 FUP-3C — SAR academic-scope verification

**Already code-complete at HEAD.** `StudentAffiliation` is deleted
(`be/compass/organization/migrations/0005_delete_studentaffiliation.py:13-15`) and live Follow-Up scope
uses `student_academics` (`policy.py:200-208`, `workspace.py:6-7,113-114`, `recovery.py:57-64`).
FUP-3C is verification only:

1. Re-run the static search for `StudentAffiliation` across `be/compass` and confirm only historical
   migrations contain it.
2. Confirm the current SAR scope tests still cover Follow-Up listing, assignee selection, recovery and
   the College transfer journey (UAT-FUP-20).
3. Correct the stale `docs/sar-0/README.md:37-38,55-58` and any proposal text in a separate
   documentation change after the owner approves; do not create an organization migration.
4. Record the result in FUP-4 evidence.

No application code or schema change is expected for FUP-3C.

## 5. FUP-4 — full regression and UAT

FUP-4 is the only slice that runs the full matrix:

- backend full `pytest` suite on the configured database, including PostgreSQL-only concurrency tests;
- frontend `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build`;
- full browser regression suite, including the Follow-Up browser test on the supported browsers;
- OpenAPI export/consistency check and Orval regeneration diff;
- approved UAT journeys from [`ux-journeys.md`](ux-journeys.md), executed with the real UI and synthetic
  accounts; record pass/fail and evidence per journey;
- decision sign-off evidence for D-FUP-01..07.

FUP-4 must not be claimed by FUP-1/FUP-2. FUP-0 executed none of these commands.

## 6. Dependency order

```text
D-FUP-01 + D-FUP-07
        |
        v
FUP-1A (tests) --> FUP-1B (copy) --> [FUP-1C optional] --> [FUP-1D optional]
                                         |
D-FUP-03 + D-FUP-04                      |
        |                                v
        +--> FUP-2A / FUP-2B / FUP-2C --> FUP-4
                                         ^
FAC decisions --> FUP-3A ----------------+
CONT decisions --> FUP-3B ---------------+
no gate --> FUP-3C verification ---------+
```

**Stop conditions:** any request to add a migration before D-FUP-01/03; to auto-close or auto-create
tasks; to add a source field to a list payload; to widen confidential recovery; to enable external
notifications; or to treat a read grant as manage authority.

## 7. Traceability

| Decision | Slice | UAT journeys | Primary files |
|---|---|---|---|
| D-FUP-01 | FUP-1A/1B/1D | UAT-FUP-10, 11, 13, 17 | `policy.py`, `services.py`, `api.py`, `followups-detail.tsx`, `followups-context.tsx` |
| D-FUP-02 | FUP-3B (and future coverage slice) | UAT-FUP-15 | `policy.py`, `recovery.py`, `continuity_policy.py` |
| D-FUP-03 | FUP-2A/2B/2C | UAT-FUP-16 | `followups-detail.tsx`, `followups-create.tsx`, optional model/migration |
| D-FUP-04 | FUP-2B/2C | UAT-FUP-16 | `followups-detail.tsx`, existing create authorization |
| D-FUP-05 | FUP-1B, FUP-2A | UAT-FUP-17, 08 | `followups-detail.tsx`, `followups-help.tsx` |
| D-FUP-06 | FUP-1A, future notification slice | UAT-FUP-12, 19 | `integration.py`, `notifications/policy.py` |
| D-FUP-07 | every slice | all 20 journeys | approval record, not code |

## 8. Explicitly out of scope for FUP-1/FUP-2

- New roles or capabilities; any change to `accounts/policy.py` grants.
- Head Guidance global list access or confidential access.
- Automatic Referral/Encounter/Routine state changes.
- Source relinking, replacement Referral lookup or merge.
- Bulk reassignment, bulk completion or background reconciliation jobs.
- Email/push delivery changes.
- Data migration of existing tasks.
- Any FUP-3A/3B implementation; FUP-3C is verification only.
- Any production/staging deployment, data repair or PII analysis.

## 9. Approval record

| Item | Owner role | Status |
|---|---|---|
| D-FUP-01 option | GCO | Pending |
| D-FUP-02 option | GCO + privacy | Pending |
| D-FUP-03 option | GCO | Pending |
| D-FUP-04 option | GCO | Pending |
| D-FUP-05 wording | GCO | Pending |
| D-FUP-06 behavior | GCO | Pending |
| D-FUP-07 journey/copy sign-off | GCO | Pending |
| FUP-1 scope approval | GCO + engineering | Pending |
| FUP-2 scope approval | GCO + engineering | Pending |
