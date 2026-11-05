# CENC-0 — Risk Register for CENC-1

**Status:** Audit output. No runtime, schema, generated-artifact, test, seed or Git change was made by
CENC-0.

**Audit base:** `integration/ux15-modernization` @ `04d2581baae3350eb25cc301ea36755775c1b98a`
(2026-11-05). **Proposal reference:** Proposal #9 §24 (lines 7763–7785) and §25 (lines 7789–7812).

**Claim labels:** *Verified* = static evidence at a path:line; *Inferred* = reasoned from verified
code; *Unknown* = evidence or command still required. Likelihood/impact ratings are **Inferred**
judgments for planning, not measurements. Proposal text is referenced as proposal, never as verified
behavior.

**Scope:** risks to the proposed CENC-1 backend slice in `implementation-plan.md`. Risks that are
already present at HEAD are marked **Current**; risks that would be introduced or left unresolved by
CENC-1 are marked **Slice**. "Owner" means the role that must decide or act, not an approval already
obtained.

---

## 1. Summary

| ID | Risk | Type | Severity (Inferred) | CENC-1 treatment |
|---|---|---|---|---|
| R-01 | Appointment `COMPLETED` mistaken for proof of Counseling attendance | Current + Slice | High | Explicit attestation + actual times; no auto-Encounter on administrative completion |
| R-02 | Duplicate Encounter for one Appointment | Current + Slice | High | One-to-one constraint, Appointment row lock, replay semantics |
| R-03 | Partial success across Appointment and Counseling | Current | High | One composed transaction; legacy partial states remain until callers migrate |
| R-04 | Deadlock from Routine/Appointment lock order | Slice | Medium | Routine → Appointment → Encounter → Users → Service order; concurrency tests |
| R-05 | Duplicate Feedback invitations | Current + Slice | Medium | Reuse `ensure_feedback_opportunity`; replay creates nothing |
| R-06 | Scheduled time recorded as actual time | Current + Slice | High | Required actual times; no server fallback; dedicated test |
| R-07 | Former/other Counselor modifies or finishes another provider's record | Current + Slice | High | Fresh provider + capability checks under lock; provider 404 |
| R-08 | GSS/IT Admin/Head gains professional-record privileges | Current + Slice | High | No capability or policy change; negative authorization tests |
| R-09 | Open E-Counseling room bypassed by Finish | Slice | High | Delegate to `complete_appointment`; explicit open-window recheck |
| R-10 | Encounter linked to the wrong Routine Interview | Current + Slice | High | Deterministic facts only; pre-validation + postcondition check |
| R-11 | Historical completion timestamp/provenance rewritten | Current + Slice | High | `complete_appointment` early return; no new completion event |
| R-12 | Feedback request sent for a non-session | Current + Slice | Medium | Only a newly created verified Encounter creates an opportunity |
| R-13 | Direct walk-in/called-in/referred recording removed or gated | Slice | High | Legacy endpoint and direct modes untouched |
| R-14 | Worklists overstate attendance / documentation gaps look like no-shows | Current | Medium | No stored Needs-documentation state; later derived projection only |
| R-15 | New UI/client breaks existing API consumers | Current | Low–Medium | No legacy route change; contract regeneration in CENC-1; FE in CENC-2 |
| R-16 | Confidential Counseling content leaks into operational responses/notifications | Slice | High | Identifier-only response; no content fields; existing notification copy |
| R-17 | New prerequisites block real sessions | Slice | Medium | No Intake/Inventory/Evaluation gate added |
| R-18 | Scattered implementation creates competing Finish flows | Slice | Medium | One composed service; legacy endpoints remain but are not duplicated |
| R-19 | Cross-proposal scope creep (FUP/CONT/FAC/SAR) | Slice | Medium | Core CENC only; no downstream authoring in the transaction |
| R-20 | Appointment-linked Encounter with non-`APPOINTMENT` entry mode is treated as matching | Current | High | Finish rejects with conflict; correction path is the remedy |
| R-21 | Any active Counselor can record an Encounter for any active Student (unscoped direct mode) | Current | High–Medium (policy-dependent) | Out of CENC-1; flag for separate decision D-CENC-22 |
| R-22 | Feedback invitation for late documentation is stale or inappropriate | Slice | Medium | Existing policy retained; decision D-CENC-12 |
| R-23 | Silent Routine link failure reports success without a link | Current | Medium | Postcondition check turns it into a rollback/conflict |
| R-24 | Legacy create leaves `SCHEDULED` + Encounter; later Finish/cancel behavior surprises staff | Current + Slice | Medium | Finish reconciles identical facts; cancel still allowed before start |
| R-25 | Contract/generated artifacts drift | Slice | Medium | Regenerate `contracts/openapi.json`; update operation-ID test; Orval in CENC-2 |
| R-26 | Staging seed/workflow assumptions diverge from the new path | Slice | Low | Seed continues to call canonical services; no seed change required |
| R-27 | Provider is deactivated/reassigned between rendering and Finish | Slice | Medium | Fresh checks under lock; non-provider gets 404; no client-supplied author |
| R-28 | Actual times backdated beyond policy | Current + Slice | Medium–High (policy) | Current rule only rejects future end; GCO policy decision D-CENC-06 |
| R-29 | Race between Finish and legacy complete/cancel/no-show creates contradictory history | Current + Slice | Medium | Row lock serialization; stable conflict outcomes |
| R-30 | Documentation implies GCO/UAT/privacy/clinical approval | Audit process | Low | Every doc labels proposal vs verified; no approval claimed |

---

## 2. Detailed risks

### R-01 — Appointment `COMPLETED` mistaken for Counseling attendance

**Type:** Current + Slice. **Severity:** High.

**Evidence (Verified):** `complete_appointment` writes status/provenance and audit only; it creates
no Encounter and no clinical fact (`be/compass/appointments/services.py:1603–1617`). The frontend's
Complete confirmation says only that the Appointment will no longer be scheduled
(`fe/src/features/appointments/appointment-detail-page.tsx:221–227`). A `COMPLETED` Appointment with
no Encounter is reachable today (`current-state.md` §2–3; `action-matrix.md`).

**Why it matters:** Staff or reports may read `COMPLETED` as "Counseling happened." The proposal
explicitly separates the administrative and clinical facts (§3, lines 6667–6671; §6.1(4), line
6875).

**CENC-1 mitigation:** Finish requires the Counselor's `counseling_occurred=true` attestation and
actual times; `complete_appointment` is never changed to create Encounters; no signal, job, admin
action or seed gains that behavior. A `COMPLETED`-without-Encounter Appointment remains a
documentation gap, not an inferred session.

**Residual:** CENC-1 does not change existing UI copy that might imply completion equals attendance;
that is CENC-2 copy work (D-CENC-18). Reporting semantics remain GCO decision D-CENC-15.

**Owner:** GCO (copy/reporting); Engineering (implementation).

---

### R-02 — Duplicate Encounter for one Appointment

**Type:** Current + Slice. **Severity:** High.

**Evidence (Verified):** One-to-one link (`be/compass/counseling/models.py:39–45`); duplicate
rejection and IntegrityError translation (`counseling/services.py:313–319`, `:376–381`);
`counseling_appointment_already_used` is already returned by the legacy API
(`counseling/api.py:270–271`). Proposal risk table line 7768.

**CENC-1 mitigation:** The Appointment row is the serialization point; Finish checks the linked
Encounter under lock before inserting; `create_encounter`'s uniqueness check and the database
constraint remain the final safeguard; a duplicate insert is translated to `EXISTING` only when the
facts match, otherwise to a stable conflict. Concurrency tests cover two finishes and finish vs.
legacy create.

**Residual:** The legacy create endpoint can still race and return its existing 409; that is
expected and documented.

**Owner:** Engineering.

---

### R-03 — Partial success across Appointment and Counseling

**Type:** Current. **Severity:** High.

**Evidence (Verified):** The two operations are independent; no composed service or endpoint exists
(`current-state.md` §2, §9; `be/compass/counseling/api.py:573–605`;
`be/compass/appointments/api.py:1105–1121`). Frontend staff perform a sequence
(`ux-journeys.md` J-01).

**CENC-1 mitigation:** One outermost `transaction.atomic()`; complete then create; any mandatory
failure rolls back both. The response reports the authoritative outcome. No frontend chain is used.

**Residual:** Until the frontend adopts Finish (CENC-2), staff can still produce partial states via
the legacy actions. CENC-1 does not remove those actions (D-CENC-03).

**Owner:** Engineering; GCO for frontend rollout.

---

### R-04 — Deadlock from Routine/Appointment lock order

**Type:** Slice. **Severity:** Medium.

**Evidence (Verified):** Routine-before-Appointment is documented and implemented
(`routine_interviews/services.py:1261–1288`); `create_encounter` locks Routine, then Appointment,
then sorted users, then Service (`counseling/services.py:481–495`); `update_encounter` uses
Routine deps → Encounter → users → sorted Appointments → Service (`:857–1046`). Proposal risk line
7770.

**CENC-1 mitigation:** Finish follows the same order: Routine → Appointment → Encounter → Users →
Service. It never locks Appointments in a loop and never loads unbounded cross-domain data inside
locks. `complete_appointment` and `create_encounter` only re-acquire rows already held.

**Residual:** Unknown whether a concurrent Routine finalization that locks Encounters in a different
order could interleave; the concurrency test matrix covers finalize vs. Finish. If a deadlock is
observed in test, the plan must pause for a lock-order audit rather than add retries.

**Owner:** Engineering.

---

### R-05 — Duplicate Feedback invitations

**Type:** Current + Slice. **Severity:** Medium.

**Evidence (Verified):** `ensure_feedback_opportunity` uses `get_or_create` plus a unique
`(source_type, source_id)` constraint (`feedback/services.py:256–267`,
`feedback/models.py:59–64`); Encounter creation creates the opportunity and optional informational
invitation (`counseling/services.py:360–375`); rollback on side-effect failure is tested
(`be/tests/test_counseling.py:284–324`). Proposal risk line 7771.

**CENC-1 mitigation:** Exactly one Encounter per Appointment; replay creates no Encounter and therefore
no opportunity or notification; no new Feedback code path. Tests assert counts unchanged on replay.

**Residual:** A Feedback invitation may still be sent for a late-documented session; that is a policy
question (R-22 / D-CENC-12), not a duplication defect.

**Owner:** Engineering; GCO for policy.

---

### R-06 — Scheduled time recorded as actual time

**Type:** Current + Slice. **Severity:** High.

**Evidence (Verified):** Encounter stores only `started_at`/`ended_at` actual times
(`counseling/models.py:48–49`); validation requires aware, ordered, non-future values
(`counseling/services.py:172–188`). The current form presents scheduled times as a reference only
(`record-encounter-form.tsx:47–61`, `:81–85`). Proposal risk line 7772.

**CENC-1 mitigation:** Request requires both actual times; the service never reads Appointment
`starts_at`/`ends_at` into the Encounter; missing values are 422; a dedicated test uses values
different from the scheduled interval and asserts stored actual times.

**Residual:** A future UI could prefill actual times from scheduled times if it labels them poorly;
CENC-2 must show provenance and require confirmation (D-CENC-07).

**Owner:** Engineering; GCO for UI wording.

---

### R-07 — Another/former Counselor modifies or finishes a record

**Type:** Current + Slice. **Severity:** High.

**Evidence (Verified):** Appointment management requires the provider relationship for Counseling
(`appointments/access.py:47–72`); current tests prove relationship-only scope
(`test_appointment_management_scope.py:365–440`); `create_encounter` checks the Appointment provider
(`counseling/services.py:299–304`). Proposal risk line 7773.

**CENC-1 mitigation:** API role/capability checks plus a fresh provider check and
`appointment_management_access_allowed` under the Appointment lock; no client-supplied counselor;
non-provider gets 404 (no existence leak). Reassignment races are serialized by the Appointment row.

**Residual:** The legacy direct Encounter path is self-only for reading and editing, but a Counselor
can record for any active Student (R-21). CENC-1 does not change that.

**Owner:** Engineering; GCO for coverage policy (D-CENC-02).

---

### R-08 — GSS/IT Admin/Head gains professional-record privileges

**Type:** Current + Slice. **Severity:** High.

**Evidence (Verified):** GSS has `appointments.manage` but no Counseling capabilities
(`accounts/policy.py:698–723`); the Counseling Appointment access policy is RELATIONSHIP_ONLY
(`appointments/access.py:24–27`); tests prove GSS cannot manage Counseling appointments
(`test_appointment_management_scope.py:365–440`); Head designation adds `appointments.manage` but
not Counseling capabilities (`accounts/policy.py:758–783`). Proposal risk line 7774.

**CENC-1 mitigation:** No capability or policy-provider change; endpoint requires an active
`COUNSELOR` with both `counseling.manage_assigned` and `appointments.manage`; service requires
provider identity. Negative tests for Student, GSS, IT Admin, non-provider Head, other Counselor.

**Residual:** If GCO later decides GSS should finish (D-CENC-02/03), that requires a separate
policy decision and implementation; CENC-1 must not pre-build it.

**Owner:** GCO; Engineering.

---

### R-09 — Open E-Counseling room bypassed by Finish

**Type:** Slice. **Severity:** High.

**Evidence (Verified):** `complete_appointment` rejects while the E-Counseling access window is OPEN
(`appointments/services.py:1595–1602`); for an already-COMPLETED Appointment it returns before that
check (`:1586–1587`). The public window function exists (`ecounseling/services.py:201`). Proposal
risk line 7775.

**CENC-1 mitigation:** For `SCHEDULED`, delegate to `complete_appointment`. For `COMPLETED`,
read-only recheck `ecounseling_access_window` and reject if OPEN. Tests cover both. Finish never
manually forces a room/capture state.

**Residual:** Unknown whether a `COMPLETED` Appointment can have an OPEN window through any
non-public path; CENC-1 treats that as a reject, not a bypass. If an operational workflow needs late
documentation during an open room, GCO must decide (D-CENC-10).

**Owner:** Engineering; GCO for sequencing policy.

---

### R-10 — Encounter linked to the wrong Routine Interview

**Type:** Current + Slice. **Severity:** High.

**Evidence (Verified):** Routine matching uses explicit facts only — student, counselor, canonical
service, delivery mode, completion, appointment identity or direct entry mode; no similarity
(`routine_interviews/matching.py:39–68`). Finalization requires an Encounter and blocks replacement
(`routine_interviews/models.py:124–155`; `routine_interviews/services.py:1365–1456`). Proposal risk
line 7776.

**CENC-1 mitigation:** Lock the Routine first; pre-validate deterministic facts when a Routine exists;
let `create_encounter` link in the same transaction; verify `Routine.counseling_encounter_id` after
creation and roll back on failure. Never create a Routine.

**Residual:** `link_appointment_encounter` silently returns `False` on mismatch today
(`routine_interviews/services.py:1324–1357`); the postcondition check prevents Finish from reporting
success, but the legacy Encounter path still tolerates the silent no-link. Changing that global
behavior is out of CENC-1 scope and should be a separate review.

**Owner:** Engineering.

---

### R-11 — Historical completion timestamp/provenance rewritten

**Type:** Current + Slice. **Severity:** High.

**Evidence (Verified):** `complete_appointment` early-returns for `COMPLETED`, preserving
`completed_at`/`completed_by` (`appointments/services.py:1586–1587`); fields exist at
`appointments/models.py:84–91`; proposal §14.8 (lines 7340–7342) and risk line 7777.

**CENC-1 mitigation:** Always call `complete_appointment`; never write completion fields directly;
never emit a second `APPOINTMENT_COMPLETED` for a replay; tests assert the original actor/time and
single audit event after late documentation.

**Residual:** The late-documentation policy itself must be approved (D-CENC-04).

**Owner:** GCO; Engineering.

---

### R-12 — Feedback request sent for a non-session

**Type:** Current + Slice. **Severity:** Medium.

**Evidence (Verified):** Feedback is created only when an Encounter is created
(`counseling/services.py:360–375`); no completion path creates one. Proposal risk line 7778.

**CENC-1 mitigation:** Only a newly created, explicitly attested Encounter triggers the existing
policy. Finish adds no other Feedback source.

**Residual:** A mistakenly completed Appointment still creates no Feedback, but a mistakenly recorded
Encounter does. Correction/retention policy is D-CENC-17.

**Owner:** Engineering; GCO.

---

### R-13 — Direct walk-in/called-in/referred recording removed or gated

**Type:** Slice. **Severity:** High.

**Evidence (Verified):** Entry modes exist (`counseling/models.py:14–18`); direct creation requires
student and delivery mode and rejects `APPOINTMENT` without an Appointment
(`counseling/services.py:552–605`); the frontend exposes the direct form
(`counselor-encounters.tsx`). Proposal risk line 7779.

**CENC-1 mitigation:** No change to `POST /counseling/encounters` or its modes; Finish is additive.
Tests confirm direct modes still work.

**Residual:** None identified for the core flow; direct-mode scope is R-21.

**Owner:** Engineering.

---

### R-14 — Worklists overstate attendance / documentation gaps look like no-shows

**Type:** Current. **Severity:** Medium.

**Evidence (Verified):** No `Needs documentation`/`requires_documentation` implementation exists at
HEAD (search in `current-state.md` §2; `README.md` static counts). Completion and Encounter are
independent, so `COMPLETED` without an Encounter is invisible as a gap. Proposal risk line 7780.

**CENC-1 mitigation:** None by design — CENC-1 must not introduce a stored state or a worklist.
Any indicator remains a later derived projection (proposal §15; D-CENC-08/D-CENC-14).

**Residual:** Staff still lack a gap view after CENC-1. This is a known scope boundary, not a
regression.

**Owner:** GCO; later CENC slice.

---

### R-15 — New UI/client breaks existing API consumers

**Type:** Current. **Severity:** Low–Medium.

**Evidence (Verified):** Both legacy endpoints are used by the frontend and staging seed
(`current-state.md` §9); the committed contract is checked by
`be/tests/test_openapi_contract.py:893–894`; Orval generates the frontend client from
`contracts/openapi.json` (`fe/orval.config.ts`). Proposal risk line 7781.

**CENC-1 mitigation:** Legacy routes unchanged; CENC-1 only adds a route and schemas and regenerates
the committed contract; the frontend client is regenerated and consumed in CENC-2, not in CENC-1.

**Residual:** Until CENC-2, the new endpoint has no UI. The frontend can continue the legacy
sequence; that is intentional for slice independence.

**Owner:** Engineering.

---

### R-16 — Confidential Counseling content leaks into operational responses/notifications

**Type:** Slice. **Severity:** High.

**Evidence (Verified):** Current Encounter responses expose identifiers, identity summaries, service,
times and timestamps only (`counseling/api.py:299–331`, `:119–130`); Feedback invitation copy is
informational (`notifications/policy.py:328–339`); completion audit metadata contains only reference
code/transition (`appointments/services.py:1607–1617`). Proposal risk line 7782.

**CENC-1 mitigation:** Finish returns identifiers and booleans only; no Evaluation, Session Summary,
Feedback, referral or message content; no new notification event; audit metadata limited to existing
IDs/transitions.

**Residual:** Response fields must be reviewed again when CENC-2 adds next-action links (D-CENC-13);
links must enforce destination authorization.

**Owner:** Engineering; Privacy/GCO review as required.

---

### R-17 — New prerequisites block real sessions

**Type:** Slice. **Severity:** Medium.

**Evidence (Verified):** Routine Intake/Evaluation and Inventory are separate workflows; no coupling
exists at Encounter creation beyond the deterministic Routine link
(`routine_interviews/services.py:1255–1305`). Proposal risk line 7783.

**CENC-1 mitigation:** No Intake, Inventory, Evaluation, Session Summary or Follow-Up gate is added;
Finish requires only the existing Appointment/Encounter preconditions.

**Residual:** A conflicting/finalized Routine causes a 409 per the deterministic rule. If operations
find this blocking in practice, GCO must decide the remediation path (D-CENC-11), not disable the
rule.

**Owner:** GCO; Engineering.

---

### R-18 — Scattered implementation creates competing flows

**Type:** Slice. **Severity:** Medium.

**Evidence (Verified):** Today there are two separate mutations plus contextual entry points
(`current-state.md` §8–9). Proposal risk line 7784.

**CENC-1 mitigation:** One composed service and one endpoint; the two legacy endpoints remain
compatible but CENC-2 will route the primary UI through Finish. No second composition is created.

**Residual:** Legacy paths remain usable indefinitely unless a later slice retires them; the project's
destructive-change policy permits a direct cutover, but that requires a separate decision.

**Owner:** GCO; Engineering.

---

### R-19 — Cross-proposal scope creep (FUP/CONT/FAC/SAR)

**Type:** Slice. **Severity:** Medium.

**Evidence (Verified):** Boundaries are documented in `cross-domain.md`; Feedback is created inside
Encounter creation; Routine linking is bounded; no Follow-Up/Summary/Evaluation authoring exists in
the completion path. Proposal risk line 7785 and out-of-scope lines 7816–7836.

**CENC-1 mitigation:** Core CENC only; no Follow-Up creation, no Session Summary publication, no
Referral closure, no Faculty reporting, no summary generation, no Evaluation finalization inside the
transaction.

**Residual:** CENC-2 next-step links may create integration pressure; hold them to navigation-only
until separate proposals cover the mutations.

**Owner:** GCO; Engineering.

---

### R-20 — Non-`APPOINTMENT` entry mode on an Appointment-linked Encounter

**Type:** Current. **Severity:** High.

**Evidence (Verified):** `_validate_appointment_link` does not require `entry_mode=APPOINTMENT`
(`counseling/services.py:285–319`); the database constraint only enforces
APPOINTMENT → link, not link → APPOINTMENT (`counseling/models.py:83–89`); correction can change
entry mode while retaining the link (`test_counseling.py:794–827`); Counseling Context matching
requires `entry_mode=APPOINTMENT` (`context_access.py:73`), and Routine matching rejects others.
Full analysis: D-CENC-21.

**Why it matters:** An Encounter can be attached to an Appointment yet not be recognized as that
Appointment's matching Encounter. Finish must not silently adopt it as the clinical fact.

**CENC-1 mitigation:** Finish treats a linked non-`APPOINTMENT` Encounter as
`counseling_finish_conflict` and directs to correction; it never rewrites entry mode. Tests cover
this.

**Residual:** The legacy create path can still produce this state (e.g., REFERRED linked to an
Appointment). Closing it requires a separate invariant/validation decision (D-CENC-21), potentially a
migration or stricter validation in a later slice.

**Owner:** Engineering; GCO for record semantics.

---

### R-21 — Any active Counselor can record directly for any active Student

**Type:** Current. **Severity:** High–Medium depending on policy.

**Evidence (Verified):** `list_students` returns all active Students with no College/lifecycle scope
(`counseling/services.py:796–812`); `create_encounter`'s direct branch checks the counselor/student
active role and service rules but not a relationship
(`counseling/services.py:560–605`); tests prove a Counselor can record for an out-of-scope/graduated
student (`test_counseling.py:1196–1265`); details/list remain self-only. Full analysis: D-CENC-22.

**Why it matters:** The proposal's "assigned/authorized Counselor" language is about the Appointment
path. The direct path is broader than the Appointment relationship policy.

**CENC-1 mitigation:** None. Finish applies the strict provider rule. CENC-1 must not accidentally
widen or tighten the direct path; this requires a separate GCO/security decision.

**Residual:** Unknown whether this is intended walk-in coverage behavior. Until confirmed, document it
and do not build on it for Finish.

**Owner:** GCO; Security/Privacy review.

---

### R-22 — Feedback invitation for late documentation is stale or inappropriate

**Type:** Slice. **Severity:** Medium.

**Evidence (Verified):** Encounter creation always creates an opportunity and optional invitation
(`counseling/services.py:360–375`); no age/currentness rule exists in the Feedback services. Proposal
decision D12 (line 7804).

**CENC-1 mitigation:** Retains the existing policy (no silent suppression, no new rule). The behavior
is documented and tested so it is not a surprise.

**Residual:** If GCO wants suppression or an age threshold, it needs a policy change in Feedback
services, likely outside CENC-1.

**Owner:** GCO.

---

### R-23 — Silent Routine link failure reports success without a link

**Type:** Current. **Severity:** Medium.

**Evidence (Verified):** `link_appointment_encounter` returns `False` on a mismatch without raising
(`routine_interviews/services.py:1324–1357`); `_link_recorded_encounter` ignores the return value
(`counseling/services.py:445–449`).

**CENC-1 mitigation:** Finish locks the Routine first and pre-validates deterministic facts; after
creation it asserts the link and rolls back on failure. The response reports the link truthfully.

**Residual:** The legacy Encounter path still tolerates the silent no-link. A later slice may align
it, but doing so now could change existing behavior beyond CENC-1's scope.

**Owner:** Engineering.

---

### R-24 — Legacy `SCHEDULED` + Encounter and cancel-before-start surprises

**Type:** Current + Slice. **Severity:** Medium.

**Evidence (Verified):** An Encounter can be recorded for a `SCHEDULED` Appointment
(`counseling/services.py:294–298` accepts SCHEDULED); cancel is blocked once the E-Counseling access
starts but otherwise does not check for an Encounter (`appointments/services.py:1042–1124`), so
`CANCELLED` + Encounter is reachable. `action-matrix.md` records the paths.

**CENC-1 mitigation:** Finish reconciles an identical existing Encounter by completing the
Appointment; it rejects contradictory facts. Cancellation semantics are not changed.

**Residual:** Staff can still cancel before start after recording, producing `CANCELLED` +
Encounter. Whether to block that is a separate lifecycle decision (D-CENC-09) and would affect the
legacy cancel path.

**Owner:** GCO; Engineering.

---

### R-25 — Contract/generated artifact drift

**Type:** Slice. **Severity:** Medium.

**Evidence (Verified):** The committed contract must match the schema (`be/README.md:445–459`);
`test_openapi_contract.py:893–894` asserts an exact operation-ID set; Orval generates the frontend
client (`fe/orval.config.ts`). CENC-0 deliberately did not run the exporter or generator.

**CENC-1 mitigation:** Add the operation ID to the expected set, assert the closed schemas, regenerate
`contracts/openapi.json`, and run `export_openapi --check`. Orval/client regeneration belongs to
CENC-2 when the frontend consumes the endpoint.

**Residual:** If CENC-1 ships backend-only, `contracts/openapi.json` changes without the generated TS
client; that is acceptable if documented and the frontend does not yet call the route. Alternatively,
regenerate the client in CENC-1 without using it; the plan recommends deferring to CENC-2 to keep the
slice minimal.

**Owner:** Engineering.

---

### R-26 — Staging seed/workflow divergence

**Type:** Slice. **Severity:** Low.

**Evidence (Verified):** `staging_seed/workflows.py` calls the canonical `complete_appointment` and
`create_encounter` services (`:105–154`); no seed calls a future Finish service.

**CENC-1 mitigation:** The seed remains valid because the legacy services are unchanged. Optionally,
a later slice may add a Finish-based seed path for UAT; that is not required for correctness.

**Residual:** UAT fixtures may not exercise Finish until CENC-2; UAT cases are proposed only, not
executed.

**Owner:** Engineering.

---

### R-27 — Provider deactivated/reassigned between render and Finish

**Type:** Slice. **Severity:** Medium.

**Evidence (Verified):** Appointment management access requires an active actor and provider
relationship (`appointments/access.py:47–72`); reassignment blocks when an Encounter exists
(`appointments/services.py:1377–1393`). No client-supplied author exists in the proposed request.

**CENC-1 mitigation:** All identity/assignment checks run fresh under the Appointment lock; the new
provider may finish, the former provider gets 404; no client field can override the actor.

**Residual:** If a reassignment occurs after the Encounter exists, the new provider can view/manage
only per existing relationship rules; correction/coverage policy is D-CENC-02/D-CENC-17.

**Owner:** GCO; Engineering.

---

### R-28 — Actual times backdated beyond policy

**Type:** Current + Slice. **Severity:** Medium–High (policy).

**Evidence (Verified):** The only time bound is "end not in the future" plus ordering
(`counseling/services.py:172–188`); no maximum age/backdating limit exists.

**CENC-1 mitigation:** Reuses the current rule and adds no new limit, so the slice does not silently
create policy. Tests cover future/reversed values.

**Residual:** Unknown whether GCO permits indefinite retrospective documentation (D-CENC-06). If a
limit is required, it belongs in the shared Encounter validation and affects the legacy path too.

**Owner:** GCO.

---

### R-29 — Race with cancel/no-show/administrative complete

**Type:** Current + Slice. **Severity:** Medium.

**Evidence (Verified):** All three operations lock the Appointment row
(`appointments/services.py:1055`, `:1578`, `:1633`); their state preconditions differ; complete and
cancel are currently independent of Encounter existence (except no-show, which checks it at
`:1661–1666`). Proposal §14.6 (lines 7321–7334).

**CENC-1 mitigation:** Serialization on the Appointment row yields a single canonical outcome and a
stable conflict for the loser; tests cover finish vs. each operation. No silent merge is attempted.

**Residual:** A cancel that wins before start can still leave `CANCELLED` + Encounter (R-24), because
cancel does not check Encounters. CENC-1 does not change that rule.

**Owner:** Engineering; GCO for lifecycle policy.

---

### R-30 — Documentation implies approvals not obtained

**Type:** Audit process. **Severity:** Low.

**Evidence (Verified):** All CENC-0 files label claims and state that no GCO/UAT/privacy/clinical
approval is claimed. Proposal §25 (lines 7789–7812).

**CENC-1 mitigation:** Keep the label discipline in implementation notes and test evidence; never
describe proposed copy or UAT steps as approved or executed.

**Residual:** None if discipline is maintained.

**Owner:** Documentation author; reviewer.

---

## 3. Risks CENC-0 could not resolve (Unknown)

| Unknown | Why it remains | Needed evidence |
|---|---|---|
| Whether GSS should retain an administrative Complete action on Counseling Appointments | Policy decision, not code | GCO decision D-CENC-03 |
| Whether late documentation after administrative completion is permitted | Policy decision; plan permits per proposal | GCO decision D-CENC-04 |
| Whether direct Encounter creation for any active Student is intended | Policy/security decision | GCO/security decision D-CENC-22 |
| Whether a backdating limit is required | Policy decision | GCO decision D-CENC-06 |
| Whether a composite audit event is required | Reporting policy | GCO decision D-CENC-20 |
| Whether a request key is required | Security review | Proposal §14.7; CENC-1 security review |
| Whether `COMPLETED` + OPEN E-Counseling is reachable outside public paths | Requires runtime/database evidence | Production-state review or invariant test; CENC-1 rejects if observed |
| Deadlock behavior under real concurrent load | Requires concurrency execution | CENC-1 `TransactionTestCase` races; staging observation |
| Whether `link_appointment_encounter`'s silent no-link is relied on elsewhere | Cross-domain audit beyond CENC-0 scope | Separate call-site review before changing it |

## 4. Go/no-go conditions for CENC-1

CENC-1 should not start until:

1. D-CENC-02/03/04 are confirmed (or explicitly deferred with the plan's restrictive default
   accepted).
2. The security/privacy reviewer accepts the identifier-only response and the 404-not-provider
   behavior.
3. The test environment can run the targeted PostgreSQL `TransactionTestCase` concurrency tests.
4. The contract-export procedure is available and the operation-ID test update is scheduled with the
   endpoint.

CENC-1 should stop and return to GCO if any of these occurs during implementation:

- A model/migration change appears necessary (the default is no migration).
- A new capability or flag appears necessary.
- The deterministic Routine rule cannot be satisfied without a policy change.
- A legacy caller depends on the exact current error code/behavior that composition would change.
- Concurrency tests expose a lock-order or duplicate-record defect.

No GCO approval, institutional sign-off, UAT execution, deployment readiness, privacy approval, or
clinical validation is claimed by this register.
