# Cross-proposal readiness — FAC, CONT and SAR

**Audit base:** `5224256a76c07f4503b5e3d98fea65c4ed84f2a9`.
**Purpose:** determine what FUP-3A (Faculty Referral journey), FUP-3B (Counselor coverage) and FUP-3C
(SAR scope) can actually do at HEAD, and which institutional gates remain.

Claims are **Verified** by static code/document inspection unless labeled otherwise. No FAC, CONT or
SAR runtime journey was executed.

## 1. Readiness summary

| Slice | Technical state at HEAD | Institutional state | Verdict |
|---|---|---|---|
| **FUP-1** Source reconciliation / presentation | Existing detail `source_unavailable`; no review contract; no schema dependency for a projection-only slice | GCO has not decided the review policy | **Policy-blocked, not technically blocked** |
| **FUP-2** Completion / further-action UX | Existing terminal completion; no successor/predecessor/classification | GCO has not decided further-action meaning or initiation authority | **Policy-blocked, not technically blocked** |
| **FUP-3A** Faculty Referral journey | Referral has Faculty-origin + three administrative states; Faculty and GCO administrative APIs exist; generic Referral-linked Follow-Up path already works for staff; no Follow-Up fields in Faculty responses; no auto-close | FAC-D1–D10 unresolved; all Faculty/administrative policy providers return `None` | **Institutionally blocked; no new FUP bridge strictly required** |
| **FUP-3B** Counselor coverage | Continuity grant model exists with time bounds/revocation; runtime policy provider returns `None`; no Follow-Up adapter and no task-coverage authority | CONT D01–D18 unresolved; operational sharing blocked | **Blocked on CONT policy and a new task-authority design** |
| **FUP-3C** SAR scope | **Already code-satisfied.** `StudentAffiliation` is deleted; Follow-Up paths use `student_academics`; no live references remain | None for code; documentation/tests need reconciliation | **Verification-only** |
| **FUP-4** Full regression/UAT | Depends on delivered slices | UAT not executed | **Deferred** |

## 2. FAC — FUP-3A

### 2.1 What exists

| Primitive | Evidence | Status |
|---|---|---|
| `FACULTY` role and a two-capability ceiling | `accounts/policy.py:31,79,82-85,635` | **Verified** |
| Referral Faculty-origin fields: submission channel, submitter, submission time, home College, Student College at submission, policy digests/events | `be/compass/referrals/models.py:48-125` | **Verified** |
| Three Faculty-visible states: `SUBMITTED`, `RECEIVED_BY_GCO`, `ADMINISTRATIVELY_CLOSED` | `be/compass/referrals/administrative_state.py:7-19` | **Verified** |
| Faculty Referral API: availability, Student confirmation, submit, list own, get own | `be/compass/referrals/faculty_api.py:100-175`; mounted at `be/compass/api/v1/router.py:285` | **Verified** |
| GCO administrative metadata and transitions: get administration, acknowledge, administratively close | `be/compass/referrals/administrative_api.py:69-120`; mounted at `api/v1/router.py:284` | **Verified** |
| Faculty response deliberately contains only reference, timestamps, state, Student and received/closed facts | `faculty_api.py:54-61` | **Verified; no Follow-Up fields** |
| Referral void is independent of Follow-Ups | `referrals/services.py:896-940`; no Follow-Up reference in `be/compass/referrals` | **Verified** |
| Referral-linked Follow-Up source check has **no submission-channel restriction** | `policy.py:98-111` checks capability, Student, `voided_at`, and `get_referral` only | **Verified** |

### 2.2 What is already true for FUP-3A

- A GCO user who can view a Faculty-originated Referral can create a `REFERRAL_ACTION` /
  `OPERATIONAL` Follow-Up against it through the same source path as a legacy Referral
  (`policy.py:98-111`; `workspace.py:50-91`). No new bridge is required for the staff-side action.
- The Faculty API does not project Follow-Up ID, assignment, due date, activity, outcome or Counseling
  status (`faculty_api.py:54-61`). The Follow-Up domain does not write Referral administrative fields
  (`services.py:391-463` has no Referral write).
- Referral completion/closure is a separate Referral action; there is no `FollowUp.COMPLETED` →
  `ADMINISTRATIVELY_CLOSED` mapping in code. **Verified** by code absence.
- The current Follow-Up source filter rejects a **voided** Referral but does not treat
  `ADMINISTRATIVELY_CLOSED` as invalid (`policy.py:104-107` only checks `voided_at`). Therefore an
  operational task can remain linked to an administratively closed Referral. Whether that is desired
  is D-FUP-05 / FAC-D6 policy, not current code behavior. **Verified** predicate; policy **Open**.

### 2.3 What is not ready

| Gap | Evidence | Consequence |
|---|---|---|
| Faculty submission/confirmation/lookup policies all return `None` | `faculty_policy.py:147-152` | Faculty API is default-denied in the current code; no live Faculty submission |
| Acknowledgment, closure, tracking-disclosure and Faculty-notice policies all return `None` | `administrative_policy.py:109-122` | GCO acknowledgment/administrative closure cannot be activated through the reviewed providers |
| FAC-D1–D10 are unresolved | `docs/fac-5/institutional-decisions.md:1-4`; `docs/fac-5/readiness.md:10-12` | No authorized meaning for digital submission, acknowledgment, Student confirmation, placement routing, closure, disclosure or notices |
| No Follow-Up-specific Faculty acceptance test | `be/tests/test_guidance_followups.py` has no Faculty-origin Referral test | The "no leak / no auto-close" claim is verified structurally, not exercised end to end |
| Faculty UAT not executed | `docs/fac-5/readiness.md:11` | Cannot claim the Faculty journey works |

**Readiness verdict:** FUP-3A does not need a new database table or a new Faculty↔Follow-Up API at HEAD.
It needs (a) an explicit regression test proving a Faculty-originated Referral can be linked without
leaking into Faculty responses and without auto-closing, and (b) FAC institutional activation before
the end-to-end Faculty journey can be called complete. If GCO wants a dedicated Faculty-facing task
signal, that would be a new disclosure decision (FAC-D7), not an automatic consequence of Follow-Ups.

## 3. CONT — FUP-3B

### 3.1 What exists

| Primitive | Evidence | Status |
|---|---|---|
| Time-bounded grant: Student, original/receiving Counselor, coverage kind, reason, requested/decided/revoked provenance, start/expiry, policy evidence/digests, version | `be/compass/counseling/continuity_models.py:49-90,100-141` | **Verified** |
| Interval/decision/revocation database constraints | `continuity_models.py:138-177` | **Verified** |
| Policy abstraction with validation | `continuity_policy.py:1-109` | **Verified** |
| Runtime approval provider | `continuity_policy.py:99-109` — `get_approved_policy()` returns `None`; `require_policy` raises | **Verified** |
| Continuity API router | `be/compass/api/v1/router.py:266` | **Verified** |
| Follow-Up continuity adapter | static search of `be/compass/counseling` for `guidance_followup` returned no matches | **Verified absent** |
| Follow-Up policy grant branch | `policy.py:51-183` has no continuity call | **Verified absent** |

### 3.2 Why a read grant is not enough

The CONT source-record policy itself distinguishes the layers:

- A confidential Follow-Up needs **both** the selected Follow-Up and a permitted source relationship
  (`docs/cont-0/source-record-policy.md:21`).
- "A source grant read cannot satisfy current manage eligibility" (`:21`).
- CONT-F06 states that a read grant cannot satisfy confidential Follow-Up **manage** eligibility
  (`docs/cont-0/README.md:24`).
- CONT-F07 requires its own per-read authority, concurrency and content-free audit contract
  (`docs/cont-0/README.md:25`).

The code matches this: `require_source(manage=True)` requires the actor to be the source's
`counselor_id` (`policy.py:52-97`), and `require_assignee` requires the candidate to pass the same
check (`policy.py:144-156`). A continuity grant has no code path into either function. **Verified.**

### 3.3 What FUP-3B would require before implementation

1. CONT institutional approval and a real `get_approved_policy()` implementation with authentic
   evidence (not a settings switch).
2. A source-domain adapter that validates a specific grant for a specific Student/Encounter/Routine
   and returns only the approved fields. The Follow-Up domain must not decrypt or copy source
   narratives.
3. A **separate task-coverage authority**: permission to read selected professional context does not
   automatically mean permission to own, reassign, complete, cancel or create a confidential task.
4. A documented distinction between:
   - read-only delegated view,
   - accepting/owning a pending task,
   - creating a new confidential task,
   - reassigning an existing one.
5. Revocation/expiry behavior: every read and mutation rechecks the grant; old notifications and links
   cannot restore access; audit is content-free.
6. A decision on what happens to the original Counselor's task when coverage ends.
7. A test matrix including grant expiry, revocation, Student mismatch, source mismatch, Head/acting
   Head limits, and attempts to use a read grant for mutation.

Until then, the safest behavior is the current one: deny. **Inferred recommendation**, not policy.

### 3.4 What FUP-1/FUP-2 must not do

- Do not add a Head/acting-Head confidential override.
- Do not downgrade a confidential task to operational to enable coverage.
- Do not treat a source UUID, Referral link, or continuity grant ID as a task credential.
- Do not add a "recover confidential" path under the operational recovery UI.
- Do not persist source narratives in Follow-Up fields as a handoff shortcut.

All are consistent with current code and CONT's stated boundaries. **Verified** as current absences.

## 4. SAR — FUP-3C

### 4.1 The retirement is complete at HEAD

| Fact | Evidence | Claim |
|---|---|---|
| `StudentAffiliation` model is deleted | `be/compass/organization/migrations/0005_delete_studentaffiliation.py:13-15` | **Verified** |
| No live `be/compass` consumer remains | `docs/sar-5/validation.md:265,274-275`; static recheck found only the two historical migrations | **Verified** |
| Follow-Up operational scope uses the canonical profile | `policy.py:45-48` (`resolve_operational_responsibility_scope`), `:200-208` (SQL profile join) | **Verified** |
| Eligible Students use the SAR helper | `workspace.py:6-7,36-47` | **Verified** |
| Eligible assignees use current placement | `workspace.py:113-114` (`get_current_placement`) | **Verified** |
| Recovery uses the canonical profile | `recovery.py:57-64,72-117` | **Verified** |
| Bulk list/report scoping remains SQL-bounded | `policy.py:186-245`; `workspace.py:150-187` | **Verified** |
| SAR-3/4 explicitly migrated the Follow-Up sites | `docs/sar-3-4/implementation.md:37,41,56` | **Verified** |

**FUP-3C code status:** satisfied. The proposal's FUP-3C slice (proposal lines 6372, 6353, 6412) is
already implemented by SAR-2A/3/4. Re-running a `StudentAffiliation` migration would be wrong.

### 4.2 What remains for FUP-3C

| Remaining work | Type | Evidence/action |
|---|---|---|
| Update FUP proposal/README references that still say `StudentAffiliation` is current | Documentation | Proposal lines 5748, 6227; `docs/sar-0/README.md:37-38,55-58` are historical |
| Record that FUP-3C is code-satisfied and does not block FUP-1 | Documentation | This audit |
| Add or confirm a regression test for SAR College transfer + Follow-Up scope/recovery | Test only | Existing tests do not cover a transfer; see UAT-FUP-20 |
| Verify deployed staging state separately | Deployment | **Unknown**; no staging access |
| Do not add a second placement writer or fallback | Architecture | Existing code correctly uses one canonical source |

### 4.3 Residual `StudentAffiliation` references

| Location | Reference | Disposition |
|---|---|---|
| `be/compass/organization/migrations/0001_canonical_baseline.py` | Created the old model | Historical; must remain |
| `be/compass/organization/migrations/0005_delete_studentaffiliation.py` | Deletes the model | Historical; must remain |
| `docs/sar-0/README.md` | Describes the pre-SAR baseline | Historical; do not treat as HEAD truth |
| FUP proposal lines 5748, 6227, 6353, 6412 | Assumes old relationship | Stale for HEAD; FUP-3C is satisfied |
| Any seed/fixture/test outside migrations | Static search found none in `be/compass` | **Verified**; no live consumer |

No live code, seed, fixture, contract or generated client requires a `StudentAffiliation` migration.

## 5. Interaction rules to preserve across proposals

| Rule | Why | Evidence |
|---|---|---|
| Follow-Up completion never closes/voids a Referral | Separate ownership; future FAC closure is an explicit administrative act | `services.py:391-417`; no Referral write; proposal lines 5806-5818 |
| Referral voiding never silently cancels a Follow-Up | Preserve history and human review | `referrals/services.py:896-940`; no Follow-Up call; proposal lines 6319-6323 |
| A source read grant never becomes task manage authority | CONT read ≠ Follow-Up manage | `docs/cont-0/source-record-policy.md:21`; `policy.py:144-156` |
| Head designation never becomes confidential source access | Prevents designation-based clinical bypass | `accounts/policy.py:761-795`; `policy.py:169-182` |
| SAR placement changes affect operational scope, not historical source authorship | Preserve provenance | `policy.py:200-208`; `recovery.py:57-64` |
| Faculty sees no Follow-Up internals | Separate administrative projection | `faculty_api.py:54-61`; no FUP fields |
| Follow-Up never creates Appointments or Student messages | Domain ownership | `followups-create.tsx:81`; no Appointment write in services |

## 6. Exact blockers, by slice

### FUP-1

- **D-FUP-01:** what happens after a voided Referral, and whether review is mandatory.
- **D-FUP-07:** approved task meanings/copy/UAT.
- No technical dependency on FAC/CONT/SAR.

### FUP-2

- **D-FUP-03:** whether further action is UI-only or a durable classification/link.
- **D-FUP-04:** who may initiate a next task.
- **D-FUP-06:** notification behavior for continuing work.
- **D-FUP-07:** copy and UAT sign-off.
- No schema dependency if the decision is UI-only; `predecessor_followup_id` would add a migration.

### FUP-3A

- FAC-D1–D10, especially D5 (acknowledgment), D6 (closure), D7 (disclosure), D8 (notifications).
- Live Faculty/administrative providers are `None` (`faculty_policy.py:147-152`;
  `administrative_policy.py:109-122`).
- No FUP-specific code bridge is required for the staff-side link, but an end-to-end Faculty UAT is
  blocked.

### FUP-3B

- CONT D01–D18 and a real continuity provider (`continuity_policy.py:99-109`).
- A source-scoped read adapter and a separate task-coverage authority.
- Revocation/expiry/audit evidence.
- CONT-F06 (`docs/cont-0/README.md:24`) explicitly bars treating read access as manage eligibility.

### FUP-3C

- No code blocker. Documentation/regression-test cleanup only.

### FUP-4

- All delivered slices and UAT decisions.
- Full backend, frontend, browser, PostgreSQL, OpenAPI and migration regression; not run in FUP-0.
