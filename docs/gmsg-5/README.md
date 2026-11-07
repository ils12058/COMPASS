# GMSG-5 — Authorized Counselor case coordination

**Status:** implemented, uncommitted. Baseline `integration/ux15-modernization` at
`0349986a5af4efe08b84274776f1f0b380426248` (GMSG-4). No commit, push, merge or branch was created
for this slice.
**Institutional status:** D-GMSG-08 remains **Open — GCO/DPO**. The code prerequisite is
implemented; approval is not. The production communication-policy provider deliberately returns
`None`, so no grant can carry a `CASE_COORDINATION` purpose and no case conversation can be opened,
read, listed or replied to in production. Nothing here is GCO-, DPO- or UCN-approved.
**Provisional engineering defaults:** D-GMSG-07 option (a) — after revocation or expiry, deny new
sends, confidential history reads and resolve/reopen for both participants. D-GMSG-15 copy is the
proposal-specified placeholder, not approved wording.

## 1. Scope

One new conversation kind, `COUNSELOR_CASE_COORDINATION`, bound to exactly one
`CounselorCaseContinuityGrant` and its Student subject:

- exactly the grant's `original_counselor` and `receiving_counselor` participate; the Student is a
  subject, never a participant, recipient, viewer or notification target;
- one thread per `(grant, Student subject)` pair, guarded by a partial unique index;
- the thread exists only while the single Counseling predicate says the grant is live; revocation
  and expiry end sends, history reads, listing and resolve/reopen for both participants;
- contextual entry only: the panel is mounted on the coverage-detail page for an `ACTIVE`,
  `CASE_COORDINATION`-purpose grant the reader participates in; there is no generic chooser entry,
  no handler/assignment route, no work-queue entry and no notification;
- the grant's source-read scope (`ENCOUNTER`, `ROUTINE_EVALUATION`) is never reused as message
  authority.

## 2. The CONT communication scope

Migration `counseling/0006_case_communication_scope` adds two columns to
`CounselorCaseContinuityGrant` and one CHECK:

| Field | Shape | Meaning |
|---|---|---|
| `communication_purpose` | nullable `CASE_COORDINATION` only | Explicit content authority; `NULL` means no messaging authority |
| `communication_policy_digest` | `""` or 64 lowercase hex | Digest of the approved communication policy at recording time |

`counseling_grant_communication_scope` requires both-or-neither and, when present, a non-null
`original_counselor` and a SHA-256-shaped digest
(`be/compass/counseling/continuity_models.py:206-214`). Historical rows upgrade as `NULL` / `""`;
that is tested in `be/tests/test_continuity_migrations.py`.

`ApprovedCaseCommunicationPolicy` (`be/compass/counseling/case_communication_policy.py:21-52`) is a
frozen dataclass of `version`, `evidence_reference`, `valid_from`, `valid_until` and
`permitted_purposes`. Its digest is SHA-256 over `json.dumps(..., sort_keys=True)` of the dataclass
fields, with frozensets sorted and datetimes normalized to UTC ISO-8601. `validate(now)` rejects a
non-token version/evidence reference, naive or closed windows, an empty purpose set and any purpose
outside `ContinuityCommunicationPurpose`.

**Default-denied provider.** `get_approved_case_communication_policy()` returns `None`
(`case_communication_policy.py:55-57`). There is no settings, environment, environment-variable or
fallback path. `require_case_communication_policy(now)` raises
`ContinuityError("communication_policy_unconfirmed")` when the provider is `None` or invalid. Tests
substitute an isolated synthetic provider with `monkeypatch`; production cannot.

Recording a purpose also requires the original Counselor to be distinct from the receiving
Counselor (`invalid_original_counselor`), and both the continuity policy and the communication
policy are revalidated at approval and at every predicate evaluation. A changed communication
policy after recording conflicts the request and later denies the grant
(`communication_policy_unconfirmed`).

## 3. The single predicate

`authorize_case_coordination(*, actor, grant_id, now=None, lock=False)` in
`be/compass/counseling/case_communication.py:96-106` is the only place that answers “may this
Counselor coordinate about this Student now?”. `visible_case_coordination_grant_ids(*, actor,
now=None)` reuses `_evaluate` for list visibility and returns only live grant IDs.

`_evaluate` (`case_communication.py:51-93`) runs in this order:

1. exact pair and non-null distinct original Counselor → otherwise `not_found` (404);
2. `communication_purpose == CASE_COORDINATION` and a non-empty policy digest → otherwise
   `not_found` (404);
3. `revoked_at IS NOT NULL` or decision `REVOKED` → `case_access_ended`;
4. decision not `APPROVED` → `not_found` (404);
5. `now < starts_at` → `not_found` (404);
6. `now >= expires_at` → `case_access_ended`;
7. continuity policy (`policy_unconfirmed` on mismatch or unavailable) and communication policy
   (`communication_policy_unconfirmed`);
8. the persisted scope snapshot is recomputed with `continuity_services._snapshot`; policy errors
   are re-raised, every other snapshot/source-revision failure becomes `case_access_ended`;
9. `continuity_services._effective(...) != "ACTIVE"` → `case_access_ended`.

`ContinuityError` prefixes only `.code` with `continuity_`; the message contains the raw code.
Messaging translates the result in one helper, `_authorized_case_grant`
(`be/compass/guidance_messages/services.py:271-278`): `continuity_case_access_ended` becomes
`CaseCoordinationEnded`, everything else becomes `ThreadNotFound` (non-disclosing 404). The API then
maps `CaseCoordinationEnded` to 403 `guidance_messages_case_coordination_ended`
(`be/compass/guidance_messages/api.py:241-242`). Messaging code repeats none of the predicate's
conditionals; directory, thread read, list, send, mark-read, resolve/reopen, recipients and the
contextual resolver all call the same predicate.

The kind rule in `be/compass/guidance_messages/policy.py:90-99` is Counselor-only, grant-participant
scoped, with `guidance_messages.case_coordination.{view,manage}` and an action suffix. The visible
`IN` list is the predicate's live grant IDs, never a bare `kind=` branch.

## 4. Lock order and concurrency

Writes acquire locks in one order:

1. the actor row with `FOR NO KEY UPDATE` (`policy.current_actor(actor, lock=True)`);
2. an unlocked read of the thread's immutable `relationship_case_grant_id`;
3. the grant row with `FOR UPDATE` (`authorize_case_coordination(lock=True)`);
4. the thread row with `FOR UPDATE`.

`send_message` and `open_case_coordination_thread` use the same order
(`be/compass/guidance_messages/services.py:282-300`, `:759-834`), so a revocation that holds the
grant row serializes against a waiting send: the send re-evaluates after the revocation commits and
is refused. Read/list/context paths pass `lock=False`. Creation races converge on the partial unique
index `gm_case_grant_subject_unique`; the loser re-reads and reuses the winner's thread inside a
savepoint. Two-direction concurrent opens share one grant lock and thread lock, so they cannot
deadlock. These properties are tested with captured `FOR UPDATE` statements and live PostgreSQL
worker sessions in `be/tests/test_guidance_messages_concurrency.py`.

## 5. API and DTO

| Method | Path | Operation ID |
|---|---|---|
| GET | `/api/v1/guidance-messages/case-grants/{grant_id}/context` | `guidanceMessagesGetCaseCoordinationContext` |
| POST | `/api/v1/guidance-messages/case-grants/{grant_id}/thread` | `guidanceMessagesOpenCaseCoordinationThread` |

The context returns `thread`, `counterpart`, `can_start` and `access_ended`. `access_ended` is
returned only to a previously authorized pair after revocation/expiry; every other refusal is a
concealed 404. `GuidanceThreadResponse` gains two additive nullable fields: `student_subject`
(populated only for case threads, only after the predicate authorized the viewer) and
`relationship_case_grant_id`. There is no handler or assignment route for case threads.

## 6. Capabilities

Two provisional definitions in `be/compass/accounts/policy.py:230-239`, granted to `COUNSELOR`
only (`policy.py:729-730`):

- `guidance_messages.case_coordination.view` — depends on `guidance_messages.view`;
- `guidance_messages.case_coordination.manage` — depends on
  `guidance_messages.case_coordination.view`.

The live Counseling grant, not the capability, is the authority. Counts after this slice: 104
capability definitions, 113 role grants, 24 designation grants. GSS, IT Admin, Institutional
Officer, Head and DPO gain nothing.

## 7. Frontend

- `getGuidanceMessagesAccess` adds `canViewCaseCoordination` / `canManageCaseCoordination`
  (Counselor + broad `guidance_messages.view` + narrow capability; manage requires view). They feed
  `hasWorkspace` and `canWrite`, never `canStart`.
- `canWriteThread` routes `COUNSELOR_CASE_COORDINATION` to `canManageCaseCoordination`; broad
  manage does not write a case thread and case manage does not write any other kind.
- `guidance-case-coordination-context.ts` mirrors the appointment context: grant-keyed query,
  reconcile of context then thread/history, and every send goes through the canonical open
  endpoint.
- `GuidanceCaseCoordinationMessages` is mounted by the coverage-detail page only for an `ACTIVE`
  `CASE_COORDINATION` grant the reader participates in and can view. The trigger renders only when
  the backend offers a thread or `can_start`; an ended grant keeps an already-open panel to show the
  ended copy. The generic new-message chooser never offers the kind.

**Exact copy provenance.** The three constants live in
`fe/src/features/guidance-messages/guidance-messages-presentation.ts:125-128` and are reproduced
verbatim from the GMSG-5 brief, which attributes them to the proposal:

| Constant | Exact text | Use |
|---|---|---|
| `CASE_COORDINATION_ENTRY_COPY` | `Coordinate on this authorized case.` | Empty state before the first Message |
| `CASE_COORDINATION_ENDED_COPY` | `Your case coordination access has ended.` | Proposal-specified placeholder pending GCO wording (D-GMSG-15); rendered only when `access_ended` is true |
| `CASE_COORDINATION_UNAVAILABLE_COPY` | `This conversation is no longer available for new messages.` | 404 from a case send |

`describeSendError(..., "case-coordination")` maps 403 code
`guidance_messages_case_coordination_ended` to the ended copy and 404 to the unavailable copy. A
generic 403 never claims access ended, and the ended copy is not used outside case coordination.

## 8. Migrations and rollback

- `counseling/0006_case_communication_scope` depends on `counseling/0005_student_placement_marker`
  and the swappable user model; it adds the two columns and the CHECK.
- `guidance_messages/0006_case_coordination` depends on `guidance_messages/0005_counselor_direct`
  and `counseling/0006_case_communication_scope`; it activates the sixth kind choice.
- Both files are listed in `be/compass/common/canonical_migrations.json`.
- The case shape branch and `gm_case_grant_subject_unique` already existed from GMSG-1's
  generalized CHECK/index inventory; 0006 adds no second shape constraint.
- Reverse to `0005`/`guidance_messages 0005` is lossless for legacy rows; a created case row keeps
  its columns and kind text after reverse, as recorded in the migration tests.

## 9. What remains institutionally open

- **D-GMSG-08 — Open — GCO/DPO.** Institutional approval of the communication purpose and its
  evidence is not given. Until it is, the production provider stays `None` and the shipped surface
  is dormant: no grant can carry a purpose, so `authorize_case_coordination` denies every case
  grant and `visible_case_coordination_grant_ids` is empty.
- **D-GMSG-07 — Provisional — engineering default, not approved.** Option (a) is implemented:
  revocation and expiry deny sends, history reads and resolve/reopen for both participants.
- **D-GMSG-15 — Open — GCO.** The ended copy is a placeholder; approved wording may replace it.
- **D-GMSG-12 — Open — GCO/DPO.** No message notification exists, including for case
  coordination; the Student is never notified or given access.
- Any future notification, typing, read-receipt or work-queue participation for this kind requires
  its own approved decision; none is built here.
