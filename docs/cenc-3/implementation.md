# CENC-3 implementation

Slice 3 of the CENC initiative: the E-Counseling session workspace offers **Finish counseling**, the
OPEN-window safeguard is no longer bypassable from inside the session, and the documentation fact means
one thing across Appointment Detail, the Counseling Workspace and the E-Counseling workspace.
Everything shipped here is a **provisional engineering decision, not GCO policy**.

## 1. Verified start state

- Branch `integration/ux15-modernization`, HEAD `70fdb31d Add CENC-2 Finish counseling UX for Detail and
  Workspace`; `git status` showed only the pre-existing untracked `outputs/paper-screenshots/`.
- CENC-1 finish endpoint `POST /api/v1/counseling/appointments/{id}/finish` and its 409 codes exist and
  are unchanged (`be/compass/counseling/finish_service.py`, `be/compass/counseling/api.py:324-325`).
- CENC-2 shipped `FinishCounselingDialog`, `finishCounselingState` / `finishCounselingNotice` /
  `unconfirmedFinishMessage`, `invalidateAfterCounselingFinish`, and the nullable
  `counseling_encounter_recorded` projection on Appointment Detail.
- `be/compass/ecounseling/services.py` emitted `{"id": encounter.pk, "recorded": True}` whenever *any*
  Encounter was linked to the Appointment and belonged to this Counselor — `recorded` was a constant.
- `EncounterSection` (`ecounseling-workspace.tsx`, pre-change `:344-434`) offered only `View encounter`,
  `Check again` and `Record encounter`, with its own ad-hoc `reloadEncounter()`.
- Re-checked before relying on it: the prompt's line numbers were accurate for the pre-change tree. They
  shift in the current file — by +8 above the rewritten section (the imports this slice adds, so
  `ECounselingWorkspace` `:222` → `:230` and `EncounterSection` `:344` → `:352`) and by +98 below it
  (`CounselorSession` `:470` → `:568`), because the slice nets +98 lines in that file.

## 2. The projection semantics change (D-CENC-25)

The shared predicate now lives in `be/compass/counseling/services.py:191-207`:

```python
def appointment_encounter_matches(appointment: Appointment) -> bool:
    ...
    return CounselingEncounter.objects.filter(
        appointment_id=appointment.pk,
        student_id=appointment.student_id,
        counselor_id=appointment.provider_id,
        service_id=appointment.service_id,
        delivery_mode=appointment.delivery_mode,
        entry_mode=CounselingEntryMode.APPOINTMENT,
    ).exists()
```

`appointment_encounter_recorded` (`be/compass/counseling/services.py:210-232`) keeps its keyword-only
signature, its `bool | None` return type, and its exposure rule unchanged (non-Counselor role,
inactive, missing `counseling.view_assigned`, not the assigned provider, or non-canonical Counseling
service → `None`); it now ends with `return appointment_encounter_matches(appointment)`. Its docstring
lost the actual-times sentence because that reasoning moved to the predicate.

`be/compass/ecounseling/services.py:350-357` sets the workspace's fact from the same predicate while
resolving `id` from `_encounter_for_appointment` (`:250-251`, deliberately unchanged):

```python
encounter_summary = None
if encounter is not None and encounter.counselor_id == counselor.pk:
    encounter_summary = {"id": encounter.pk, "recorded": appointment_encounter_matches(appointment)}
```

### 2.1 Why the identity rule and not the times

The rule is CENC-1's `_encounter_matches` (`be/compass/counseling/finish_service.py:214-230`) minus the
actual times. A projection cannot know which times the Counselor would type, so comparing them would
make a surface say "not recorded" about a session that plainly was recorded. Finishing **does** compare
them, which is why `test_linked_non_matching_encounter_is_never_mistaken_for_a_finished_session` asserts
the 409 `counseling_finish_conflict` rather than a completion. The predicate is deliberately *not* the
finish comparison, and `_encounter_matches` is deliberately *not* reused.

### 2.2 Privacy and exposure matrix

| Viewer / state | `counseling_encounter_recorded` (Detail) | `counseling_encounter` (E-Counseling workspace) |
|---|---|---|
| Assigned Counselor, canonical Counseling service | `true` / `false` | `{id, recorded}` |
| No Encounter linked | `false` | `null` (unchanged: no summary at all) |
| Linked Encounter is `WALK_IN`/`REFERRED`/`CALLED_IN` | `false` | `{id, recorded: false}` → UI `MISMATCH` |
| Linked Encounter mismatches student / service / delivery mode | `false` | `{id, recorded: false}` → UI `MISMATCH` |
| Linked Encounter belongs to **another** Counselor | `false` (provider guard in the caller) | `null` — the counselor-matching guard at `:351` never leaks the id |
| Student or other actor | `null` | (route not reachable for them) |
| Non-Counseling service | `null` | `{id, recorded}` if an Encounter is somehow linked; UI ignores it because `finishCounselingState` returns `UNAVAILABLE` for a non-canonical service |

`recorded` never discloses anything the Counselor cannot already see in this session: the Encounter `id`
and the boolean both come from the same linked row that `View encounter` already navigated to.

### 2.3 Contract consequence

None. `CounselingEncounterWorkspaceSummary.recorded` was already a required plain `boolean`; this slice
gave a dead field its meaning. `be/tests/test_openapi_contract.py` asserts the property set is exactly
`{"id", "recorded"}`, that `recorded` is `{"type": "boolean"}` with no `anyOf`, that both are required,
and that `additionalProperties is False`. `export_openapi --check` reports the contract current and
`git diff --stat contracts/openapi.json` is empty.

## 3. The online state machine (D-CENC-23, D-CENC-24)

Decision and copy live in `fe/src/features/ecounseling/encounter-section-state.ts` as one pure function
`encounterSectionView`, mirroring `finish-counseling-availability.ts` so the section is testable without
the call runtime. Precedence is the implementation, quoted:

```ts
if (recorded || (appointmentReadConfirmed && finishState === "RECORDED"))     // :64  RECORDED
if (uncertainSave)                                                            // :69  UNCERTAIN
if (encounterId)                                                              // :80  MISMATCH
if (!canManageAssigned)                                                       // :89  READ_ONLY
if (joinState === ECounselingJoinState.OPEN)                                   // :95  WINDOW_OPEN
if (!appointmentReadConfirmed)                                                 // :104 FALLBACK_RECORD
if (finishState === "OFFERED")                                                 // :108 FINISH
                                                                               // :117 NOT_AVAILABLE
```

| State | Trigger | Status | Line | Actions |
|---|---|---|---|---|
| `RECORDED` | workspace `recorded`, or a confirmed read whose `finishState` is `RECORDED` | `Recorded` | `Encounter recorded.` | `view-encounter`, or `view-encounters` when no id is exposed |
| `UNCERTAIN` | an unconfirmed finish or record | `Not confirmed` | `unconfirmedFinishMessage` / `unconfirmedEncounterMessage` | `check-again`, `view-encounters` |
| `MISMATCH` | `id` present, `recorded === false` | `Not this Appointment’s record` | `A Counseling Encounter is linked to this Appointment but is not its Counseling-Appointment record. Review it in My counseling encounters.` | `view-encounter` |
| `READ_ONLY` | no `counseling.manage_assigned` | `Not yet recorded` | `Record the encounter after the counseling conversation.` | none |
| `WINDOW_OPEN` | `join_state === OPEN`, nothing above matched | `Not yet recorded` | `The online access period is still open. Finish counseling becomes available here once it ends.` | **none** |
| `FALLBACK_RECORD` | Appointment read not confirmed | `Not yet recorded` | `Record the encounter after the counseling conversation.` | `record` |
| `FINISH` | confirmed read + `finishState === "OFFERED"` | `Not yet recorded` | `Finish counseling after the conversation. This records the Encounter and completes the Appointment.` | `finish` |
| `NOT_AVAILABLE` | confirmed read + `finishState === "UNAVAILABLE"` + window not OPEN | `Not yet recorded` | `Finish counseling isn’t available for this session yet. Review the Appointment for its latest details.` | `view-appointment` |

### 3.1 Wiring (`ecounseling-workspace.tsx:352-532`)

- `canFinish = canManage && getAppointmentAccess(user).canManage` (`:367`) — Finish needs both
  capabilities, so the Appointment read is requested (`useAppointmentsGet`, `retry: false`, `:370`) only
  for a Counselor who could actually finish.
- Only `appointmentQuery.isSuccess` counts (`:371`); last-known data never confirms anything, so a failed
  read falls to `FALLBACK_RECORD` rather than claiming a state.
- `reloadEncounter()` (`:383-392`) keeps the Record path's invalidations and additionally invalidates
  `getAppointmentsGetQueryKey(appointmentId)`, because the Appointment's own fact now decides the next
  action.
- Success goes through `invalidateAfterCounselingFinish(queryClient, { appointmentId, routineInterviewId })`
  (`:410-413`), which already covers the E-Counseling workspace key (`finish-counseling-refresh.ts:59`),
  so no extra workspace invalidation was invented.
- Conflict → `handleFinishStale` (`:418-423`): close, notice, reload the Encounter **and**
  `appointmentQuery.refetch()`. Never resubmit.
- `checkFinishAgain` (`:426-437`) confirms
  `status === COMPLETED && counseling_encounter_recorded === true` from a fresh read and only then treats
  the finish as done — ADR-091, check don't replay.
- `openDialog` (`:451-458`) clears the notice and the uncertain flag, and each dialog's `open` prop is
  gated on `view.actions.includes(...)` (`:506`, `:517`) so a dialog can never be mounted for an action
  the state machine withdrew.
- Focus restore targets the section's own action container (`:462-467`), same rule CENC-2 uses.

## 4. What closed the OPEN-window bypass

`WINDOW_OPEN` (`:95`) is evaluated **before** both `FINISH` (`:108`) and `FALLBACK_RECORD` (`:104`), and
returns `actions: []`. So while `join_state === OPEN` there is no authoring control in the session at
all, even when the Appointment read failed — the fallback cannot smuggle a Record through the window.
`join_state` is read only as an explanation; nothing in this slice derives a status or an attendance
claim from it, from media, from capture, or from join/leave (D-CENC-24, D-CENC-07).

What still allows recording, stated plainly:

1. The **server** still allows `POST /api/v1/counseling/encounters` during an OPEN window; this slice
   adds no check there, because that would be a CENC-1-adjacent semantics change the slice forbids.
2. `Record encounter` remains reachable when the Appointment read is not confirmed (network failure, or
   a Counselor without `appointments.manage`, for whom the read is deliberately never issued).
3. Direct Walk-in/Called-in/Referred recording is untouched (D-CENC-22), as is the standalone
   appointment-recording list on `/portal/counseling`.

`MISMATCH` is evaluated before `WINDOW_OPEN` on purpose: a session whose Appointment already carries a
foreign record should say so rather than talk about the access window.

## 5. Copy inventory (provisional, D-CENC-18)

New strings, all in `encounter-section-state.ts` unless noted:

- `Recorded` / `Encounter recorded.` (`:65`)
- `Not this Appointment’s record` (`:83`) and the `MISMATCH` line (`:84`)
- `Not yet recorded` (`NOT_RECORDED`, `:51`)
- `The online access period is still open. Finish counseling becomes available here once it ends.` (`:99`)
- `Record the encounter after the counseling conversation.` (`:90`, `:105` — unchanged from the
  pre-slice section)
- `Finish counseling after the conversation. This records the Encounter and completes the Appointment.` (`:112`)
- `Not confirmed` + `unconfirmedFinishMessage` / `unconfirmedEncounterMessage` (`:70-75`, reused)
- `Finish counseling isn’t available for this session yet. Review the Appointment for its latest details.` (`:120`)

Control labels (`ecounseling-workspace.tsx:479-501`): `Finish counseling`, `Record encounter`,
`Check again` / `Checking…`, `View encounter`, `View encounters`, `View appointment`.

Result notices: the four `finishCounselingNotice` strings (reused unchanged);
`An encounter was already recorded for this Appointment. The latest details are now shown.` (`:401`,
kept verbatim from the pre-slice section); `${message} The latest details are now shown.` (`:420`);
`Counseling finished. The latest details are now shown.` (`:435`);
`The finish result is not confirmed. Check the Appointment details before trying again.` (`:525`).

Server-conflict copy is reused from `counseling-shared.tsx` unchanged:
`counseling_finish_conflict` (`:43`), `ecounseling_access_open` (`:45`),
`counseling_appointment_closed` (`:42`), `appointment_lifecycle_conflict` (`:44`).

Help copy (`session-help.tsx`):
- `:8` now ends `…leaving doesn’t complete the Appointment or record the Counseling Encounter; use
  Finish counseling when the session ends, and it doesn’t stop recording or transcription.`
- `:12` is `Finishing counseling records the Counseling Encounter and completes the Appointment in one
  action. It is separate from recording audio or video, and it is available once the online access
  period has ended.`
- No other help string changed. Apostrophes are typographic to match the surrounding copy.

## 6. Tests written

| File | What it proves |
|---|---|
| `be/tests/test_ecounseling.py` | `recorded` true for a matching Appointment-origin Encounter; false with no Encounter; false — with `id` still pointing at the linked record — for `WALK_IN`/`REFERRED` and for student/service/delivery mismatch; another counselor's linked Encounter never surfaced; `set(body) == set(before)` on every other workspace field; `provider_readiness.join_state` unchanged by the reads (reads wrapped in `override_settings(DAILY_ENABLED=True)`); Detail/E-Counseling parity across the four combinations; a linked non-matching Encounter yields 409 `counseling_finish_conflict` with the Appointment still `SCHEDULED` and exactly one Encounter |
| `be/tests/test_openapi_contract.py` | `recorded` is still a plain required `boolean` — proof of no contract change |
| `fe/tests/ecounseling-finish.test.mjs` (new, 361 lines, 14 tests) | All eight state rows including the read-driven `RECORDED`; nothing authoring while OPEN; `Record` only when the read is not confirmed; the two-capability conjunction; the 409 `ecounseling_access_open` and `counseling_finish_conflict` copy paths; `encounterCreatePayload` can only ever produce an `APPOINTMENT`-origin Encounter for the session (and the three direct modes send no `appointment_id`); plus a static `renderToStaticMarkup` of the real `ECounselingWorkspace` for FINISH / WINDOW_OPEN / FALLBACK_RECORD / RECORDED / MISMATCH |

CENC-1's finish tests were not modified; `tests/test_counseling_finish.py` passes as part of the
targeted backend run.

## 7. Reconciliations between the plan and the code

1. **Eight rows, not seven.** The plan's table has no row for "confirmed read, `finishState`
   `UNAVAILABLE`, window not OPEN" — e.g. a Cancelled or no-show Appointment reached from a stale
   session link. That state is real and must not silently fall through to `FALLBACK_RECORD`, so
   `NOT_AVAILABLE` (`:117`) shows `View appointment` instead of an authoring action.
2. **`READ_ONLY` is the named "no manage authority" row.** Its status and line stay exactly as today and
   it offers nothing, because a Counselor without `counseling.manage_assigned` could not use `Record`
   here anyway; the plan's "`View encounter` only" is satisfied one row earlier, since a linked Encounter
   reaches `RECORDED` or `MISMATCH` before the authority check.
3. **`RECORDED` accepts either projection.** The plan triggers it from workspace `recorded === true`; a
   fresh Appointment read of `RECORDED` is at least as authoritative, so `:64` honours both, and falls
   back to `view-encounters` when the workspace exposed no Encounter id (`:65`).
4. **`MISMATCH` outranks `WINDOW_OPEN`.** Not stated in the plan; see §4 for the reasoning.
5. **`apostrophe`**: `Not this Appointment’s record` uses the typographic form, matching the plan's
   intent and the surrounding copy.
6. **The old `alreadyRecorded` string survives as a notice.** `handleAlreadyRecorded` (`:399-403`) keeps
   the exact pre-slice sentence in a `role="status"` paragraph (`:475`) rather than as the state line, so
   the Record fallback's behaviour is preserved while the state machine stays the single source of the
   permanent message (`:476`).
7. **No fixture change was needed.** `fe/tests/support/ui-hierarchy-fixtures.mjs` is unmodified; the
   `recorded`/`id` variants the new tests need are built inside the test file.
8. **Workspace invalidation already existed.** The plan asked to "also invalidate the E-Counseling
   workspace key" on Finish; `invalidateAfterCounselingFinish` already does
   (`finish-counseling-refresh.ts:59`), so nothing was added on top of it.
9. **`reloadEncounter()` kept for Record only.** Finish goes through the shared invalidation set, which
   is a superset for the facts Finish changes.
10. **The static render worked.** The plan anticipated the call runtime blocking it; supplying an idle
    `ActiveECounselingCallContext.Provider` value was enough, and no file under
    `fe/src/features/ecounseling/runtime/` or `call/` was edited.
