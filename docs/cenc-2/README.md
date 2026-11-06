# CENC-2 — Finish Counseling UX (Appointment Detail + Counseling Workspace)

**Status:** implemented in the working tree, **not committed, not pushed**. Base is
`integration/ux15-modernization` at `22675506` (`Add CENC-1 atomic counseling appointment finish`),
verified before editing. Implementation date 2026-11-06.
**Decision status:** D-CENC-01, D-CENC-05, D-CENC-06, D-CENC-07, D-CENC-08, D-CENC-10 and D-CENC-18
were decided **provisionally by engineering** because GCO decisions are not available. They are not
GCO-approved, and no GCO, institutional, security, privacy, clinical or UAT approval is claimed or
implied. CENC-5 UAT may revise the copy in `implementation.md`.
**Availability:** the projection and both surfaces ship enabled. There is no feature flag,
availability toggle, provisional-gating environment variable, or disabled-route shim.

## What this slice adds

One primary Counselor action — **Finish counseling** — that records the Counseling Encounter and
completes the Appointment through the existing CENC-1 endpoint
`counselingFinishAppointment`, with actual times entered by the Counselor and an affirmative
"Counseling took place." attestation.

CENC-1 behavior is unchanged. The only backend addition is one **read-only projection**,
`counseling_encounter_recorded`, on Appointment Detail, which lets both surfaces decide between
Finish, Record and the legacy Complete action without inventing a persisted documentation state.

| Surface | Behavior when eligible |
|---|---|
| Appointment Detail | `Finish counseling` replaces `Complete appointment`; Session details states the documentation fact; a completed Appointment with no Encounter shows a derived hint |
| Counseling Workspace (Appointment context) | `Finish counseling` replaces `Record encounter`; a recorded Encounter shows a review line instead of either authoring action |
| Everything else | Unchanged: legacy Complete, `Record encounter`, E-Counseling, direct recording, Routine workspaces |

## Provisional decisions implemented

| ID | Decision | How it ships |
|---|---|---|
| D-CENC-01 | **A** — required affirmative attestation | `#finish-counseling-occurred` must be checked; submit is refused with an on-screen reason |
| D-CENC-05 | **A** — one primary label | `Finish counseling` on both surfaces; `Complete appointment` survives only where Finish cannot be offered |
| D-CENC-06 | **A** — no extra backdate window | Client uses the shared `actualTimeIssues` contract (aware, end later than start, end not future); the server stays authoritative |
| D-CENC-07 | **A** — times never prefilled | Actual times initialize to `""`; scheduled times are shown as reference and never sent |
| D-CENC-08 | **B** — derived hint only | Documentation fact plus hint are projections; no persisted status, no worklist, no new model field |
| D-CENC-10 | **A** — preserve the E-Counseling block | Finish is not offered while `actions.complete.allowed` is false (including E-Counseling `OPEN`); the server rechecks |
| D-CENC-18 | **A** — provisional copy | The §6 copy is final for this slice and labeled provisional here and in `implementation.md` |

## Files changed

| File | Change |
|---|---|
| `be/compass/counseling/services.py` | **Modified** — new `appointment_encounter_recorded` read helper (33 lines) |
| `be/compass/appointments/api.py` | **Modified** — `counseling_encounter_recorded: bool \| None` on `AppointmentDetailResponse`, one local import, one return entry |
| `be/tests/test_counseling_context.py` | **Modified** — projection matrix test covering all eight §4.4 cases |
| `be/tests/test_counseling_finish.py` | **Modified** — Finish-then-Detail projection test |
| `be/tests/test_openapi_contract.py` | **Modified** — nullable required field contract test |
| `contracts/openapi.json` | **Regenerated** with `export_openapi` (never hand-edited): 13 insertions, 1 deletion |
| `fe/src/features/counseling/finish-counseling-availability.ts` | **New** (52 lines) — state matrix, notice copy, unconfirmed message |
| `fe/src/features/counseling/finish-counseling-refresh.ts` | **New** (72 lines) — post-finish invalidation set |
| `fe/src/features/counseling/finish-counseling-dialog.tsx` | **New** (234 lines) — shared data-entry dialog |
| `fe/src/features/counseling/counseling-shared.tsx` | **Modified** — four finish error codes (existing entries unchanged) |
| `fe/src/features/appointments/appointment-detail-page.tsx` | **Modified** — fact, hint, action swap, dialog wiring |
| `fe/src/features/counseling/counseling-workspace.tsx` | **Modified** — Appointment-context Finish action, recorded line, dialog wiring |
| `fe/tests/counseling-finish.test.mjs` | **New** (188 lines) — 9 tests: state matrix, copy, Detail render, Workspace render |
| `fe/tests/counseling-online-delivery.test.mjs` | **Modified** — appointment factory carries `counseling_encounter_recorded: null` |
| `docs/cenc-2/README.md`, `implementation.md`, `validation.md` | **New** — this record |

No model, migration, setting, capability, policy provider, seed, audit action constant,
notification policy, Orval config, or generated file was hand-edited. `be/compass/counseling/finish_service.py`,
`be/compass/appointments/services.py`, E-Counseling workspaces, direct recording, and Routine
Interview workspaces are untouched. `docs/cenc-0/` and `docs/cenc-1/` are unmodified.

## Out of scope (unchanged by this slice)

- CENC-1 finish semantics, lock order (`RoutineInterview → Appointment → Encounter → Users → Service`),
  audits, Feedback, notifications.
- E-Counseling workspace actions and copy (CENC-3).
- Direct Walk-in/Called-in/Referred recording copy and flows (CENC-3).
- Routine Interview workspaces and Routine linkage logic.
- Any Needs-documentation worklist, persisted documentation state, or reconciliation projection
  (CENC-4).
- Feature flags and availability toggles.

## Relationship to the other CENC slices

- **CENC-0** (`docs/cenc-0/`) is the audit of record; it stays unmodified.
- **CENC-1** (`docs/cenc-1/`) provides the atomic finish CENC-2 calls. CENC-2 changes no CENC-1
  behavior; it only reads the Appointment to decide which action to offer.
- **CENC-3** owns E-Counseling and direct-recording surfaces; CENC-2 deliberately leaves them alone,
  which is why the projection returns `None` rather than a guess for viewers outside the assigned
  Counselor relationship.
- **CENC-4** owns documentation reconciliation. CENC-2's hint is a derived on-screen statement only,
  so CENC-4 can build the worklist without changing what CENC-2 shipped.

## Reading order

1. [`implementation.md`](implementation.md) — field semantics and privacy matrix, action matrix,
   dialog behavior, copy inventory, and plan/code reconciliations.
2. [`validation.md`](validation.md) — exact commands, results, first-run failures, contract diff,
   migration check, and explicit not-run list.
