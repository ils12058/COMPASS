# Selected-read authorization contract

`continuity_access.read_selected_continuity_record` is a bounded two-kind domain coordinator, called by the source-owned Encounter and Routine entry points. It returns a validated projection after commit, never a reusable permission decision or bearer token. There is no generic HTTP source/model selector.

For every call it independently checks:

1. Reloaded active canonical COUNSELOR identity and effective `counseling.continuity.read_selected` (including its view dependency). Encounter additionally requires `counseling.view_assigned`; Evaluation requires `routine_interviews.view_assigned`. Those ordinary codes alone never establish cross-author ownership.
2. A current, fully validated operational policy and an independently validated disclosure policy. Missing policy fails before ciphertext retrieval/decryption. No production provider is enabled.
3. Exact receiving identity, APPROVED state, `starts_at <= now < expires_at`, current Grant version and the sealed material/scope snapshot. Source reads never trust an earlier ACTIVE metadata response.
4. Current Student role/activity/lifecycle, unchanged affiliation marker and applicable active College/Campus within **both** policy scopes. Receiver responsibility/College does not substitute for the exact Grant; legitimate cross-College receiving remains possible.
5. Current original approval actor's supported role, effective approval capability and policy-named Head designation through CONT-2A's effective-status predicate. Head approval alone never grants source readership. Original author/requester departure does not revoke historical provenance by itself.
6. Exact `(kind, source UUID, projection)` in the sealed scopes. Neither a valid UUID nor a later-created record qualifies automatically.
7. Source-owned lifecycle, Student, historical author/link and structural revision checks under source locks. No approved scope is silently refreshed after source change.
8. On HTTP calls, the current opaque AuthSession row, same credential digest, matching actor, unrevoked state and future expiry. Session revocation or rotation during initial request authorization cannot reuse stale authenticated state for disclosure.
9. Reauthorization after source locking, after decryption/typed projection preparation and again after synchronous Audit insertion. Expiring capabilities, policy and Grant/session windows are recalculated from backend time.

No source write/manage/assignment function accepts this coordinator's result. Ordinary `routine_interviews.services.get_assigned()` retains its exact Counselor filter. Existing Context resolver/defaults and Summary author/Student routes remain independent.

## Separate disclosure evidence

`ApprovedDisclosurePolicy` requires version/reference; approved basis and Student transparency evidence; retention, monitoring and coordination evidence; effective dates; explicit College IDs; and immutable typed source projections. An `ApprovedSourceProjection` contains an allowlisted kind/projection pair, a nonempty exact field set, `FINALIZED_COMPLETED_V1` lifecycle and `SEALED_STRUCTURAL_REVISION_V1` revision rule. Unknown categories, projections, fields or rules deny. Encounter V1 requires approval of its complete six-field inventory; Evaluation V1 permits only an explicitly approved subset of its nine pinned names.

The validator checks structure and bounds; **an opaque reference string is not proof that an institution approved it**. A future reviewed provider must resolve authentic current evidence and obey the policy-publication fence with transactionally visible authoritative storage, without cached allow state. This provider does not yet exist. Test fixtures return explicit synthetic values only. No consent/basis workflow, policy management UI, general feature flag or emergency exception is created.

The complete disclosure digest binds fields, evidence, dates, scope, lifecycle/revision rules and policy revision into the operational policy's optional `disclosure_policy_digest`. Existing Grant `policy_digest` and `snapshot_digest` then bind that decision. A changed disclosure document cannot widen an old approved Grant, even if a provider reuses the same version label. Updating the operational binding invalidates the old Grant snapshot and requires a new request. Empty binding retains byte-equivalent CONT-2A metadata behavior and provides no disclosure authority.

## Routes and safe denial behavior

- `GET /api/v1/counseling/continuity-grants/{grant_id}/encounters/{encounter_id}/metadata` — `counselingContinuityGetSelectedEncounterMetadata`.
- `GET /api/v1/counseling/continuity-grants/{grant_id}/routine-evaluations/{routine_interview_id}` — `counselingContinuityGetSelectedRoutineEvaluation`.

Both require integer `expected_version >= 1`. Unknown query keys (including field/projection/model selectors) are rejected. There are no POST/PUT/PATCH/DELETE variants, list/history, file, streaming or export operations.

Existing session authentication returns 401 for unauthenticated requests; an expired/revoked/rotated in-flight session gives `continuity_session_unavailable` (401). Unsupported role, missing capability, unconfirmed operational/disclosure policy or unavailable release coordination gives 403. Missing, unrelated, noneffective or unselected Grant/source gives concealed 404. Unrelated Grants are filtered by receiver **before locking**, so another receiver's row contention does not reveal their Grant. Stale version, altered snapshot/revision or bounded lock conflict gives 409 for otherwise applicable operations; a missing required version/unknown query gives 422. Authorized unreadable encrypted content gives generic `continuity_source_unavailable` (503), without codec reason, token, key or plaintext. Required Audit failure returns no projection and rolls back; the central API handler returns a safe error.

Every response/denial inherits the existing continuity `Cache-Control: private, no-store` middleware. No overlapping cache mechanism or new notification channel is introduced.
