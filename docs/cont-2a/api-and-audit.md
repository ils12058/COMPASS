# Metadata API and transactional audit

Django Ninja registers the focused `continuity_api` router under `/api/v1/counseling/continuity-grants`. Every operation uses existing opaque cookie session authentication and existing error envelopes. Unsafe requests retain canonical CSRF enforcement. Input schemas forbid extra fields and enumerate all response fields; arbitrary clinical text, policy evidence supplied by the caller, generic filters and narrative decisions are not accepted.

| Method/path suffix | Operation ID | Behavior |
| --- | --- | --- |
| GET root | counselingContinuityListGrants | Policy-authorized own/received or approved office metadata; scope before pagination; page size 1–50 |
| GET /{grant_id} | counselingContinuityGetGrant | Same independent visibility and current authoritative checks; concealed unrelated UUID |
| POST root | counselingContinuityRequestCoverage | New exact Student/receiver/source snapshot; expected_version=0 and actor-scoped request_id required; 201 |
| POST /{grant_id}/approve | counselingContinuityApproveGrant | Independent current policy-named Head, exact snapshot/revisions, live identities and interval; expected_version required |
| POST /{grant_id}/decline | counselingContinuityDeclineGrant | Same professional authority/separation, requested-state decision |
| POST /{grant_id}/cancel | counselingContinuityCancelGrant | Requester only, requested-state withdrawal |
| POST /{grant_id}/revoke | counselingContinuityRevokeGrant | Current independent Head with approve and revoke authority; bounded reason, terminal state |

Approval/revocation do not require or return source bodies. Grant metadata contains UUID identities, technical coverage/reason enums, request/decision/revocation metadata, interval, backend-derived status, version, opaque policy/evidence references and exact typed scope revisions. No Student name, institutional ID, free-text reason, evaluation answer, score, Intake concern, content ciphertext, media URL or credential is selected for these responses. Future `read_selected` eligibility is not exposed as a reusable allow token.

The no-store middleware matches only this exact route prefix (plus children) and applies `Cache-Control: private, no-store` to success, authentication/capability/policy errors, CSRF and validation errors, concealed not-found and unimplemented source/content/export paths. It is placed before maintenance/security/session middleware so downstream denials retain the header. Ordinary Context/source routes are not changed by this middleware. Actual external proxy behavior is not claimed from local header tests.

Safe error family (canonical envelope):

- 401: existing session-authentication error.
- 403: continuity_invalid_role, continuity_missing_capability, continuity_policy_unconfirmed, continuity_approval_authority_missing, continuity_self_approval.
- 404: continuity_not_found for nonexistent or unrelated grants; continuity_source_not_found uniformly conceals missing/wrong-Student/unentitled/draft exact source references.
- 409: continuity_stale_version, continuity_invalid_transition, continuity_request_conflict, continuity_overlap, continuity_scope_changed, continuity_source_changed, continuity_source_busy, continuity_student_changed.
- 422: continuity_invalid_interval, continuity_invalid_scope, continuity_duplicate_scope, continuity_invalid_source_category, continuity_invalid_purpose, continuity_ineligible_student/receiver, continuity_invalid_original_counselor, continuity_invalid_revocation_reason, continuity_invalid_request_id, continuity_invalid_pagination; canonical schema validation also returns 422.

Role/capability checks do not depend on guessed UUID existence. Missing policy denies before protected resource existence is revealed. Current Head designation alone is not a blanket metadata scope: the exact policy names the actor and office Colleges. There is no Student-wide source enumeration or professional-source route. GET/POST/PUT/PATCH on any invented source/body/export operation remains unavailable; frontend contract generation cannot create authority.

## Audit

The five bounded actions in `audit/actions.py` are `counseling.continuity.requested/approved/declined/cancelled/revoked`. `continuity_services` calls the existing synchronous `record_event` inside the same atomic transaction as the transition. Actor context must match the locked acting identity; HTTP mutations supply the request's AuditContext. Target is the Grant UUID. Metadata explicitly includes Student/receiver UUID, kind, bounded reason code, resulting version, interval, opaque policy/evidence reference and the exact scope snapshot digest. No raw request/response, narrative, score, token, key or ciphertext enters Audit. Existing Audit append-only application behavior and curated-feed allowlists remain unchanged; no new raw audit browser or notification event is added.

Required audit failure rolls back request/Scope insertion and every transition. Repeated identical current-version decisions produce neither a second state change nor duplicate event. Audit remains accountability evidence, not a claim that an approver read professional content. New action codes do not activate email, Push, realtime or in-app delivery. CONT-3 must separately approve any concrete recipients and copy before adding consumers.
