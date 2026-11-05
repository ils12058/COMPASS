# CENC-0 — Appointment × Encounter action matrix

**Status:** read-only static audit at `04d2581b` (2026-11-05). Claims are **Verified**,
**Inferred** or **Unknown**. This file answers which states are reachable **today**, which actions
each state permits **today**, and which actors can perform them. Proposal #9's target matrix is shown
separately for comparison; it is not current behavior.

---

## 1. State matrix at HEAD

Legend for action columns:

- **Yes** = the service permits it when its other preconditions hold (authorization, time, E-Counseling).
- **No** = the service explicitly rejects it.
- **N/A** = not applicable / no such action.
- **Idem** = returns the existing record without a new transition.

| Appointment | Encounter | Reachable at HEAD | Complete | No-show | Cancel | Reassign | Record another Encounter | Context matching Encounter | Feedback exists |
|---|---|---|---|---|---|---|---|---|---|
| `SCHEDULED` | none | **Yes**, normal booking | Yes at/after `starts_at`, E-Counseling not `OPEN` | Yes after `ends_at`, E-Counseling not `OPEN` | Yes before `starts_at`, access not started, no room | Yes before `starts_at`, no Routine/Encounter/room | Yes | No (none) | No |
| `SCHEDULED` | linked, `entry_mode=APPOINTMENT` | **Yes**, Encounter recorded first or after start | Yes | **No** (`COUNSELING_ENCOUNTER_LINKED`) | Yes before `starts_at` (no Encounter check) | **No** (Encounter linked) | **No** (one-to-one already used) | Yes if facts/time match | Yes |
| `SCHEDULED` | linked, `entry_mode!=APPOINTMENT` | **Yes** via API create/update; UI does not normally send it | Yes | **No** | Yes before `starts_at` | **No** | **No** | **No** (entry mode mismatch) | Yes |
| `COMPLETED` | none | **Yes**, administrative/clinical completion | Idem (`COMPLETED`) | **No** (`NOT_SCHEDULED`) | **No** (`NOT_SCHEDULED`) | **No** (`NOT_SCHEDULED`) | **Yes** (candidate list includes `COMPLETED`) | No (none) | No |
| `COMPLETED` | linked, matching | **Yes**, normal terminal combination | Idem | **No** | **No** | **No** | **No** | Yes | Yes |
| `COMPLETED` | linked, `entry_mode!=APPOINTMENT` | **Yes** via create/update | Idem | **No** | **No** | **No** | **No** | **No** | Yes |
| `CANCELLED` | none | **Yes**, normal cancellation | **No** (`NOT_SCHEDULED`) | **No** | Idem | **No** | **No** (status rejected) | No | No |
| `CANCELLED` | linked | **Yes, exceptional**: link while `SCHEDULED`, then cancel before start; cancellation does not check Encounter | **No** | **No** | Idem | **No** | **No** | Maybe, if facts/time match (Appointment status is not part of the matching query) | Yes |
| `NO_SHOW` | none | **Yes**, normal no-show | **No** | Idem | **No** | **No** | **No** | No | No |
| `NO_SHOW` | linked | **No through services**: no-show refuses an existing Encounter; create/update refuse `NO_SHOW`. Only legacy/manual DB state. | **No** | **No** | **No** | **No** | **No** | Maybe (status not part of matching query) | Yes |
| Any | Encounter attached to another Appointment | **No** through services; one-to-one link is validated and not reassociated | — | — | — | — | — | — | — |
| Any | Conflicting finalized Routine | **No** through linking; finalized evaluation cannot be invalidated by correction | — | — | — | — | — | — | — |

### 1.1 Evidence for the matrix

| Row / behavior | Evidence |
|---|---|
| Statuses and terminal consistency | `be/compass/appointments/models.py:13-17,122-163` |
| Complete permits `SCHEDULED` only, not before start, not while E-Counseling `OPEN`; idempotent `COMPLETED` | `appointments/services.py:1583-1602` |
| No-show permits `SCHEDULED` only, after end, not while E-Counseling `OPEN`, refuses linked Encounter | `appointments/services.py:1638-1666` |
| Cancel permits `SCHEDULED` only, before start, access not started, no room; **no Encounter check** | `appointments/services.py:1066-1093` |
| Reassign refuses Routine, Encounter or room | `appointments/services.py:1377-1393` |
| Encounter creation accepts `SCHEDULED` or `COMPLETED`; rejects `CANCELLED`/`NO_SHOW`; rejects already-used Appointment | `counseling/services.py:285-319` |
| Encounter creation allows non-`APPOINTMENT` entry mode with `appointment_id` | `counseling/services.py:480-532`; `counseling/models.py:83-89` |
| Correction can attach/detach Appointment and change entry mode independently | `counseling/services.py:857-951`; `be/tests/test_counseling.py:794-827` |
| Complete/no-show/cancel action projection reflects the above | `appointments/services.py:1886-1922`; `be/tests/test_appointment_action_projection.py:56-109` |
| No-show terminal and Encounter rejection | `be/tests/test_final_api_lifecycle_completion.py:285-348` |
| Completion provenance | `be/tests/test_final_api_lifecycle_completion.py:185-235` |
| Completed + Encounter context extension | `be/tests/test_counseling_context.py:344-385` |
| Completed without Encounter context expires after grace | `be/tests/test_counseling_context.py:387-430` |

### 1.2 How `CANCELLED` + Encounter is reachable

**Verified code path; reachable consequence is Inferred from the verified services.**

1. A future `SCHEDULED` Appointment exists.
2. A Counselor records an Encounter with `appointment_id` set and actual times that are in the past
   (`create_encounter` accepts this; `_validate_appointment_link` does not compare actual times to
   the scheduled window — `counseling/services.py:285-319,480-549`).
3. Before the Appointment's `starts_at`, the provider cancels it. `cancel_appointment` checks status,
   E-Counseling access/room and start time, but **not** the Encounter
   (`appointments/services.py:1066-1093`).

The result is a `CANCELLED` Appointment with a linked Encounter and a Feedback opportunity. No
service path can then attach or detach that link while the Appointment is `CANCELLED`, because
`_validate_appointment_link` accepts only `SCHEDULED`/`COMPLETED` (`counseling/services.py:294-298`).
The proposal classifies this as an exceptional inconsistent/legacy state requiring a dedicated
remediation policy (proposal line 6935); at HEAD it is reachable through ordinary API calls, not only
through legacy data. This strengthens the case for CENC-1 rejecting Finish on cancelled/no-show and
for a later remediation decision (D-CENC-09).

### 1.3 `SCHEDULED` + Encounter is not a corner case

Recording an Encounter does not complete the Appointment. The form says so explicitly
(`fe/src/features/counseling/record-encounter-form.tsx:358`), and the backend never changes the
Appointment (`counseling/services.py:452-605`). A Counselor who records first and forgets
**Complete appointment** leaves exactly this state. The completion projection still offers Complete
and does not warn that an Encounter exists (`appointments/services.py:1911-1915`), while no-show is
blocked (`:1916-1922`).

---

## 2. Authorization matrix at HEAD

Legend: **Yes** = allowed when the normal record/time preconditions also hold; **No** = denied;
**404** = not found/concealed; **—** = no such route for that actor.

| Actor | View Counseling Appointment | Complete Appointment | Cancel | No-show | Record Encounter for Appointment | Record direct Encounter | View Encounter | Finish (proposed) |
|---|---|---|---|---|---|---|---|---|
| Assigned Counselor (active, capabilities current) | Yes | Yes (`appointments.manage` + provider) | Yes before start | Yes after end, no Encounter | Yes (`counseling.manage_assigned`) | Yes, any active Student (no relationship scope) | Own only | Proposed yes, narrow |
| Other Counselor | 404 (relationship-only) | 404 | 404 | 404 | 404 | Yes, any active Student | Own only | Proposed 404 |
| Head Guidance, **not** selected provider | 404 | 404 | 404 | 404 | 404 | Yes (Head is also a Counselor) | Own only | Proposed 404 |
| Head Guidance, selected provider | Yes | Yes | Yes | Yes | Yes | Yes | Own only | Proposed yes |
| GSS | 404/empty | 404 | 404 | 404 | No (role and capability) | No | No | Proposed no |
| IT Admin | 403/404 | 403 | 403 | 403 | No | No | No | Proposed no |
| Student (own Appointment) | Yes (`appointments.view_self`) | No | Yes before saved cutoff (`appointments.manage_self`) | No | No | No | No | Proposed no |
| Student (another Student) | 404 | No | 404 | No | No | No | No | Proposed no |
| Faculty | — | — | — | — | — | — | — | Proposed no |

### 2.1 Evidence

| Claim | Evidence |
|---|---|
| Counseling Appointment is `RELATIONSHIP_ONLY`; provider only | `appointments/access.py:24-27,47-72` |
| Provider list/detail/cancel works; other Counselor/Head/GSS denied | `be/tests/test_appointment_management_scope.py:365-440` |
| Head sees only when selected provider | `be/tests/test_appointment_management_scope.py:444-476` |
| GSS has `appointments.manage` but no Counseling capability | `accounts/policy.py:698-723` |
| Counselor has `appointments.manage`, `counseling.view_assigned`, `counseling.manage_assigned` | `accounts/policy.py:654-696` |
| Head designation adds `appointments.manage` but no `counseling.*` | `accounts/policy.py:758-783` |
| Encounter API requires active Counselor role plus capability | `counseling/api.py:239-244,573-605` |
| Student self view/cancel | `appointments/services.py:553-563,1063-1064`; policy `accounts/policy.py:725-753` |
| Direct Encounter has no relationship scope | `counseling/services.py:796-812`; `be/tests/test_counseling.py:1196-1265` |
| Encounter detail self-only | `counseling/services.py:787-793`; `be/tests/test_counseling.py:908-917` |

### 2.2 Authorization conclusions for CENC-1

1. **Verified**: the proposal's actor rule — assigned, active Counselor only — can be expressed
   with existing capabilities and record-level checks. No new capability is needed for the normal
   path (`counseling.manage_assigned` + `appointments.manage` + provider identity are all present in
   the COUNSELOR grant and in `appointment_management_access_allowed`).
2. **Verified**: GSS/IT Admin/other Counselors cannot even see a canonical Counseling Appointment.
   CENC-1 must preserve that concealment and return not-found semantics, not a distinct
   "not assigned" message.
3. **Verified gap**: direct Encounter authoring is broader than the Appointment path. CENC-1 must not
   use the direct path to bypass the Appointment relationship, and should not widen it. D-CENC-21
   asks whether to narrow it separately.
4. **Verified**: a Head who is the selected provider is treated exactly like the assigned Counselor.
   A Head who is not the provider gets nothing. The proposal's "Head not arbitrary" rule matches
   HEAD behavior.

---

## 3. Unreachable or rejected combinations at HEAD

| Combination / attempt | Result | Evidence |
|---|---|---|
| Two Encounters linked to one Appointment | DB one-to-one prevents; service raises `CounselingAppointmentAlreadyUsed` | `counseling/models.py:39-45`; `counseling/services.py:313-319`; error mapping `counseling/api.py:270-271` |
| `NO_SHOW` + Encounter created afterwards | Rejected: create accepts only `SCHEDULED`/`COMPLETED`; no-show refuses existing Encounter | `counseling/services.py:294-298`; `appointments/services.py:1661-1666` |
| `CANCELLED` + new Encounter link | Rejected by create/update link validation | `counseling/services.py:294-298,944-951` |
| Encounter for a non-Counseling Service | Rejected: canonical Service identity and Appointment service equality | `counseling/services.py:249-251,500-504` |
| Encounter for a Group Session/Fixed-Date record with no canonical Appointment | Rejected before creation; no Appointment identity exists | same; proposal line 6873 |
| `entry_mode=APPOINTMENT` without `appointment_id` | Rejected by service and DB constraint | `counseling/services.py:552-553`; `counseling/models.py:83-89` |
| Equal, reversed or future actual end | Rejected | `counseling/services.py:184-187` |
| Complete before scheduled start | Rejected | `appointments/services.py:1590-1593` |
| Complete while E-Counseling `OPEN` | Rejected | `appointments/services.py:1595-1602` |
| No-show before scheduled end | Rejected | `appointments/services.py:1647-1650` |
| Cancel after access started or with room | Rejected | `appointments/services.py:1074-1083` |
| Cancel/reassign after Appointment starts | Rejected | `appointments/services.py:1084-1087,807-813` |
| Reassign with Routine, Encounter or room | Rejected | `appointments/services.py:1377-1393` |
| Encounter reassociation to a different Appointment | Rejected when target already used or identity differs; source link is one-to-one | `counseling/services.py:313-319,944-951` |
| Replace a finalized Routine's linked Encounter | Rejected | `routine_interviews/services.py:1200-1252`; `counseling/services.py:966-1004` |
| Match an unrelated Encounter by Student/date similarity | No such code path | `routine_interviews/matching.py:39-68` |

**Inferred**: `NO_SHOW` + Encounter can exist only through direct database/manual state or data that
predates the current no-show guard. No service inspected creates it. CENC-0 found no migration or
seed that does so; this is not a claim that staging contains no such row (`Unknown`, no DB read).

---

## 4. Comparison with proposal §7

Proposal matrix: lines 6925–6940. "Proposed" below means proposal intent, not current behavior.

| Proposal row | Proposal behavior | HEAD behavior today | Gap class |
|---|---|---|---|
| `SCHEDULED` / none | Primary Finish: create Encounter + complete atomically | Two independent actions; either can happen alone | **Missing composition** |
| `SCHEDULED` / matching Encounter | Reconcile completion, never duplicate/rewrite | Complete is allowed; no reconciliation label or notice; no duplicate possible | **Missing explicit reconciliation UX/contract** |
| `COMPLETED` / none | Authorized Counselor may record genuinely occurred session, preserve prior completion provenance | Encounter creation is allowed and provenance is untouched; there is no dedicated action or completion-time preservation test | **Missing guided recovery; mechanics already safe** |
| `COMPLETED` / matching Encounter | Already-finished result; no new writes except safe deterministic link | Creation blocked by duplicate; complete is idempotent; no single projection says "already finished" | **Missing authoritative result** |
| `CANCELLED` / none | Reject Finish | Create/complete already reject; no Finish exists | Compliant but uncomposed |
| `NO_SHOW` / none | Reject Finish | Create/complete already reject; no Finish exists | Compliant but uncomposed |
| `CANCELLED`/`NO_SHOW` / Encounter | Exceptional; controlled investigation, no overwrite | Reachable for `CANCELLED` via pre-start link + cancel; no remediation path; `NO_SHOW` only legacy/manual | **Policy + remediation gap** |
| Encounter attached to another Appointment | Conflict; no reassociation | Rejected by link validation and one-to-one | Compliant |
| Conflicting finalized Routine | Preserve finalized Evaluation; reject mutation | Finalized mismatch rejected on update; linking skips mismatch silently | **Partial: conflict is not surfaced at creation** |

---

## 5. Race and concurrency behavior at HEAD

No race test was run; the table is **Verified** code-path analysis and **Inferred** consequence.
No composed Finish exists, so its races are described in the implementation plan instead.

| Race | Serialization today | Observed/expected outcome | Evidence |
|---|---|---|---|
| Two `create_encounter` requests for the same Appointment | Both lock the Appointment; one inserts, the other hits one-to-one and maps to `CounselingAppointmentAlreadyUsed` | One Encounter; one 409 | `counseling/services.py:480-549,313-319`; unique one-to-one `counseling/models.py:39-45` |
| Create Encounter vs Complete Appointment | Both lock the Appointment, but they touch different state | Both succeed → `COMPLETED` + Encounter if create first; if complete first, create still succeeds. No partial failure because there is no composition. | `counseling/services.py:487`; `appointments/services.py:1577-1584` |
| Create Encounter vs no-show | Both lock the Appointment; create validates status; no-show checks Encounter | If create commits first, no-show rejects; if no-show commits first, create rejects. Coherent terminal state. | `counseling/services.py:487,515-521`; `appointments/services.py:1643-1666` |
| Create Encounter vs cancel | Both lock the Appointment; cancel does **not** check Encounter | If create commits first and the appointment has not started, cancel succeeds → `CANCELLED`+Encounter. If cancel first, create rejects. Order-dependent exception. | `appointments/services.py:1066-1093` |
| Complete vs cancel | Both lock the Appointment; each requires `SCHEDULED` | Exactly one transition wins; the loser rejects (cancel is idempotent only for `CANCELLED`, complete only returns `COMPLETED`) | `appointments/services.py:1066-1069,1586-1589` |
| Complete vs no-show | Both lock; each requires `SCHEDULED` | One wins; the other rejects | `appointments/services.py:1586-1589,1641-1646` |
| Reassign vs create Encounter | Reassign locks Appointment and checks relationships; create locks Appointment and validates provider | If reassign first, old Counselor's create fails provider equality; if create first, reassign sees Encounter and rejects. Coherent. | `appointments/services.py:1396-1499,1377-1393`; `counseling/services.py:515-521` |
| Encounter correction vs Routine finalization | Correction locks Routine dependencies first; finalization locks Routine then Encounters; `ensure` uses `skip_locked` | Designed to avoid replacement and deadlock; correction validates against the linked Routine. **Verified** design comments, **Inferred** scheduling. | `counseling/services.py:815-854,966-1004`; `routine_interviews/services.py:1200-1252,1255-1288,1365-1456` |
| Feedback creation race | `get_or_create` + unique source; IntegrityError fetch fallback | One opportunity | `feedback/services.py:256-267`; `feedback/models.py:59-64` |

**Deadlock risk in a future Finish operation**: a composed service that locks the Appointment
before the Routine would invert the documented Routine-first order used by Encounter creation and
Routine mutations (`routine_interviews/services.py:1261-1265`; `counseling/services.py:482-486`).
The implementation plan requires Routine → Appointment → Users → Service and a concurrency test.

---

## 6. Derived "Needs documentation" today

**Verified**: no projection, query, endpoint, field or frontend element exists. The only related
facts are:

- Appointment status and completion provenance;
- whether a linked Encounter exists (`appointments/services.py:1857-1858` for the action projection);
- the Encounter candidate list including `COMPLETED` (`counseling/services.py:664-672`).

There is no way for a Counselor to see, from Appointment Detail or a worklist, that a `COMPLETED`
Appointment has no Encounter. After Counseling Context expires, the `Open Counseling` link disappears
(`appointment-detail-page.tsx:592` uses `counseling_context_available`), and the only path left is
the general Record Encounter form with its Appointment search. This is a discoverability gap, not an
automatic-attendance risk: recording still requires explicit Counselor input.

**Inferred**: a `COMPLETED` Appointment with no Encounter is not proof that documentation is
missing — the Appointment may have been completed administratively and no session occurred. The
proposal treats the indicator as derived and not persisted (lines 6929–6940); CENC-1 should not
introduce a persisted attendance state.
