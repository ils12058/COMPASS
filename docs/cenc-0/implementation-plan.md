# CENC-0 — Proposed Implementation Plan for CENC-1

**Status:** Proposed. Nothing in this document is implemented at HEAD. CENC-0 is documentation-only and
made no runtime, schema, generated-artifact, test, seed or Git change.

**Audit base:** `integration/ux15-modernization` @ `04d2581baae3350eb25cc301ea36755775c1b98a`
(2026-11-05). **Proposal reference:** Proposal #9, reviewed against `staging`
`0a843dae20c01984d0fb9aa46d5eef34102ab386` (October 21, 2026).

**Claim labels:** *Verified* = static evidence at a path:line; *Inferred* = reasoned from verified
code; *Unknown* = evidence or command still required. **Plan items are "Proposed" and are not claims
about current behavior.** Proposal text is referenced as proposal, never as verified behavior.

**Scope of this plan:** the smallest safe **backend** slice (CENC-1). Frontend composition and
generated-client consumption are deferred to a later slice (CENC-2). No CENC feature flag is proposed;
the finished endpoint is canonical and governed only by normal authentication, capability and
assignment checks, consistent with the project's provisional-enablement rule.

---

## 1. Why a composed service is required

At HEAD, completing an Appointment and recording a Counseling Encounter are independent operations:

- `POST /api/v1/appointments/{appointment_id}/complete` → `complete_appointment()`
  (`be/compass/appointments/api.py:1105–1121`, `be/compass/appointments/services.py:1566–1618`).
  It never creates or links an Encounter (Verified).
- `POST /api/v1/counseling/encounters` → `create_encounter()`
  (`be/compass/counseling/api.py:573–605`, `be/compass/counseling/services.py:452–605`).
  It never changes Appointment status (Verified).
- Neither endpoint accepts an idempotency key, and the frontend currently performs the two
  operations as a user-driven sequence (Verified; see `ux-journeys.md`).

A frontend chain therefore has a partial-failure window: Encounter recorded but Appointment still
`SCHEDULED`, or Appointment completed but no documentation, with a retry producing
`counseling_appointment_already_used` or a misleading second action. The proposal's §14.1
(lines 7261–7265) explicitly rejects that chain. CENC-1 closes exactly that gap with one server-side
transaction and leaves both legacy endpoints working.

---

## 2. The eleven required design constraints

| # | Requirement | Proposed CENC-1 response | Current-state evidence |
|---|---|---|---|
| 1 | One composed server-side transaction | A new `finish_appointment()` application service runs inside a single outermost `transaction.atomic()`. It calls the canonical domain services (`complete_appointment`, `create_encounter`) rather than writing Appointment/Encounter fields directly. Any mandatory failure rolls back every newly requested transition. | Existing services are independently atomic (Verified: `appointments/services.py:1576`, `counseling/services.py:481`, `:560`); nested `atomic()` uses savepoints, so the outer call composes them. |
| 2 | Idempotent replay and parallel requests | No request-key ledger. State-based idempotency: the Appointment row lock serializes requests, the one-to-one Encounter/Appointment constraint is the final safeguard, and an identical replay returns the already-recorded outcome. Contradictory actual times return a stable conflict and direct the Counselor to correction; nothing is overwritten. | One-to-one link Verified: `be/compass/counseling/models.py:39–45`; unique constraint path and duplicate detection Verified: `counseling/services.py:313–319`, `:376–381`; proposal §6.3 and §14.7 (lines 6896–6898, 7336–7338). |
| 3 | No automatic Encounter from administrative completion | `complete_appointment` is not modified, no signal/post-save hook is added, and no other completion path creates Encounters. Only the new Finish action records an Encounter, and only after explicit Counselor attestation plus actual times. | Completion is audit-only with no Encounter write (Verified: `appointments/services.py:1603–1617`); no signals or tasks create Encounters (Verified caller inventory in `current-state.md` §9). |
| 4 | No scheduled-time substitution | The request requires `actual_started_at` and `actual_ended_at`. The service never falls back to `Appointment.starts_at`/`ends_at`. Missing, naive, out-of-order, or future actual times are rejected. Scheduled times may be shown by a future UI as a labelled reference only. | Actual-time validation already exists (Verified: `counseling/services.py:172–188`); Encounter stores only actual times (Verified: `counseling/models.py:48–49`); the existing form labels scheduled times as reference only (Verified: `fe/src/features/counseling/record-encounter-form.tsx:47–61,81–85`). |
| 5 | Preserve `completed_by`/`completed_at` | For an already-`COMPLETED` Appointment, `complete_appointment` is still called and takes its idempotent early return, preserving the original actor/time; the missing Encounter is created separately. No second `APPOINTMENT_COMPLETED` audit event is written. | Early return Verified: `appointments/services.py:1586–1587`; provenance fields Verified: `appointments/models.py:84–91`; proposal §14.8 (lines 7340–7342). |
| 6 | No duplicate Feedback opportunity | Finish creates at most one Encounter per Appointment; `create_encounter` retains `ensure_feedback_opportunity`'s `get_or_create` plus source uniqueness. A replay creates neither an Encounter nor a Feedback row. | Unique source Verified: `be/compass/feedback/models.py:59–64`; `get_or_create` Verified: `be/compass/feedback/services.py:256–267`; rollback on side-effect failure Verified: `be/tests/test_counseling.py:284–324`. |
| 7 | No E-Counseling bypass | For a `SCHEDULED` Appointment, Finish delegates the transition to `complete_appointment`, which rejects completion while the E-Counseling access window is `OPEN`. For an already-`COMPLETED` Appointment, Finish performs a read-only `ecounseling_access_window` recheck before recording documentation and rejects if the window is `OPEN`; the recheck applies only to ONLINE canonical Counseling Appointments. | Completion guard Verified: `appointments/services.py:1595–1602`; ONLINE-only guard Verified: `appointments/services.py:1019–1021`; public window function Verified: `be/compass/ecounseling/services.py:201`; proposal §6.1(6), §14.4(4). |
| 8 | Assigned/authorized Counselor attestation only | Endpoint requires an active `COUNSELOR` with both `counseling.manage_assigned` and `appointments.manage`; the service additionally requires the actor to be the Appointment's `provider` and requires `appointment_management_access_allowed`. No GSS, IT Admin, non-provider Head, or Student path is added. No new capability. The request's `counseling_occurred` flag is an attestation, not an authorization substitute. | Counselor grants Verified: `be/compass/accounts/policy.py:654–696`; GSS cannot manage Counseling appointments Verified: `be/compass/appointments/access.py:47–72` and `be/tests/test_appointment_management_scope.py:365–440`; proposal §14.5 (lines 7315–7319). |
| 9 | Compatibility with legacy endpoints | Both existing endpoints remain registered and behaviorally unchanged. Finish delegates to the same services, so legacy-created Encounters/complete-only Appointments reconcile coherently: Finish completes a `SCHEDULED` Appointment that already has an identical Encounter, and documents a `COMPLETED` Appointment that lacks one. | Existing routes Verified: `counseling/api.py:573–605`, `appointments/api.py:1105–1121`; candidates already include `COMPLETED` (Verified: `counseling/services.py:640–690`). |
| 10 | No new availability feature flag | No flag, setting toggle, or capability is introduced. The endpoint is always registered; availability is decided by the existing capability and assignment checks. | Proposal line 7608; project rule that features ship default-on. No availability/counseling flag exists at HEAD (Verified in `current-state.md`). |
| 11 | Deterministic Routine linking only | Finish locks the Routine first via `lock_routine_for_encounter_recording`, pre-validates the deterministic match when a Routine exists, lets `create_encounter` establish the link in the same transaction, and then verifies the postcondition. It never creates a Routine, never uses Student/time similarity, and never silently accepts a failed link. | Lock helper Verified: `routine_interviews/services.py:1255–1288`; deterministic matcher Verified: `be/compass/routine_interviews/matching.py:39–68`; silent-false link Verified: `routine_interviews/services.py:1324–1357`. |

---

## 3. Exact files for CENC-1

| File | Change | Notes |
|---|---|---|
| `be/compass/counseling/finish_service.py` | **New** | `finish_counseling_appointment(...)`, its result dataclass, and finish-specific error classes. No model import side effects; imports the canonical services. |
| `be/compass/counseling/api.py` | **Modify** | Add `CounselingFinishRequest`/`CounselingFinishResponse` strict schemas, one `POST` route, imports, and `_raise` mappings for the new errors. |
| `be/tests/test_counseling_finish.py` | **New** | Service-level and API-level behavior, authorization, validation, provenance, routine outcomes, rollback, legacy compatibility. |
| `be/tests/test_counseling_finish_concurrency.py` | **New** | `TransactionTestCase` parallel-finish and cross-operation races. |
| `be/tests/test_openapi_contract.py` | **Modify** | Add `counselingFinishAppointment` to `EXPECTED_OPERATION_IDS` (`:57–894`) and assert the closed request/response schemas. |
| `contracts/openapi.json` | **Regenerate** | Required by the committed-contract test; produced by `export_openapi`, never hand-edited. |

**Deliberately not changed in CENC-1:** models, migrations, settings, capability definitions, policy
providers, seeds, staging workflows, notification policy, audit action constants, existing tests,
`be/compass/appointments/**`, `be/compass/routine_interviews/**`, generated frontend client, Orval
config, and any frontend file.

---

## 4. Endpoint and contract

### 4.1 Route

```
POST /api/v1/counseling/appointments/{appointment_id}/finish
operation_id = counselingFinishAppointment
tags = ["counseling"]
auth = session_auth
```

- Registered on the existing Counseling router (`be/compass/counseling/api.py:63`), mounted at
  `/counseling` (`be/compass/api/v1/router.py:264`), producing the proposal's illustrative path
  (§14.2, line 7271).
- Success status: `200` for both a first finish and a replay. The operation is a composition, not a
  pure collection creation, and a replay must not look like a new creation. `201` is rejected for
  that reason.
- Error statuses: `401`, `403`, `404`, `409`, `422` via the existing `response_with_errors` pattern
  (`counseling/api.py:575–582`).

### 4.2 Request (strict, `extra="forbid"`)

```json
{
  "actual_started_at": "2026-11-05T09:03:00+08:00",
  "actual_ended_at": "2026-11-05T09:51:00+08:00",
  "counseling_occurred": true
}
```

| Field | Rule |
|---|---|
| `actual_started_at` | Required, timezone-aware, actual session start. Never defaulted. |
| `actual_ended_at` | Required, timezone-aware, actual session end; must be after start and not in the future. |
| `counseling_occurred` | Required boolean; `false` is rejected with `422 counseling_invalid_request`. It records the Counselor's explicit attestation (§6.1(4)) and does not replace identity/authorization. |
| `request_key` | **Not in CENC-1.** The proposal calls it illustrative (§14.2 line 7284; §14.7 "If a `request_key` is used"). State-based idempotency is sufficient for a unique Appointment target and avoids a new table/migration. Revisit if security review requires keyed replay. |

The client never supplies `counselor_id`, `student_id`, `completed_by`, `completed_at`, service, or
delivery mode; those are resolved from the locked Appointment.

### 4.3 Response (strict)

```json
{
  "appointment_id": "<uuid>",
  "appointment_status": "COMPLETED",
  "encounter_id": "<uuid>",
  "encounter_result": "CREATED",
  "routine_interview_id": null,
  "routine_interview_linked": false,
  "already_finished": false
}
```

| Field | Meaning |
|---|---|
| `appointment_status` | Always `COMPLETED` on success. |
| `encounter_result` | `CREATED` when this request inserted the Encounter; `EXISTING` when an identical Encounter already existed. No `RECONCILED` value in CENC-1 (proposal §14.3 says the enum is optional). |
| `routine_interview_id` / `routine_interview_linked` | The deterministic Routine found for this Appointment and whether its link is established. `null`/`false` when no Routine exists. |
| `already_finished` | `true` only when the Appointment was already `COMPLETED` **and** an identical Encounter already existed before the request. `false` when documentation was added or the Appointment was newly completed. |

No confidential Evaluation, Session Summary, Feedback content, referral content, or message content
is returned. Identifiers are returned only for currently authorized destinations.

### 4.4 Error mapping

| Condition | Status | Stable code | Source |
|---|---|---|---|
| Not authenticated | 401 | existing session error | `session_auth` |
| Not an active `COUNSELOR`, or missing either capability | 403 | `permission_denied` | `_require_counselor` (`counseling/api.py:239–244`) |
| Appointment absent **or** actor is not its provider | 404 | `counseling_resource_not_found` | new check; avoids revealing existence (§6.5 line 6921) |
| Appointment `CANCELLED` or `NO_SHOW` | 409 | `counseling_appointment_closed` (new) | finish service |
| Existing Encounter contradicts request facts, or has non-`APPOINTMENT` entry mode | 409 | `counseling_finish_conflict` (new) | finish service |
| Encounter was created concurrently with different facts | 409 | `counseling_finish_conflict` (new) | translated from `CounselingAppointmentAlreadyUsed` |
| Appointment not canonical Counseling Service / delivery mismatch | 409 | `counseling_appointment_invalid` (existing) | `_validate_appointment_link` |
| Completion before scheduled start | 409 | `appointment_lifecycle_conflict` (existing code, reused) | `complete_appointment` |
| E-Counseling access window `OPEN` | 409 | `ecounseling_access_open` (existing code, reused) | `complete_appointment` / recheck |
| Routine mismatch | 409 | `counseling_routine_interview_mismatch` (existing) | pre-validation |
| Routine already linked/finalized incompatibly | 409 | `counseling_routine_interview_already_linked` / `counseling_finalized_routine_conflict` (existing) | pre-validation |
| Actual times missing/naive/reversed/future | 422 | `counseling_invalid_time` (existing) | `_normalize_actual_times` |
| `counseling_occurred` false or malformed body | 422 | `counseling_invalid_request` (existing) | request validation |

Existing code strings are preserved where an existing endpoint already returns them so that clients
do not see two vocabularies for the same domain rule. The two new codes are finish-specific because
no current endpoint expresses those outcomes.

---

## 5. Service design

### 5.1 Signature

```python
# be/compass/counseling/finish_service.py
@dataclass(frozen=True)
class FinishCounselingResult:
    appointment: Appointment
    encounter: CounselingEncounter
    encounter_result: Literal["CREATED", "EXISTING"]
    routine_interview: RoutineInterview | None
    already_finished: bool

def finish_counseling_appointment(
    *,
    appointment_id: UUID,
    counselor: User,
    counseling_occurred: bool,
    actual_started_at: datetime,
    actual_ended_at: datetime,
    context: AuditContext,
    now: datetime | None = None,
) -> FinishCounselingResult: ...
```

The function lives in Counseling because the composed fact is a Counseling session; it imports the
Appointment and Routine domain services rather than writing their fields. This avoids a
Counseling → Appointment model-write dependency and keeps the lock helpers in their owning modules
(proposal §14.1 warns against an unreviewed cross-domain write-through).

### 5.2 Transaction and lock order

One outermost `with transaction.atomic():`

1. **Request validation before locks:** `counseling_occurred` is true; `_normalize_actual_times`
   yields aware, ordered, non-future actual times. Invalid input fails before any row is touched.
2. **Lock the Routine first:** `lock_routine_for_encounter_recording(counselor=counselor,
   routine_interview_id=None, appointment_id=appointment_id)`. This preserves the documented
   Routine → Appointment order (`routine_interviews/services.py:1261–1265`).
3. **Lock the Appointment:** `Appointment.objects.select_for_update(of=("self",))
   .select_related("service", "student", "provider")` by `appointment_id`.
4. **Authorization and state recheck under lock:** Appointment exists; actor is active `COUNSELOR`;
   actor is `provider`; `appointment_management_access_allowed` passes; status is `SCHEDULED` or
   `COMPLETED`; service is the active canonical COUNSELING Service; delivery mode normalizes.
   Not-provider → 404; `CANCELLED`/`NO_SHOW` → 409.
5. **Load the existing Encounter under lock:** `CounselingEncounter.objects.select_for_update()
   .filter(appointment_id=appointment.pk).first()`.
6. **Branch on existing Encounter:**
   - **None:** proceed to create.
   - **Exists:** verify exact provenance and facts (student, counselor, service, delivery mode,
     entry mode `APPOINTMENT`, normalized actual start/end). Identical → replay; any difference →
     `CounselingFinishConflict`. Never update the Encounter here.
7. **E-Counseling recheck:** only when the Appointment is the canonical COUNSELING service with
   `delivery_mode=ONLINE` (mirroring `_uses_ecounseling_lifecycle`,
   `appointments/services.py:1019–1021`), call the public
   `ecounseling_access_window(appointment, now=current)` (`ecounseling/services.py:201`); if `OPEN`,
   raise a finish error mapped to the existing `ecounseling_access_open` code. The guard is skipped
   for IN_PERSON Appointments, whose access window is not part of their lifecycle. This check runs
   for both `SCHEDULED` and `COMPLETED`; for `SCHEDULED` it duplicates the guard inside
   `complete_appointment`, which remains authoritative.
8. **Complete the Appointment:** call `complete_appointment(appointment_id=..., actor=counselor,
   context=..., now=current)`.
   - `SCHEDULED` → transitions to `COMPLETED`, sets `completed_at`/`completed_by`, writes one
     `APPOINTMENT_COMPLETED` audit event.
   - `COMPLETED` → early return; provenance and audit unchanged.
   - Before-start and other lifecycle failures propagate and roll back the whole transaction.
9. **Create the Encounter only if missing:** call `create_encounter(counselor=counselor,
   entry_mode=APPOINTMENT, appointment_id=..., started_at=actual_started_at,
   ended_at=actual_ended_at, context=...)`. This re-locks the Routine and Appointment (already held
   by this transaction), locks users in sorted PK order, locks the Service, validates the link,
   inserts the Encounter, writes `COUNSELING_ENCOUNTER_CREATED`, creates the Feedback opportunity
   and invitation, and links the Appointment's Routine when the deterministic matcher permits.
   - Catch `CounselingAppointmentAlreadyUsed`: re-read the Encounter under the still-held
     Appointment lock. If its facts are identical → treat as `EXISTING`; otherwise raise
     `CounselingFinishConflict`. This is only reachable if a legacy path inserted between our
     existence check and insert, which the Appointment lock should already prevent; the
     one-to-one constraint is the final safeguard.
10. **Verify the Routine postcondition:** if the locked Routine exists, re-read it after
    `create_encounter`; if `routine.counseling_encounter_id != encounter.pk`, raise a conflict so
    the transaction rolls back rather than reporting a success with a silently unlinked Routine.
    This addresses the silent `False` return in `link_appointment_encounter`
    (`routine_interviews/services.py:1324–1357`).
11. **Return** the authoritative Appointment, Encounter and Routine facts after the transaction
    commits. The API serializes identifiers only.

Lock order summary (identical to the existing canonical order):

```
RoutineInterview → Appointment → Encounter (if present) → User(s) sorted by PK → Service
```

`complete_appointment` and `create_encounter` only re-acquire rows already held by the outer
transaction, so no new lock-order edge is introduced. The plan introduces **no** loop over
Appointments and no unbounded cross-domain loading inside locks (proposal §14.4 line 7313).

### 5.3 Actual-time normalization

- Reuse `_normalize_actual_times` (`counseling/services.py:172–188`): require aware datetimes,
  convert to the institutional timezone, require `start < end`, and reject an end in the future
  relative to the server's `now`.
- Equality for replay is compared after normalization (institutional timezone, same instant).
- The Appointment's scheduled `starts_at`/`ends_at` are never read into the Encounter and never
  defaulted. This is asserted by a dedicated test.

### 5.4 Routine behavior

| Situation after locking | Proposed outcome |
|---|---|
| No Routine for the Appointment | Create the Encounter; `routine_interview_id=null`, `routine_interview_linked=false`. Do not create a Routine. |
| Routine exists, open, deterministic match passes | `create_encounter` links it in the same transaction; response reports the ID and `true`; `ROUTINE_INTERVIEW_ENCOUNTER_LINKED` audit is written by the Routine domain. |
| Routine exists and already links **this** Encounter (replay) | Idempotent success; no duplicate link audit. |
| Routine exists but deterministic facts mismatch | 409 `counseling_routine_interview_mismatch`; no Encounter, no completion. |
| Routine exists, finalized or already linked to a different Encounter | 409 `counseling_finalized_routine_conflict` or `counseling_routine_interview_already_linked`; no writes. |
| Routine changes concurrently | Serialized by the Routine-first lock; the loser sees fresh state and gets a stable conflict or an idempotent outcome. |

Matching uses only the existing `RoutineEncounterFacts` fields (student, counselor, canonical
service, delivery mode, completed state, entry mode/appointment identity) — never Student/date
similarity (`routine_interviews/matching.py:39–68`). Pre-validation mirrors
`validate_encounter_for_routine_context` without replacing it; `create_encounter` remains the
authoritative writer.

### 5.5 Authorization

1. API: `_require_counselor(request, "counseling.manage_assigned")` and
   `_require_counselor(request, "appointments.manage")`. Both are already granted to `COUNSELOR`
   (`accounts/policy.py:654–696`); no new capability (D-CENC-16 recommendation A).
2. Service: active counselor, provider identity, and
   `appointment_management_access_allowed` against the locked Appointment.
3. Non-provider active Counselor → 404, not 409, to avoid revealing the protected Appointment.
4. GSS, IT Admin, Student, and non-provider Head cannot reach the service: role/capability checks
   stop them at the API (403) or provider check (404). This slice adds no override.

### 5.6 Audit, Feedback and notifications

- Exactly the existing domain events: `COUNSELING_ENCOUNTER_CREATED` (once, new Encounter only),
  `APPOINTMENT_COMPLETED` (once, `SCHEDULED → COMPLETED` only), and
  `ROUTINE_INTERVIEW_ENCOUNTER_LINKED` (only when a link is newly established).
- No new audit action is proposed for CENC-1. Correlation is available through
  `Encounter.appointment_id`, the audit metadata `appointment_id`/`reference_code`, and the
  transaction timestamps. If GCO requires a single "finished" event for reporting, add it in a
  later slice under D-CENC-20; do not double-write one here.
- Feedback: one opportunity per Encounter, enforced by source uniqueness; replay creates none.
  The existing optional informational `FEEDBACK_INVITATION` is created only with a new Encounter.
  CENC-1 does not change feedback policy or suppress invitations for late documentation (D-CENC-12).
- No completion notification exists today and none is added (`notifications/policy.py:46–52`).
- External email/push transport failure after commit follows existing durable post-commit semantics
  (`notifications/services.py:92–150`) and does not roll back confirmed history (proposal §6.2
  atomicity rule, line 6894).

### 5.7 Legacy reconciliation semantics

| Pre-existing state | Finish behavior |
|---|---|
| `SCHEDULED` + Encounter with `entry_mode=APPOINTMENT`, identical facts | Complete the Appointment; `encounter_result=EXISTING`; `already_finished=false`. |
| `SCHEDULED` + Encounter with different facts or non-`APPOINTMENT` mode | 409 `counseling_finish_conflict`; direct to correction. |
| `COMPLETED` + no Encounter | Create the Encounter; preserve `completed_at`/`completed_by`; no new completion audit; `already_finished=false`. |
| `COMPLETED` + identical Encounter | 200 `EXISTING`; `already_finished=true`; no writes. |
| `COMPLETED` + contradictory Encounter | 409 `counseling_finish_conflict`. |
| `CANCELLED`/`NO_SHOW` + no Encounter | 409 `counseling_appointment_closed`; nothing created. |
| `CANCELLED`/`NO_SHOW` + Encounter (reachable via cancel-before-start) | 409 `counseling_appointment_closed`; the existing Encounter is untouched. |

Legacy `POST /counseling/encounters` and `POST /appointments/{id}/complete` remain unchanged and
continue to permit their current partial states. CENC-1 does not attempt to retroactively forbid
them; it provides the coherent path and documents the partial states as legacy-compatible.

---

## 6. Idempotency and concurrency semantics

### 6.1 Replay definition

A replay is an authenticated request by the Appointment's provider with actual times equal
(same instant after normalization) to the single existing linked Encounter, whose other provenance
matches the Appointment.

- Appointment already `COMPLETED` + Encounter existed before the request → `EXISTING` +
  `already_finished=true`.
- Appointment `SCHEDULED` + Encounter existed before the request (legacy partial state) →
  completion is the only new fact → `EXISTING` + `already_finished=false`.
- Any differing fact → `409 counseling_finish_conflict`; the message directs to the authorized
  Encounter correction workflow. The service never edits the Encounter.

### 6.2 Parallel requests

- Two finishes: both take the Routine (if any) then Appointment row lock; one runs first and
  commits; the second observes `COMPLETED` + identical Encounter and returns `EXISTING`. Exactly
  one Encounter, one opportunity, one completion event.
- Finish vs. legacy Encounter creation: serialized on the Appointment row because
  `create_encounter` locks it (`counseling/services.py:487`). The later request either sees the
  Encounter or gets `counseling_appointment_already_used`; Finish translates that to `EXISTING`
  only when facts are identical, otherwise to `counseling_finish_conflict`.
- Finish vs. administrative complete: serialized on the Appointment row; if complete wins, Finish
  becomes late documentation and preserves provenance; if Finish wins, complete is an idempotent
  no-op.
- Finish vs. cancel/no-show: serialized; if the terminal non-completion wins, Finish returns 409
  and creates nothing; if Finish wins, cancel/no-show see `COMPLETED` and fail under their existing
  rules.
- Finish vs. reassignment: reassignment is already blocked when an Encounter exists
  (`appointments/services.py:1377–1393`); if reassignment wins first, the original Counselor gets
  404 and the new provider may finish.
- Finish vs. Routine finalization/link: Routine-first lock serializes; the outcome is a valid link
  or a stable conflict, never an orphan Encounter.
- Retry after commit before response: re-enters as a replay and returns the committed identifiers.

### 6.3 Why no request key

The only uniqueness domain is one Appointment → at most one Encounter, already enforced by a
database constraint. A key ledger would require a new model/migration (contrary to the default-no-
migration decision) and would not add safety beyond the row lock plus the one-to-one constraint. If
a future security review requires keyed replay across a broader composition, add it with a scoped
retention policy (proposal §14.7) in a separate slice.

---

## 7. Migration decision

**No migration.** CENC-1 adds no model, field, constraint, index, enum, setting, or data change.
`Appointment` and `CounselingEncounter` already carry every required field, and the unique
Appointment link already exists (`counseling/models.py:39–45`). The proposal itself lists "No
database migration is assumed" (§20, lines 7611–7613).

CENC-1 validation must confirm this with:

```
DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py makemigrations --check --dry-run
```

A non-empty diff means the plan drifted and must stop for review.

---

## 8. Rollback and failure atomicity

| Failure point | Result |
|---|---|
| Request validation | No transaction opened / no writes. |
| Authorization or not-found | No writes; 403/404. |
| Appointment `CANCELLED`/`NO_SHOW` | No writes; 409. |
| Before scheduled start (existing completion rule) | Whole transaction rolls back; no Encounter; 409. |
| E-Counseling window `OPEN` | Whole transaction rolls back; no Encounter; 409. |
| Encounter insert unique race | Savepoint rolls back the insert; Finish re-reads and returns replay or conflict; no partial completion remains. |
| Feedback opportunity or invitation persistence failure | Nested atomic in `_create_row` rolls back the Encounter; outer transaction rolls back the completion; no audit survives. Verified rollback pattern: `be/tests/test_counseling.py:284–324`. |
| Routine link mismatch/finalization conflict | Whole transaction rolls back; no completion, no Encounter. |
| Post-commit email/push transport failure | Confirmed Appointment/Encounter history and durable notification intent stand; transport retry is out of band (existing semantics). |
| Response lost after commit | Retry is a replay; no duplicate Encounter, Feedback, or audit. |

The outer atomic is the single rollback boundary for all newly requested mandatory transitions.
No `except` block may swallow an error after a write without re-raising or re-reading under lock.

---

## 9. Test plan

### 9.1 `be/tests/test_counseling_finish.py`

1. **Normal path:** `SCHEDULED` Appointment; finish with actual times → 200; Appointment `COMPLETED`
   with `completed_at=now`, `completed_by=actor`; Encounter `entry_mode=APPOINTMENT`, correct
   student/counselor/service/delivery, actual times, `created_by=actor`; exactly one Feedback
   opportunity; exactly one `FEEDBACK_INVITATION` notification; exactly one
   `COUNSELING_ENCOUNTER_CREATED` and one `APPOINTMENT_COMPLETED` audit; response `CREATED`,
   `already_finished=false`.
2. **No scheduled substitution:** request actual times differ from `starts_at`/`ends_at`; assert the
   Encounter stores the request times; omit either field → 422; naive, reversed, future → 422; no
   writes.
3. **Attestation:** `counseling_occurred=false` → 422; no writes.
4. **Replay:** repeat identical finish → 200 `EXISTING`, `already_finished=true`; Encounter count,
   Feedback count, notification count, and audit counts unchanged.
5. **Contradictory replay:** change one actual time → 409 `counseling_finish_conflict`; treated
   Encounter unchanged; no correction side effects.
6. **Administrative completion, missing Encounter:** complete via the legacy endpoint first; finish;
   Encounter created; original `completed_at`/`completed_by` preserved; no second
   `APPOINTMENT_COMPLETED`; `already_finished=false`.
7. **Administrative completion, existing identical Encounter:** legacy create then legacy complete
   then finish → `EXISTING`, `already_finished=true`, no writes.
8. **Existing Encounter with non-`APPOINTMENT` entry mode:** 409 `counseling_finish_conflict`;
   Appointment remains `SCHEDULED`; no completion.
9. **Terminal appointment states:** `CANCELLED` and `NO_SHOW` → 409
   `counseling_appointment_closed`; no Encounter; state unchanged.
10. **Before scheduled start:** `SCHEDULED`, now earlier than `starts_at` → 409
    `appointment_lifecycle_conflict`; no writes.
11. **E-Counseling open:** ONLINE Appointment with `OPEN` window → 409 `ecounseling_access_open`;
    Appointment unchanged; no Encounter; audit unchanged.
12. **Authorization matrix:** unauthenticated 401; Student/GSS/IT Admin 403; other active Counselor
    404; non-provider Head 404; provider Counselor succeeds. Assert no detail leaks in bodies.
13. **Service eligibility:** non-canonical Counseling service or delivery mismatch → 409
    `counseling_appointment_invalid`; no writes.
14. **Routine outcomes:** matching Routine links and reports the ID; mismatch → 409; finalized or
    already-linked-to-different-Encounter → 409; no Routine → `null/false`; no similarity-created
    link.
15. **Feedback persistence failure rollback:** patch the notification/opportunity path to raise;
    assert no Encounter, no completion, no audit. Reuse the established rollback test pattern
    (`be/tests/test_counseling.py:284–324`).
16. **Legacy compatibility:** legacy create and legacy complete still behave as before; finish
    reconciles each partial state as §5.7.

### 9.2 `be/tests/test_counseling_finish_concurrency.py`

`TransactionTestCase` with real threads/connections:

1. Two finishes at once → one `CREATED`, one `EXISTING`; one Encounter; one opportunity; one
   completion audit.
2. Finish vs. legacy `create_encounter` → one Encounter; finish returns `EXISTING` if identical;
   legacy returns `counseling_appointment_already_used` if it loses.
3. Finish vs. administrative complete → Appointment completed once; no duplicate audit; finish
   outcome is stable (`CREATED` + already-completed provenance preserved, or `EXISTING`).
4. Finish vs. cancel → either completed+Encounter or cancelled+no Encounter; never cancelled+new
   Encounter from Finish.
5. Finish vs. no-show → same invariant; no-show's existing Encounter conflict rule still applies.
6. Finish vs. Routine finalize/link → valid link or stable 409; no orphan.
7. Finish vs. reassignment → original actor 404 after reassignment; no Encounter written by the
   loser.
8. Retry after commit → replay returns the same IDs; counts unchanged.

### 9.3 Contract and static checks

- `be/tests/test_openapi_contract.py`: add `counselingFinishAppointment` to the expected operation
  ID set and assert the request/response schema field sets, `additionalProperties=false`, tag, and
  session security.
- Regenerate and check the committed contract:
  ```
  DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi \
    --output ../contracts/openapi.json
  DJANGO_SETTINGS_MODULE=tests.settings uv run python manage.py export_openapi \
    --check --output ../contracts/openapi.json
  ```
- `makemigrations --check --dry-run` must report no changes.
- Targeted test command for the slice:
  ```
  DJANGO_SETTINGS_MODULE=tests.settings uv run pytest \
    tests/test_counseling_finish.py tests/test_counseling_finish_concurrency.py \
    tests/test_openapi_contract.py
  ```
- The full backend regression suite is reserved for the last slice of the CENC family, not for
  CENC-1, per the project's slice-validation rule.

### 9.4 Acceptance mapping (proposal §22, lines 7632–7674)

| Proposal acceptance theme | CENC-1 evidence |
|---|---|
| One action yields coherent Appointment + Encounter | Normal-path test; one transaction; one completion event. |
| No duplicate Encounter/Feedback on retry | Replay test; counts unchanged. |
| Contradictory facts never overwrite | Conflict test; no Encounter update path. |
| Actual times, not scheduled times | Explicit no-substitution test. |
| Completion provenance preserved | Late-documentation test. |
| E-Counseling safeguards | Open-window rejection test. |
| Assigned Counselor only | Authorization matrix test. |
| Deterministic Routine linking | Match/mismatch/no-similarity tests. |
| Legacy paths remain coherent | Legacy compatibility tests. |
| No new flag/migration | No model change; `makemigrations --check`; route always on. |

---

## 10. Smallest-safe-scope justification

The slice is the smallest change that removes the partial-failure window:

- **One new application service**, one endpoint, one contract update, tests.
- **No new model, field, table, migration, capability, flag, setting, policy provider, audit action,
  notification event, or background job.**
- **No modification to either legacy mutation path**, so existing clients, seeds, and tests remain
  valid.
- **Domain-owned writes only:** completion stays in the Appointment domain; Encounter, Feedback and
  Routine linking stay in their existing paths; the new module composes, it does not duplicate.

A smaller frontend-only change is rejected because it cannot be atomic. A larger design (request-key
ledger, new capability, completion-triggered automatic documentation, new Needs-documentation
projection, reminder jobs) is not required to fix the composition gap and would add schema, policy,
or reporting decisions that belong to separate proposals or later CENC slices.

## 11. What CENC-1 must not do

- Do not create Encounters from `complete_appointment`, signals, admin actions, seeds, or scheduled
  jobs.
- Do not default actual times from scheduled times.
- Do not reassign `completed_by`/`completed_at` or write a second completion event.
- Do not add a capability, feature flag, setting, or availability toggle.
- Do not duplicate Feedback opportunities or notification events.
- Do not bypass E-Counseling completion constraints.
- Do not allow GSS, IT Admin, non-provider Head, Student, or any non-provider to finish.
- Do not link Routines by similarity, create Routines, or silently ignore a failed link.
- Do not change or remove the legacy endpoints.
- Do not introduce a Needs-documentation stored state; any such indicator remains a later derived
  projection (proposal §15, lines 7364–7379).
- Do not add Student Session Summary, Counseling Follow-Up, Evaluation, referral, or message
  authoring to this transaction (proposal §14.9, line 7346).

## 12. Open decisions that must be confirmed before implementation

| Decision | Relevance to this plan | Reference |
|---|---|---|
| Attestation wording/orientation | Whether `counseling_occurred` is the final field and copy | D-CENC-01 |
| Who may finish | Plan restricts to assigned Counselor; GCO must confirm GSS is excluded | D-CENC-02, D-CENC-03 |
| Retrospective documentation after administrative completion | Plan permits it per proposal §6.1/§14.8; GCO confirmation required | D-CENC-04 |
| Actor-facing action name | Endpoint/code names are internal; UI label belongs to CENC-2 | D-CENC-05 |
| Actual-time guidance and backdating limits | Plan reuses current non-future rule only | D-CENC-06, D-CENC-07 |
| Feedback invitation for late documentation | Plan keeps existing policy; suppression is a later decision | D-CENC-12 |
| Audit interpretation / composite event | Plan adds no new audit action | D-CENC-20 |
| Idempotency key | Plan omits it; revisit only if security review requires | Proposal §14.7 |
| User copy approval | Deferred to CENC-2 | D-CENC-18 |

Until these are confirmed, CENC-1 remains a proposal. No GCO approval, institutional sign-off, UAT
execution, deployment readiness, privacy approval, or clinical validation is claimed or implied.
