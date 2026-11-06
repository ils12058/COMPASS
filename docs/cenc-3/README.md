# CENC-3 — E-Counseling and direct interaction refinements

**Status:** implemented in the working tree, **not committed, not pushed**. Base is
`integration/ux15-modernization` at `70fdb31d` (`Add CENC-2 Finish counseling UX for Detail and
Workspace`), verified before editing. Implementation date 2026-11-06.
**Decision status:** D-CENC-23, D-CENC-24 and D-CENC-25 were decided **provisionally by engineering**
because GCO decisions are not available; D-CENC-07, D-CENC-10, D-CENC-18 and D-CENC-21 keep the
options CENC-0/CENC-2 already carried. None is GCO-approved, and no GCO, institutional, security,
privacy, clinical or UAT approval is claimed or implied. CENC-5 UAT may revise the copy in
`implementation.md`.
**Availability:** the aligned projection and the online Finish path ship enabled. There is no feature
flag, availability toggle, provisional-gating environment variable, or disabled-route shim.

## What this slice adds

Inside the Counselor's E-Counseling session workspace, **Finish counseling** replaces the two-step
`Record encounter` path, using the CENC-1 endpoint and the CENC-2 dialog unchanged. The documentation
fact now means the same thing on all three surfaces, because the E-Counseling workspace's
`counseling_encounter.recorded` answers through the same predicate as Appointment Detail's
`counseling_encounter_recorded`.

| Outcome | How it is met |
|---|---|
| An eligible online Counseling Appointment can be finished from its own session workspace | `EncounterSection` reads the Appointment (`useAppointmentsGet`, `retry: false`), and when that read is confirmed and `finishCounselingState` is `OFFERED`, offers `Finish counseling` through `FinishCounselingDialog` |
| Recording mid-session no longer bypasses the OPEN-window safeguard | The state machine's `WINDOW_OPEN` row is evaluated before both `FINISH` and `FALLBACK_RECORD`, so **no authoring action at all** is offered while `join_state === OPEN` |
| The fact means the same thing everywhere | One shared predicate, `appointment_encounter_matches`, backs both `counseling_encounter_recorded` (Detail) and `counseling_encounter.recorded` (E-Counseling workspace) |

No CENC-1 semantics, contract, model field, migration or persisted state changed. The contract diff
for this slice is **zero lines**: `recorded` was already declared `boolean`; it is now truthful.

## The safeguard hole this slice closes

CENC-1 refuses to finish while the online access period is open
(`be/compass/counseling/finish_service.py:241-252` → HTTP 409 `ecounseling_access_open`), but the
plain Encounter create path has no such check (`_validate_appointment_link`,
`be/compass/counseling/services.py:318-352` validates status, provider, student, service, delivery
mode and one-Encounter-per-Appointment only). Before this slice a Counselor could therefore document
a session **from inside the call** in a way the Finish path forbids, and the result was exactly the
partial state CENC exists to remove: the Encounter recorded, the Appointment still `SCHEDULED`,
Appointment Detail reading `Recorded`, and only legacy `Complete appointment` left to offer.

CENC-3 closes the UI half of that hole by precedence. What still allows recording, honestly:

- **The server still allows it.** `POST /api/v1/counseling/encounters` has no window check, and this
  slice adds none (no CENC-1 semantics, no new validation).
- **`Record encounter` is still reachable** as the fallback when the Appointment read is not
  confirmed, and is what a Counselor without `appointments.manage` sees (the Appointment read is
  never issued for them, so the read is not confirmed by design).

## Provisional decisions implemented

| ID | Decision | How it ships |
|---|---|---|
| D-CENC-23 | **A** — one action online | `Finish counseling` replaces `Record encounter` whenever the shared action matrix offers it; `Record encounter` survives **only** as the unconfirmed-Appointment-read fallback, never as a way to record during an OPEN window |
| D-CENC-24 | **A** — the OPEN window is copy, never a status | `join_state` only explains (`encounter-section-state.ts:95-102`); it changes no status and implies no attendance. A stale read that yields 409 shows the existing `ecounseling_access_open` copy |
| D-CENC-25 | **A** — one meaning for the documentation fact | `counseling_encounter.recorded` = "an Encounter matching this Appointment's Counseling record exists" (student, counselor, service, delivery mode, `entry_mode=APPOINTMENT`; **times deliberately not compared**). `id` keeps pointing at whatever Encounter is linked so review navigation still works |
| D-CENC-21 | **stays C** — no new enforcement | A linked non-`APPOINTMENT` Encounter is neither created by any UI path nor mistaken for a finished session; it is reported as its own `MISMATCH` state. No write-side rejection, DB check or migration added |
| D-CENC-07 | **stays A** — times never prefilled | The Finish dialog is reused unchanged; actual times initialize empty and join/leave/capture timestamps are never read into them |
| D-CENC-10 | **stays A** — preserve the E-Counseling block | Finish is offered only from a confirmed Appointment read whose `actions.complete.allowed` is true; the server rechecks |
| D-CENC-18 | **stays A** — provisional copy | The §5 copy inventory is final for this slice and labeled provisional here and in `implementation.md` |

## Files changed

| File | Change |
|---|---|
| `be/compass/counseling/services.py` | **Modified** — `appointment_encounter_matches` extracted as the shared predicate; `appointment_encounter_recorded` keeps its signature, exposure rule and behavior |
| `be/compass/ecounseling/services.py` | **Modified** — `recorded` now comes from the shared predicate; `id` still from `_encounter_for_appointment`, counselor-matching guard unchanged |
| `be/tests/test_ecounseling.py` | **Modified** — `recorded` matrix, Detail/E-Counseling parity, and linked-non-matching-never-finished tests |
| `be/tests/test_openapi_contract.py` | **Modified** — asserts `recorded` is still a plain required `boolean` (proof of no contract change) |
| `fe/src/features/ecounseling/encounter-section-state.ts` | **New** (127 lines) — pure state machine + copy for the section |
| `fe/src/features/ecounseling/ecounseling-workspace.tsx` | **Modified** — Appointment read, state-machine wiring, `FinishCounselingDialog`, check-don't-replay paths |
| `fe/src/features/ecounseling/session-help.tsx` | **Modified** — two help strings now point at Finish counseling |
| `fe/tests/ecounseling-finish.test.mjs` | **New** (361 lines) — 14 tests: all eight rows, the two precedence sweeps, capability conjunction, 409 copy, create-payload proof, and a static render of the real workspace |

No model, migration, setting, capability, policy provider, seed, audit action constant, notification
policy, Orval config, contract file or generated client was edited. `be/compass/counseling/finish_service.py`,
`be/compass/appointments/services.py`, the E-Counseling call runtime
(`fe/src/features/ecounseling/call/`, `runtime/`), capture and consent flows, Routine Interview
workspaces, direct Walk-in/Called-in/Referred recording and `docs/cenc-0/`, `docs/cenc-1/`,
`docs/cenc-2/` are untouched.

## Out of scope (unchanged by this slice)

- CENC-1 finish semantics, lock order (`RoutineInterview → Appointment → Encounter → Users → Service`),
  audits, Feedback, notifications, error codes.
- Any **server-side** window check on the Encounter create path, and any enforcement or migration for
  the Appointment-linked / non-`APPOINTMENT` combination (D-CENC-21 → CENC-4).
- The direct Student lookup scope of Walk-in/Called-in/Referred recording (D-CENC-22).
- Any Needs-documentation worklist, persisted documentation state, or reconciliation projection
  (CENC-4).
- Full backend and frontend suites — that gate is CENC-5.
- Feature flags and availability toggles.

## Relationship to the other CENC slices

- **CENC-0** (`docs/cenc-0/`) is the audit of record; it stays unmodified.
- **CENC-1** (`docs/cenc-1/`) provides the atomic finish CENC-3 calls. CENC-3 changes no CENC-1
  behavior.
- **CENC-2** (`docs/cenc-2/`) shipped the dialog, the state matrix and `counseling_encounter_recorded`
  on Detail and the Counseling Workspace. CENC-3 reuses all of it and removes the disagreement between
  those two projections and the E-Counseling one. CENC-2's records are not edited.
- **CENC-4** owns documentation reconciliation. The `MISMATCH` state is the surface-level report that
  CENC-4 must eventually resolve; CENC-3 deliberately does not guess at a fix.

## Known conflict with pre-existing browser tests (reported, not rewritten)

Thirteen pre-existing browser cases drive the `Record encounter` dialog inside an E-Counseling session —
that is the behavior D-CENC-23 removes, so they now fail. They were left untouched per the slice's stop
condition and are quoted verbatim in [`validation.md`](validation.md) §3.5:

- `fe/tests/ecounseling-call.browser.mjs` → `38/40 browser checks passed` (2 failures)
- `fe/tests/counseling-encounter-consistency.browser.mjs` → `2/14 browser checks passed` (11 of the 12
  failures are `/portal/e-counseling/...` cases)

Two further failures in those runs — `counseling-workspace-dialog-identity` and
`ui-information-hierarchy`'s `counseling-workspace` (`17/18 browser checks passed`) — are on the
`/portal/counseling/workspace/appointment/...` surface, which is **pre-existing breakage from the already
committed CENC-2**, whose validation never ran browser tests. `counseling-workspace.tsx` is not in this
slice's diff. Fixing either group is CENC-5's browser-gate work, not a silent rewrite here.

## Reading order

1. [`implementation.md`](implementation.md) — the projection-semantics change and its privacy
   reasoning, the eight-row state machine, the copy inventory, and plan/code reconciliations.
2. [`validation.md`](validation.md) — exact commands, results, first-run failures verbatim (including
   the browser conflicts), contract and migration evidence, and the explicit not-run list.
