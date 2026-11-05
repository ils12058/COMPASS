# CENC-1 — Implementation record

**Module:** `be/compass/counseling/finish_service.py` (new)
**Route:** `be/compass/counseling/api.py:645`
**Contract:** `contracts/openapi.json`, regenerated with `manage.py export_openapi`
**Base:** `integration/ux15-modernization` at `b3318637`, 2026-11-05

This record describes the implemented design. It does not decide any Open CENC question.

## 1. Service surface

```python
@dataclass(frozen=True, slots=True)
class FinishCounselingResult:
    appointment: Appointment
    encounter: CounselingEncounter
    encounter_result: Literal["CREATED", "EXISTING"]
    routine_interview: RoutineInterview | None
    already_finished: bool


def finish_counseling_appointment(
    *, appointment_id: UUID, counselor: User, counseling_occurred: bool,
    actual_started_at: datetime, actual_ended_at: datetime,
    context: AuditContext, now: datetime | None = None,
) -> FinishCounselingResult: ...
```

The service composes domain-owned operations; it never writes Appointment or Encounter fields
directly. Appointment completion stays in `compass.appointments.services.complete_appointment`;
Encounter creation, Feedback opportunity, notification and Routine linking stay in
`compass.counseling.services.create_encounter`. No new audit action, notification event, capability,
setting, model, field, constraint, index, or migration is introduced.

The API wraps the service with `_require_counselor(request, "counseling.manage_assigned")` followed
by `_require_counselor(request, "appointments.manage")` (`be/compass/counseling/api.py:650`), so
Students, GSS, IT Admin, non-provider Heads, and unauthenticated callers are rejected before the
service (`401`/`403`). Under the Appointment lock the service re-checks provider identity and
`appointment_management_access_allowed`, returning `404` for any non-provider or out-of-scope actor.

## 2. Transaction and lock order

One outermost `transaction.atomic()` (`finish_service.py:164`). Canonical order:

```
RoutineInterview → Appointment → Encounter (if present) → User(s) sorted by PK → Service
```

Step map:

| Step | Implementation |
|---|---|
| 0 | Reject `counseling_occurred is not True` with `InvalidCounselingInput`; normalize actual times with `_normalize_actual_times(..., now=now)`; run the Fix 2 capability gate. All before any row lock. |
| 1 | `lock_routine_for_encounter_recording(counselor=..., routine_interview_id=None, appointment_id=...)` — imported at module top so it is patchable at `compass.counseling.finish_service.lock_routine_for_encounter_recording`. |
| 2 | Lock the Appointment with `select_for_update(of=("self",))` and `select_related("service", "student", "provider__role")`; absent → `CounselingNotFound`. |
| 3 | Under lock: provider must be the caller, active, role `COUNSELOR`, and pass `appointment_management_access_allowed`; otherwise `CounselingNotFound` (never `403`/`409`). |
| 4 | **Fix 1 recheck** (below), before any write. |
| 5 | Only `SCHEDULED` and `COMPLETED` proceed; otherwise `CounselingAppointmentClosed`. |
| 6 | Canonical `COUNSELING` Service required, else `CounselingAppointmentInvalid`; normalize delivery mode. |
| 7 | Lock the existing Encounter for this Appointment, if any. |
| 8 | Existing Encounter must match every fact exactly (`student`, `counselor`, `service`, delivery mode, `entry_mode=APPOINTMENT`, appointment, normalized start/end); otherwise `CounselingFinishConflict`. Never update it. |
| 8a | **Routine linkability pre-validation** (below). |
| 9 | For `ONLINE` only: reject `ECounselingJoinState.OPEN` via the public `ecounseling_access_window(appointment, now=current)`; applies to `SCHEDULED` and `COMPLETED`. |
| 10 | `was_completed = status == COMPLETED`; call `complete_appointment(..., now=current)`; translate its errors. |
| 11 | If no Encounter existed, call `create_encounter(...)` with the request's normalized actual times; `CREATED`. On `CounselingAppointmentAlreadyUsed`, re-read under the still-held Appointment lock: identical → `EXISTING`, otherwise `CounselingFinishConflict`. |
| 12 | If a Routine is locked, re-read its `counseling_encounter_id` and require equality with the resulting Encounter; otherwise `CounselingFinishConflict` and roll back. |
| 13 | `already_finished = was_completed and encounter_existed`; return after commit. |

No exception is swallowed after a write: every failure propagates inside the atomic block, so
completion, Encounter, Feedback opportunity, notification, Routine link, and audit roll back
together.

## 3. Mandatory Fix 1 — Routine-creation lock-order race

`lock_routine_for_encounter_recording` performs an unlocked lookup before locking the Routine, while
`ensure_for_appointment` locks the Appointment first and then creates the Routine. Without a
recheck, a Routine committed between Finish's lookup and Finish's Appointment lock could later be
locked after the Appointment by `create_encounter`, inverting the canonical order.

After the Appointment row lock (`finish_service.py:191`):

```python
routine_id_now = (
    RoutineInterview.objects.filter(appointment_id=appointment.pk)
    .values_list("pk", flat=True)
    .first()
)
locked_routine_pk = locked_routine.pk if locked_routine is not None else None
if routine_id_now is not None and routine_id_now != locked_routine_pk:
    raise CounselingFinishConflict(
        "The Appointment's Routine Interview state changed; retry the finish request."
    )
```

The creator is blocked on the Appointment row held by this transaction, so a single plain recheck
closes the race; the Routine is not re-locked. A retry re-runs step 1, finds the committed Routine,
and locks it first. Deterministic coverage:
`be/tests/test_counseling_finish_concurrency.py:577` patches only the finish module's helper
reference, interleaves `ensure_for_appointment`, and asserts `409`, no Encounter, no completion
audit, then retries and verifies the link.

## 4. Mandatory Fix 2 — service-level authorization

`_require_finish_actor` (`finish_service.py:96`) runs in step 0, before the transaction:

```python
if (
    not counselor.is_active
    or counselor.role.code != "COUNSELOR"
    or not counselor.has_capability("counseling.manage_assigned")
    or not counselor.has_capability("appointments.manage")
):
    raise CounselingNotPermitted("Active Counselor access is required.")
```

This is additive to the API checks and the under-lock provider/access check. Direct callers cannot
bypass the two capabilities. `CounselingNotPermitted` keeps its existing `409
counseling_not_permitted` wire mapping; the API still returns `403 permission_denied` first.
Coverage: `be/tests/test_counseling_finish.py:572` revokes each capability with
`UserCapabilityOverride(effect="REVOKE")` and asserts zero writes;
`be/tests/test_counseling_finish.py:593` covers inactive and non-COUNSELOR callers.

## 5. Routine linkability pre-validation

`link_appointment_encounter` can return `False` silently on a context mismatch. Relying only on the
step-12 postcondition would surface a mismatch as the generic `counseling_finish_conflict`, while
plan §5.4 and §2(11) require fail-fast behavior and the existing
`counseling_routine_interview_mismatch` code. `_validate_routine_linkability`
(`finish_service.py:106`) therefore runs after the existing-Encounter check and before completion:

- A Routine already linked to a **different** Encounter → `CounselingRoutineInterviewAlreadyLinked`.
- An unlinked Routine that fails the domain's own encounter-context validation →
  `CounselingRoutineInterviewMismatch` (or `...AlreadyLinked` for a domain conflict).

The step-12 equality check remains as a postcondition and still raises `CounselingFinishConflict`
if the domain link silently fails for any other reason. No Routine is created or similarity-linked.

## 6. Error table

Service-level errors and their wire results:

| Service error | Wire status/code | Source |
|---|---|---|
| `CounselingNotFound` | `404 counseling_resource_not_found` | Existing `_raise` mapping |
| `CounselingNotPermitted` | `409 counseling_not_permitted` | Existing mapping (Fix 2, direct callers) |
| `InvalidCounselingInput` | `422 counseling_invalid_request` | Existing mapping (attestation, translated `InvalidAppointmentInput`) |
| `CounselingInvalidTime` | `422 counseling_invalid_time` | Existing mapping (normalization) |
| `CounselingAppointmentInvalid` | `409 counseling_appointment_invalid` | Existing mapping (non-canonical Service) |
| `CounselingAppointmentClosed` | `409 counseling_appointment_closed` | **New mapping** |
| `CounselingFinishConflict` | `409 counseling_finish_conflict` | **New mapping** |
| `CounselingFinishLifecycleConflict` | `409 appointment_lifecycle_conflict` | Reused wire code, translated from `AppointmentLifecycleConflict` |
| `CounselingFinishECounselingAccessOpen` | `409 ecounseling_access_open` | Reused wire code, translated from `AppointmentECounselingAccessOpen` and raised directly for the finish-level recheck |
| `CounselingRoutineInterviewMismatch` | `409 counseling_routine_interview_mismatch` | Existing mapping (pre-validation) |
| `CounselingRoutineInterviewAlreadyLinked` | `409 counseling_routine_interview_already_linked` | Existing mapping (pre-validation) |

Domain translations applied around `complete_appointment`: `AppointmentNotFound → CounselingNotFound`,
`InvalidAppointmentInput → InvalidCounselingInput`, `AppointmentLifecycleConflict →
CounselingFinishLifecycleConflict`, `AppointmentECounselingAccessOpen →
CounselingFinishECounselingAccessOpen`. `_raise` keeps its single `CounselingError` parameter; the
four new checks sit before the generic fallback (`be/compass/counseling/api.py:318`).

## 7. Idempotency, provenance and legacy reconciliation

Replay means the same provider, same Appointment, and identical Encounter facts after time
normalization. Contrary facts never edit the Encounter.

| Pre-state | Result | Writes |
|---|---|---|
| `SCHEDULED`, no Encounter | Complete + Encounter; `CREATED`, `already_finished=false` | One completion, one Encounter, one Feedback opportunity/invitation, Routine link if present |
| `SCHEDULED`, identical Encounter (legacy partial) | Complete + reconcile; `EXISTING`, `already_finished=false` | One completion only |
| `COMPLETED`, no Encounter (administrative first) | Create Encounter; `CREATED`, `already_finished=false` | Encounter + side effects; original `completed_at`/`completed_by` preserved; no second completion audit |
| `COMPLETED`, identical Encounter | `EXISTING`, `already_finished=true` | None |
| Any state, contradicting Encounter facts | `409 counseling_finish_conflict` | None; Encounter unchanged |
| `CANCELLED` / `NO_SHOW` | `409 counseling_appointment_closed` | None |
| Non-canonical Service | `409 counseling_appointment_invalid` | None |
| Existing Encounter with non-`APPOINTMENT` entry mode | `409 counseling_finish_conflict` | None |

One `appointment.completed` event is written only on a real transition; one
`counseling.encounter.created` only for a new Encounter; one `routine_interview.encounter_linked`
only when the link is newly established. Feedback uniqueness remains source-owned; no policy change.

The request has no `request_key`; idempotency is by deterministic facts, not a ledger. A repeated
request after commit returns the same `appointment_id` and `encounter_id`.

## 8. Documented plan/code reconciliations

1. **Mismatch wire code.** Plan §4 step 12 mandates the postcondition `CounselingFinishConflict`,
   while plan §5.4 and §2(11) require the mismatch to surface as
   `counseling_routine_interview_mismatch`. Because the domain link returns `False` silently, the
   pre-validation in §5 above is required to satisfy both; the postcondition is unchanged.
2. **Finalized-but-unlinked Routine.** Such a row cannot exist: the
   `routine_finalized_requires_encounter` check constraint requires
   `counseling_encounter IS NOT NULL` whenever `evaluation_finalized_at` is set
   (`be/compass/routine_interviews/models.py`). The test therefore covers a finalized Routine linked
   to a **different** Encounter and asserts `409 counseling_routine_interview_already_linked`.
3. **Post-finish `ensure_for_appointment`.** The prompt's concurrency case 10 expects a Routine
   created after a successful finish to link the existing Encounter. `ensure_for_appointment`
   requires `status == SCHEDULED` (`be/compass/routine_interviews/services.py`), so after a finish it
   raises `RoutineInterviewAppointmentInvalid`. The test asserts that rejection and no duplicate
   Encounter/completion, then separately proves the supported order: Routine created first for a new
   Appointment, then finish links it.

## 9. Files and non-changes

Created: `be/compass/counseling/finish_service.py`,
`be/tests/test_counseling_finish.py`, `be/tests/test_counseling_finish_concurrency.py`,
`docs/cenc-1/README.md`, `docs/cenc-1/implementation.md`, `docs/cenc-1/validation.md`.

Modified: `be/compass/counseling/api.py` (+69),
`be/tests/test_openapi_contract.py` (+49), `contracts/openapi.json` (+184, generated).

Unchanged on purpose: all models and migrations, settings, capability and policy definitions, seeds,
audit action constants, notification policy, `be/compass/appointments/**`,
`be/compass/routine_interviews/**`, frontend, Orval config, generated client, and `docs/cenc-0/`.
