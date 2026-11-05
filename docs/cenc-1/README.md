# CENC-1 — Finish Counseling Appointment

**Status:** backend slice implemented in the working tree, **not committed**. Base is
`integration/ux15-modernization` at `b33186371fd04c8e14772cd32a85457519ee30da`. Implementation
date 2026-11-05.
**Decision status:** D-CENC-01..22 remain **Open**. This slice implements the audited CENC-1 plan; it
does **not** decide any GCO-owned question, and no GCO, institutional, security, privacy, clinical or
UAT approval is claimed or implied.
**Availability:** the endpoint is always registered under normal session authentication, capability,
and resource-access rules. There is no feature flag, capability, toggle, or disabled-route shim.

## What this slice adds

One Counselor-confirmed action, `POST /api/v1/counseling/appointments/{appointment_id}/finish`,
composes two existing domain operations in a single database transaction:

- **Appointment** completion, through `complete_appointment` (unchanged).
- **Counseling Encounter** recording, through `create_encounter` (unchanged), or reconciliation with
  an identical existing Encounter.

It also links the deterministic Appointment Routine Interview through the existing link path and
reports only identifiers. Actual session times are supplied by the request and are never defaulted
from scheduled times.

## Files changed

| File | Change |
|---|---|
| `be/compass/counseling/finish_service.py` | **New** — `finish_counseling_appointment`, `FinishCounselingResult`, finish errors, Fix 1 recheck, Fix 2 gate, Routine linkability pre-validation |
| `be/compass/counseling/api.py` | **Modified** — strict request/response schemas, route `counselingFinishAppointment`, four `_raise` mappings |
| `be/tests/test_counseling_finish.py` | **New** — 22 service/API tests |
| `be/tests/test_counseling_finish_concurrency.py` | **New** — 10 real-thread concurrency tests |
| `be/tests/test_openapi_contract.py` | **Modified** — operation ID plus closed identifier-only contract assertions |
| `contracts/openapi.json` | **Regenerated** with `export_openapi` (never hand-edited) |
| `docs/cenc-1/README.md`, `implementation.md`, `validation.md` | **New** — this record |

No model, migration, setting, capability, policy provider, seed, audit action constant, notification
policy, frontend file, Orval config, or generated client was changed. `be/compass/appointments/**`
and `be/compass/routine_interviews/**` are untouched.

## Endpoint summary

| Property | Value |
|---|---|
| Route | `POST /api/v1/counseling/appointments/{appointment_id}/finish` |
| Operation ID | `counselingFinishAppointment` |
| Tag / auth | `counseling` / `session_auth` |
| Success | `200` for both first finish and replay |
| Errors | `401`, `403`, `404`, `409`, `422` |
| Request | `{actual_started_at, actual_ended_at, counseling_occurred}` strict, extra fields forbidden |
| Response | `{appointment_id, appointment_status, encounter_id, encounter_result, routine_interview_id, routine_interview_linked, already_finished}`; identifiers only |

`encounter_result` is `CREATED` or `EXISTING`. `already_finished=true` only when the Appointment was
already `COMPLETED` **and** an identical Encounter existed before the request.

## Mandatory hardening fixes

- **Fix 1 — Routine-creation lock-order race.** After locking the Appointment, the service rechecks
  `RoutineInterview.objects.filter(appointment_id=...).values_list("pk", flat=True).first()`. If a
  non-null PK differs from the initially locked Routine PK, it raises `CounselingFinishConflict`
  before `create_encounter`. See `be/compass/counseling/finish_service.py:191` and the deterministic
  interleaving test `be/tests/test_counseling_finish_concurrency.py:577`.
- **Fix 2 — service-level authorization.** Before any lock, the service rejects inactive,
  non-COUNSELOR, or capability-revoked callers with
  `CounselingNotPermitted("Active Counselor access is required.")`. See
  `be/compass/counseling/finish_service.py:96` and the revocation tests at
  `be/tests/test_counseling_finish.py:572`.

## Acceptance mapping (plan §9.4)

| Proposal acceptance theme | CENC-1 evidence |
|---|---|
| One action yields coherent Appointment + Encounter | `test_finish_records_completion_and_encounter_atomically`; one transaction; one completion event |
| No duplicate Encounter/Feedback on retry | `test_finish_replay_returns_existing_without_new_writes`; two-finish concurrency test |
| Contradictory facts never overwrite | `test_finish_contradictory_replay_is_a_conflict_and_never_edits_the_encounter` |
| Actual times, not scheduled times | `test_finish_never_substitutes_scheduled_times_and_rejects_invalid_actual_times` |
| Completion provenance preserved | `test_finish_documents_an_administratively_completed_appointment_without_new_completion` |
| E-Counseling safeguards | `test_finish_rejects_an_open_ecounseling_window_for_scheduled_and_completed` |
| Assigned Counselor only | `test_finish_authorization_matrix_returns_no_resource_details`; Fix 2 tests |
| Deterministic Routine linking | Routine match/mismatch/link-conflict tests; Fix 1 concurrency test |
| Legacy paths remain coherent | `test_legacy_paths_keep_partial_states_and_finish_reconciles_them`; legacy concurrency test |
| No new flag/migration | No model change; `makemigrations --check` empty; route always on |

## Reading order

1. [`implementation.md`](implementation.md) — design, lock order, error table, idempotency and
   legacy reconciliation, documented plan/code reconciliations.
2. [`validation.md`](validation.md) — exact commands, first-run failures and resolutions, final
   counts, contract diff, explicit not-run list.
3. `docs/cenc-0/` — the audit of record (unmodified), including
   `implementation-plan.md` §3–§11 and `risks.md` R-04.
