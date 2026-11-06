# CENC-2 implementation

## 1. Verified start state

```
git log -1 --format='%H %s'
22675506…  Add CENC-1 atomic counseling appointment finish
```

`git status --short` showed no uncommitted work in `be/`, `fe/`, or `contracts/openapi.json` before
editing (only the pre-existing untracked `outputs/paper-screenshots/`, untouched by this slice).

## 2. The projection

`be/compass/counseling/services.py:191` — `appointment_encounter_recorded(actor, appointment, at=None)`.

It answers one question: does this Appointment already have a recorded **Appointment-origin**
Encounter that matches the Appointment's own Student, Counselor, Service and delivery mode?

```python
CounselingEncounter.objects.filter(
    appointment_id=appointment.pk,
    student_id=appointment.student_id,
    counselor_id=appointment.provider_id,
    service_id=appointment.service_id,
    delivery_mode=appointment.delivery_mode,
    entry_mode=CounselingEntryMode.APPOINTMENT,
).exists()
```

- The identity filter is CENC-1 `_encounter_matches` (`finish_service.py:76`) **minus the actual
  times**. The field says a valid Encounter exists; finishing still compares times, so a
  time-differing Encounter is never silently treated as this Finish's outcome.
- `None` means *not exposed*, and the helper returns before issuing any query for such viewers:
  not the canonical Counseling Service, not an active `COUNSELOR`, not the Appointment's own
  provider, or no `counseling.view_assigned` at `at`.
- Single indexed query, derived read only. No model field, no migration, no persisted state.

`be/compass/appointments/api.py:276` declares `counseling_encounter_recorded: bool | None` on
`AppointmentDetailResponse`; `:927` adds the local import and `:937` returns
`appointment_encounter_recorded(actor=request.auth_user, appointment=item)`. It is independent of
`counseling_context_available`, which answers a different question (is the confidential Context
window open for this viewer) and is deliberately not reused.

### 2.1 Field semantics and privacy matrix

| Viewer | Canonical Counseling Appointment | Value | Effect in the UI |
|---|---|---|---|
| Assigned Counselor with `counseling.view_assigned` | yes | `true` / `false` | Documentation fact, and the Finish/Record/Complete decision |
| Assigned Counselor whose capability was revoked or who is inactive | yes | `None` | No fact, no Finish |
| Any other Counselor (not the provider) | yes | `None` at helper level; HTTP **404** before it | No detail page at all: Guidance College access is `RELATIONSHIP_ONLY` for Counseling (`be/compass/appointments/access.py`) |
| Head Guidance, GSS (even with `appointments.manage`) | yes | `None` at helper level; HTTP **404** | Same |
| Student | yes | `None` | Never rendered |
| IT Admin | yes | `None` | Never rendered |
| Assigned Counselor | no (other Service) | `None` | No fact, no Finish |
| Assigned Counselor, non-canonical Service | no | `None` | No fact, no Finish; legacy Complete unchanged |

The fact is rendered only where `counseling_encounter_recorded !== null` **and** the Appointment is
canonical Counseling, so `None` is indistinguishable from "no such row" for every other actor.
Finish additionally requires `counseling.manage_assigned` **and** `appointments.manage`, matching
the endpoint's own gate (`finish_service.py:96`).

## 3. Action matrix

`fe/src/features/counseling/finish-counseling-availability.ts:10` encodes:

| Appointment status | `counseling_encounter_recorded` | `actions.complete.allowed` | `canFinish` | State | Appointment Detail | Workspace (Appointment context) |
|---|---|---|---|---|---|---|
| `SCHEDULED` | `false` | `true` | `true` | `OFFERED` | **Finish counseling** replaces Complete; fact `Not recorded` | **Finish counseling** replaces Record |
| `SCHEDULED` | `false` | `false` (pre-start, or E-Counseling access `OPEN`) | any | `UNAVAILABLE` | legacy Complete stays hidden; existing explanations stay | `Record encounter` stays |
| `SCHEDULED` | `true` | any | `true` | `RECORDED` | legacy **Complete appointment** stays; fact `Recorded` | recorded-for-this-Appointment line + encounters link; no Record, no Finish |
| `COMPLETED` | `false` | `false` | `true` | `OFFERED` | **Finish counseling** + completed-without-documentation hint | **Finish counseling** replaces Record |
| `COMPLETED` | `true` | `false` | `true` | `RECORDED` | fact `Recorded`; no lifecycle re-open | recorded line; no authoring action |
| `CANCELLED` / `NO_SHOW` | any | any | any | `UNAVAILABLE` | unchanged | unchanged |
| any | `null` | any | any | `UNAVAILABLE` | no fact, no Finish | `Record encounter` fallback |
| any | any | any | `false` | `UNAVAILABLE` | unchanged | unchanged |

Two deliberate consequences:

- **`RECORDED` while still `SCHEDULED` keeps legacy Complete.** The Counselor is not forced to
  re-enter actual times that CENC-1 would then compare exactly, which would turn a bookkeeping step
  into a conflict.
- **The Workspace keeps `encounterState === "NOT_RECORDED"` as a precondition.** If the time-bounded
  Context already projects this Appointment's Encounter, the existing recorded block wins; Finish
  only replaces the *Record* action.

## 4. Shared modules

| Module | Responsibility |
|---|---|
| `finish-counseling-availability.ts` | `finishCounselingState`, `finishCounselingNotice`, `unconfirmedFinishMessage` |
| `finish-counseling-refresh.ts` | `invalidateAfterCounselingFinish(queryClient, {appointmentId, routineInterviewId})` |
| `finish-counseling-dialog.tsx` | `FinishCounselingDialog` — data-entry dialog (times + attestation), not a `ConsequentialActionDialog` |
| `counseling-shared.tsx` | four added `counselingErrors` entries |

The invalidation set covers exactly the projections a Finish changes: Guidance work queues, the
Appointment detail/history/reminders/list/bookable/reschedule reads, the Appointment Counseling
Context overview, My Encounters and Appointment candidates, both E-Counseling workspace reads, and —
only when the response carries `routine_interview_id` — the five Routine reads. No unrelated domain
is invalidated.

### 4.1 Dialog behavior

1. Title `Finish counseling`; description branches on `appointment.status`
   (`SCHEDULED` vs `COMPLETED`).
2. Read-only `<dl>`: Student (display name + Institutional ID or `Not provided`), Delivery,
   Scheduled (`formatAppointmentDateTime(starts_at, ends_at)`), Appointment reference.
3. Provenance line from `encounterProvenanceNote("APPOINTMENT")`.
4. `ActualTimeFields` with `idPrefix="finish-counseling"`; both values start as `""`. Scheduled times
   are displayed as reference and are never sent (D-CENC-07).
5. Submit validates with `actualTimeIssues` / `firstActualTimeIssue` at `Date.now()`, focuses
   `actualTimeInputId("finish-counseling", field)`, and converts with
   `institutionalDateTimeInputToISO`.
6. Attestation checkbox `#finish-counseling-occurred`. Unchecked at submit sets `attempted` and shows
   the `role="alert"` reason; no request is sent (D-CENC-01).
7. `useCounselingFinishAppointment({ mutation: { retry: false } })`;
   `mutateAsync({appointmentId, data: {actual_started_at, actual_ended_at, counseling_occurred: true}})`.
   `wasCompleted` is captured at submit time. `dismissible={!submitting && !uncertain}` keeps Escape
   and overlay clicks from hiding an in-flight or unconfirmed result.
8. Outcomes:
   - success → `onFinished(response.data, wasCompleted)`; times and checkbox reset.
   - non-`CompassApiError` or status ≥ 500 → `uncertain`: warning `Notice` with
     `unconfirmedFinishMessage` and only two actions — `Check again` (label `Checking…` while pending;
     a `false` answer adds "The result is still not confirmed. Wait a moment and check again.") and
     `Close`. **The request is never replayed** (ADR-091).
   - `409` → `onStale(counselingErrorMessage(caught, "The Appointment could not be finished."))`; the
     caller closes, refreshes and shows the notice.
   - other 4xx → inline `role="alert"` copy; the dialog stays open with the entered times.
9. `Finish counseling` / `Finishing…`, plus `Cancel` disabled while submitting. Cancel keeps the
   entered times; only a confirmed finish clears them.
10. `onCloseAutoFocus` lets the caller move focus to the action that replaced Finish.

### 4.2 Surface wiring

**Appointment Detail** (`appointment-detail-page.tsx`): `:646` derives `finishState`/`finishOffered`
from `getCounselingAccess(user).canManageAssigned && getAppointmentAccess(user).canManage`;
`:732` renders the documentation fact; `:700` renders the derived hint; `:749`/`:753` add
`finishOffered` to the Actions panel and button-row conditions so an undocumented `COMPLETED`
Appointment still shows Actions; `:759` swaps Complete for Finish; `:560`/`:572`/`:579` are
`handleFinished`, `handleFinishStale`, `checkFinishAgain`; `:1042` mounts the dialog. `ConfirmAction`,
the Complete handler and every other action's eligibility are unchanged.

**Counseling Workspace** (`counseling-workspace.tsx`): `:289` reads the Appointment through
`useAppointmentsGet`, enabled only for Appointment anchors with `counseling.view_assigned`; `:295`
takes the value **only when `isSuccess`**, never last-known data; `:303` requires
`encounterState === "NOT_RECORDED"`; `:419` renders the recorded-for-this-Appointment line with a
link to `/portal/counseling#encounters`; `:423` renders Finish with the status-matched note and
closes the Record dialog when opening; `:409` renders `finishNotice` above all action branches;
`:449` mounts the dialog whenever the Appointment read succeeded. `checkRecordAgain` (`:365`) now
also invalidates and refetches the Appointment read in Appointment contexts, and `handleCreated`
invalidates it, so a record committed outside this dialog stops offering authoring actions. Routine
Interview contexts, `RecordEncounterDialog` and the direct/E-Counseling flows are unchanged.

## 5. Copy inventory (provisional, D-CENC-18)

| Surface | Exact copy |
|---|---|
| Action (both surfaces) | `Finish counseling` |
| Pending | `Finishing…` |
| Dialog title | `Finish counseling` |
| Dialog description (`SCHEDULED`) | `This records the Counseling Encounter and marks the Appointment completed.` |
| Dialog description (`COMPLETED`) | `This records the Counseling Encounter for this completed Appointment.` |
| Provenance | `The Appointment sets the student, Service, and delivery mode. You are recorded as the counselor.` |
| Checkbox | `Counseling took place.` |
| Checkbox help | `Confirm that you met with this Student for Counseling.` |
| Checkbox error | `Confirm that Counseling took place before finishing.` |
| Detail fact | `Counseling encounter` / `Recorded` / `Not recorded` |
| Completed hint | `This Appointment is marked completed, but no Counseling Encounter is recorded for it. If the session took place, finish counseling to record it.` |
| Workspace recorded line | `A Counseling Encounter is recorded for this Appointment. Review it in My counseling encounters.` |
| Workspace finish note (`SCHEDULED`) | `Records the Encounter and completes this Appointment.` |
| Workspace finish note (`COMPLETED`) | `Records the Encounter for this completed Appointment.` |
| Uncertain | `We couldn’t confirm whether counseling was finished.` |
| Still unconfirmed | `The result is still not confirmed. Wait a moment and check again.` |
| Uncertain close | `The finish result is not confirmed. Check the Appointment details before trying again.` |
| Stale suffix | `The latest details are now shown.` |
| Success (created) | `Counseling finished and the Encounter recorded.` |
| Success (existing kept) | `Counseling finished. The Encounter already recorded for this Appointment was kept.` |
| Success (already finished) | `Counseling was already finished. The latest details are now shown.` |
| Success (late documentation) | `Counseling Encounter recorded for this completed Appointment.` |
| Success (check again) | `Counseling finished. The latest details are now shown.` |
| `counseling_appointment_closed` | `This Appointment was cancelled or marked no-show, so it cannot be finished.` |
| `counseling_finish_conflict` | `This Counseling session is already recorded with different details. Review it in My counseling encounters.` |
| `appointment_lifecycle_conflict` | `This Appointment changed before it could be finished. Review the latest details.` |
| `ecounseling_access_open` | `Wait until the online counseling access or rejoin period has ended before finishing this Appointment.` |

No clinical content appears in any of it, administrative status is never presented as proof that a
session happened, and an unconfirmed outcome never claims success.

## 6. Tests written

Backend:

| Test | Covers |
|---|---|
| `be/tests/test_counseling_context.py:1054` `test_detail_projects_whether_the_appointment_encounter_is_recorded` | all eight §4.4 cases: `False`, Student/unrelated/GSS/Head `None`, non-canonical `None`, `True` after `create_encounter`, `WALK_IN` ORM link → `False`, mismatched delivery → `False` |
| `be/tests/test_counseling_finish.py:797` `test_detail_projects_the_encounter_recorded_by_a_finish` | API Finish then Detail: `true`, `COMPLETED`, one Encounter, existing keys unchanged, `counseling_context_available` still boolean |
| `be/tests/test_openapi_contract.py:3486` `test_appointment_detail_encounter_record_projection_openapi_contract` | property present, required, `anyOf` boolean|null, sibling field still plain boolean |

Frontend (`fe/tests/counseling-finish.test.mjs`, 9 tests): the full state matrix, all four notice
outcomes plus the exact uncertain message, the four error codes through
`counselingErrorMessage(new CompassApiError(...))`, Detail rendering for OFFERED / RECORDED /
undocumented-COMPLETED / Student `null` / non-canonical Service, and Workspace rendering for Finish,
the recorded line, and the unconfirmed-read Record fallback.

## 7. Reconciliations between the plan and the code

1. **§4.4 case 4 through HTTP.** Appointment Detail applies `RELATIONSHIP_ONLY` access for canonical
   Counseling, so GSS, Head Guidance and unrelated Counselors receive **404**, not a body containing
   `null` (`be/compass/appointments/access.py`; Head Guidance is explicitly excluded from Counseling
   appointment management). The test therefore asserts `appointment_encounter_recorded(...) is None`
   at service level for anna, the unrelated Counselor, GSS and Head Guidance, `status_code == 404`
   for those three staff outsiders, and `None` **through** the API for the Student, who is allowed to
   read the Appointment. The privacy outcome is identical; the assertion mechanism differs because
   the plan's route is not reachable for those staff.
2. **Unavailable-actions wording vs the action swap.** When Finish replaces Complete,
   `actions.complete.allowed` is normally `false` (a `COMPLETED` Appointment), which would list
   "Complete" under Unavailable actions next to a Finish button. `appointment-detail-page.tsx:649`
   filters that single entry out of the disclosure **only while Finish is offered**; every other
   action's explanation, and the Complete confirmation path itself, is untouched.
3. **Result-flag reset without an effect.** The dialog must stay mounted so Cancel preserves the
   entered times, but a reopened dialog must not show a stale uncertain banner. An effect that
   cleared flags when `open` became false was rejected by
   `react-hooks/set-state-in-effect`; the flags are instead cleared in the dialog's own
   `changeOpen` wrapper (used by Escape, overlay, Cancel and the uncertain `Close`), and a confirmed
   `Check again` clears `uncertain` directly, because that path is closed by the caller.
4. **Uncertain Notice copy.** The plan's §6 lists only `unconfirmedFinishMessage`, so unlike the
   Record form the dialog appends no extra sentence; the "still not confirmed" line appears only
   after a `Check again` that came back negative.
5. **Dialog mount condition.** Appointment Detail mounts the dialog for any canonical Counseling
   Appointment (not only when `finishOffered`) so entered times survive Cancel; the state machine
   still decides who can open it. The Workspace mounts it whenever the Appointment read succeeded,
   mirroring the plan's "always mounted when `appointment` exists".
6. **Workspace Record invalidation.** The plan extends `checkRecordAgain`; this slice additionally
   invalidates the Appointment read in `handleCreated`, otherwise an Encounter recorded through the
   still-mounted `RecordEncounterDialog` would keep offering Record/Finish until a manual reload.
