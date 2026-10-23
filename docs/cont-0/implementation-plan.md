# Implementation slices and acceptance gates

This plan is proposed work, not completed features. Sequence: **CONT-1A → CONT-1B → CONT-2A → CONT-2B → CONT-3 → CONT-4**. Governance work can proceed alongside early slices. Keep one cohesive PR per slice unless source adapters genuinely require separate domain review; do not create many ceremonial microslices. Every PR targets the agreed integration branch and requires explicit merge/deployment authorization independently.

## CONT-1A — correct the Student-summary audience

| Requirement | Implementation specification |
| --- | --- |
| Objective | Remove cross-author publication disclosure through Context; retain owning Student and original author lifecycle. |
| Exact likely owners | `be/compass/counseling/{context_services,context_api,api,shared_summaries}.py`; primarily remove Context projection/route. `fe/src/features/counseling/counseling-workspace.tsx`, Encounter detail link integration; `contracts/openapi.json`; Context/summary/encryption tests and affected frontend tests. |
| Dependencies | CONT-0 reviewed; explicitly requested audience rule. No continuity policy/grant dependency. |
| Database impact | None. Preserve all draft/published rows, UUIDs, author/Encounter, text, publication and timestamps. |
| API impact | Remove Context summary endpoint/schema/section/operation; ordinary old-named author/self summary endpoints remain until 1B. No forwarding alias. |
| Frontend impact | Remove cross-author history tab/query/render/cache keys; preserve author work on Encounter detail and Student list/detail; provide safe current Encounter link. Regenerate clients, never hand-edit generated output. |
| Authorization | No Context/Appointment/College-based cross-author Student Summary read; old direct URL denies before decrypt. Own author/Student checks intact. |
| Encryption | Same keyring/binding/payload; negative tests spy on decrypt calls. No re-encryption. |
| Required tests | Existing Context, shared summary and applicable encryption authorization cases; replace cross-author-positive expectation. Add current provider/direct modes/Head provider/cross-College, revoked capability, other Student/draft, old URL, no section, cache removal; preserve Context projections and own-record-after-expiry. Frontend affected tests/typecheck and focused browser view. |
| Acceptance | Both author and Student positives pass; B cannot obtain A's body through any active route; contract has no Context Summary operation; current publication and encryption integrity unchanged. |
| Release blockers | Any remaining alternate disclosure path, broken author workflow, changed ciphertext/publication, stale protected body after denied refresh. |
| PR boundary / rollback | One focused confidentiality PR. Reverting it would restore the audience mismatch: use forward fixes or suspend the affected surface rather than silently reverting protection. No DB rollback needed. |

Full field-level task in [summary audit](student-session-summary-audit.md). Recommended immediate next task is this slice only.

## CONT-1B — one Student Session Summary contract

| Requirement | Implementation specification |
| --- | --- |
| Objective | Complete active-code/model/API/event/capability/config/crypto/UI naming cutover with no permanent aliases. |
| Exact likely owners | `counseling/models.py`, renamed summary service/content/rotation modules, `accounts/{policy,bootstrap}.py`, `audit/actions.py`, `notifications/{policy,email_links,push_policy}.py`, paired templates, config settings/examples, runtime-secret inventory/Compose contract, staging_seed modules; frontend files/route/notification targets; OpenAPI; CI file selections/durations; additive migrations and registry. Use [file inventory](rename-inventory.csv). |
| Dependencies | 1A; retention/disposability decision D16, new key custody D17, reviewed Notification/capability transformation and rehearsed cutover. Preparing the PR does not authorize deployed execution. |
| Database impact | Additive RenameModel/reverse relation/constraint changes on immutable canonical baseline. Stored capability codes/grants/overrides transform or scoped retirement; Notification strings transform or authorized synthetic purge. B+C summary reset preferred only when disposable confirmed; A otherwise. Never rewrite immutable Audit. |
| API impact | New canonical author/self endpoints, operation/schema/error IDs and Notification target enum. Old resource routes removed. Backend contract export/check and generated client regeneration mandatory. |
| Frontend impact | Student Session Summary copy/components/route/query keys/capabilities, author publication confirmation, notification target/link fixtures, navigation and command palette. One active vocabulary. |
| Authorization | Preserve 1A audience and capability REVOKE/expiry when renaming persisted codes. No dual capability acceptance. |
| Encryption | New dedicated setting/mount/binding; reset+regenerate or exact offline old→new envelope converter. Rotation command only rewraps keys and cannot rebind. Test failure paths and new ring separation. |
| Required tests | Fresh PostgreSQL install + canonical populated A/B rehearsal; model/graph consistency and baseline hashes; test DB creation; pending delivery/unique collision handling; capability rename preserves REVOKE; old endpoints/settings/modules absent; new codec roundtrip/tamper/rotation; seeder deterministic verify; OpenAPI and frontend typecheck/build as appropriate. |
| Acceptance | One model/table/route/capability/setting contract; new payloads readable, retained data matches or explicitly disposable loss accepted; historical Audit intact; fresh and chosen cutover paths pass; no old active fallbacks. |
| Release blockers | Unverified disposable status, lost key recovery, unreadable retained token, orphaned source/delivery/capability state, old consumer still running, baseline edited, future graph untested. |
| PR boundary / rollback | One coordinated rename/migration PR, no new grants/source sharing. Follow [cutover checklist](encryption-and-cutover.md); rollback requires a consistent image/schema/data/keyring/manifest/frontend unit, not code alone. Reset execution is a separately authorized task. |

## CONT-2A — continuity foundation, no professional reads

| Requirement | Implementation specification |
| --- | --- |
| Objective | Persist single-Student/single-receiver requests, exact scopes, approval decision, finite interval/version and revocation; expose safe metadata only. |
| Exact likely owners | New focused `counseling/continuity_*` modules/models imported by current domain, `accounts/policy.py`, `organization` approver-scope integration only as necessary, Audit actions/metadata, API router and generated contract; tests for new state/ACL. |
| Dependencies | 1B; D01–D05/D07/D10/D12/D13 authority, interval, delegation and overlap decisions for implemented paths. If Acting scope is unresolved, deny it and record blocker; do not invent a role. |
| Database impact | Additive Grant+Scope tables/checks/indexes and capability sync, optional narrowly scoped delegation evidence only if confirmed necessary. No source ownership writes. |
| API impact | Proposed metadata list/detail/request/approve/decline/revoke/cancel with exact expected_version. Reviewer endpoints do not decrypt sources/Handoff. No content read merely because grant exists. |
| Frontend impact | Generated contracts/access helpers may prepare metadata integration; full coverage/approval UI remains 3. No hidden activation. |
| Authorization | Existing effective capability engine + active Counselor + receiver/requester/approver relation and organizational predicate. Default no self-approval; exact selected scopes, deny unknown/forbidden types, live expiry. |
| Encryption | No confidential free-text reason initially. Structural reason/evidence codes only. No Handoff payload or keyring yet. |
| Required tests | State machine; before/start/exact end/revoked, incorrect Student/receiver, IT/GSS/inactive/revoked cap, Head/Acting/separation, concurrent approval/revoke/overlap, changed scope after approval, metadata no decrypt, Audit failures rollback, model/graph/fresh DB and OpenAPI. Real PostgreSQL transaction tests for locks. |
| Acceptance | Foundation never returns professional bodies; denied roles fail despite arbitrary capability overrides; finite server-enforced time/revocation; concurrency/audit proven; no existing Context behavior changes. |
| Release blockers | Missing policy bounds/scope, self-approval loophole, stale cached approval, unsynchronized identity changes, implicit source entitlement. |
| PR boundary / rollback | One foundation PR. New tables can remain inert when routes disabled by a forward code change; revoke active grants before removing readers in later rollback. No source data rollback needed. No new feature flag requested. |

## CONT-2B — selected confidential source reads

| Requirement | Implementation specification |
| --- | --- |
| Objective | Allow only institutionally approved source kinds/projections through per-read grant + source-domain decisions. |
| Exact likely owners | `counseling/continuity_access.py` and source adapters; `routine_interviews` finalized Evaluation read; `referrals` and `guidance_followups` only approved projections. Existing ordinary assigned getters/mutations retain predicates. Minimal operational context serializers, safe headers/audit, new tests/contracts. |
| Dependencies | 2A; D05/D06/D08/D10/D13/D14/D18 and technical approval of each adapter. Start Encounter metadata + selected finalized Evaluation; add Referral/Follow-Up only when justified. |
| Database impact | Scope source-revision/projection fields if not finalized in 2A; no duplicate source bodies, author changes or source mutations. |
| API impact | Typed selected-source GETs under a grant; no arbitrary resource router, export or Student-wide history. Concealed denial; source-specific corruption safe error; private/no-store for success/errors. |
| Frontend impact | Generated selected-read operations and view-only components; full receiving workflow in 3. No body fetch in approval lists. |
| Authorization | All ten requested checks plus source lifecycle/revision. Approval-time metadata selector and read-time policy independent. Role/capability/expiry/revocation/Student/UUID/type/receiver evaluated every read. |
| Encryption | Reuse source adapter and existing source keyring only after authorization; no copied encrypted clinical store; no decryption on denial. |
| Required tests | Full actor/source negative matrix, changed/wrong Student/UUID/projection, excluded kinds, corrupted ciphertext, stale source revision, read/expire/revoke/deactivate races, readonly mutations/export denied, Audit failure, no sensitive logs/hints/Notification. Validate ordinary author/Student paths and Context unchanged. |
| Acceptance | Receiver sees exactly approved finalized fields/IDs during effective grant; all others deny; no generic global bypass; source write rules unchanged. |
| Release blockers | Category/basis unsigned, wildcard source enumeration, Intake/full Inventory/assessment/media/message leakage, source-manage checks weakened, missing access audit/race tests. |
| PR boundary / rollback | One bounded source integration PR or at most distinct high-sensitivity domain reviews where necessary. Forward-remove adapters/revoke grants to stop new disclosure; previously viewed data cannot be recalled. |

## CONT-3 — handoff, planned/unplanned coverage and UI

| Requirement | Implementation specification |
| --- | --- |
| Objective | Integrate focused request/approval/receiver workflows and optional encrypted professional Handoff; work without original Counselor participation. |
| Exact likely owners | `counseling` Handoff model/service/content/API/rotation; new independent settings/runtime-secret inventory contract (deployment separate); frontend Counseling coverage pages/components, existing Routine/Encounter contextual links; Notifications policy/currentness/templates/targets; Audit. |
| Dependencies | 2A/B; D02/03/08/09/11/14/15/17/18 and source-selection procedure. |
| Database impact | Add Handoff model with immutable grant/Student/author/recipient, ciphertext, submission and optional receipt timestamps; additive graph. Notification events/targets and any safe receipt state. |
| API impact | Author-only draft create/update, explicit submit, receiver read under effective grant, optional acknowledge, metadata review/revoke. No Student publication or approval-content read. |
| Frontend impact | My case coverage, requests, pending approvals, active/expiring/expired/revoked views, explicit scope/receiver/expiry, read-only source review and distinct Handoff. Shared controls, mobile/keyboard/focus/stale states. Student notice only once basis/process approved. |
| Authorization | Author qualification distinct from receiver/approver; grant validity on receiver reads; draft author only, submitted immutable; no summary prerequisite; no impersonation/self-approval. |
| Encryption | New independent Handoff keyring and bound JSON; all identity bindings checked, separation/rotation/provisioning/recovery verified. No Student Summary key reuse or generic audience flag. |
| Required tests | Planned/unplanned/no-original flows, author/receiver/approver separation, swap/wrong key/binding, draft/submission/ack/expiry, currentness after revoke, generic channel bodies, stale deep links, browser cache/authority clearing, mobile/200%/keyboard/dialog focus, Account switch. |
| Acceptance | Actual useful coverage without unrestricted history or required Handoff; approver sees metadata only; Student never sees professional content; external messages contain no confidential details; independent scheduling/Follow-Up constraints remain. |
| Release blockers | Unapproved notice/basis/retention, no backup approval path, undefined Handoff correction/post-expiry rights, mixed audience, unavailable independent key custody, inaccessible consequential UI. |
| PR boundary / rollback | One cohesive workflow/Handoff PR; separate live secret/cutover execution. Revoke grants and stop new reads/events; preserve ciphertext/audit and custody, do not erase professional handoffs by UI rollback. |

## CONT-4 — final security and institutional release validation

| Requirement | Implementation specification |
| --- | --- |
| Objective | Prove the final actor/source/time/cutover contracts with controlled synthetic integration/UAT. |
| Exact likely owners | Existing/new backend tests, PostgreSQL concurrency tests, affected frontend/browser tests, synthetic fixture/seeder verification and documentation. Domain/security/GCO review evidence, not a broad redesign. |
| Dependencies | 1A–3, approved institutional decision register, exact candidate and test lineage. |
| Database impact | No unplanned model changes. Test fresh creation and approved canonical upgrade/reset on disposable isolated databases; actual staging reset/deployment remains separately scoped. |
| API/frontend impact | Verify one canonical contract, no aliases, generated clients synchronized, direct API denials, all user workflows and stale states. Fix defects in their owning slice without widening access. |
| Authorization | Complete matrix incl. cross-College, former/inactive Counselor, unsupported role with capabilities, no self-approval, scope/type/Student tampering, expiry/revocation and identity races. |
| Encryption | Summary cutover and new Handoff integrity, independent keyrings, wrong bindings, rotation, recovery, no plaintext/log/channel disclosure. |
| Required tests | T01–T24, historical author preservation, duplicate grants, fresh/install/upgrade/test DB, fixtures and Notification queues, endpoint/capability/config old-name absence, browser old links/cache, safe exports, mobile/keyboard; controlled synthetic GCO UAT. Relevant existing domain regressions, not indiscriminate whole-repository reruns. |
| Acceptance | Exact-head evidence and signed policy/UAT; every high-risk item resolved or explicitly accepted by authorized owner; all exclusion and negative tests pass; deployment/activation request is separately reviewable. |
| Release blockers | Any unresolved high risk, untested migration/reset, unspecified policy or only mocked concurrency evidence, confidential content in channels, real-data/UAT safety unconfirmed. |
| PR boundary / rollback | One validation/hardening PR with precise defect scope. Keep implementation/test/CI/merge/deployment/live proof distinct. No automatic merge or deploy; release rollback follows reviewed consistent-state cutover unit. |

## Focused execution guidance

Inspect actual test names before selecting. Existing candidates are `test_counseling_context.py`, `test_shared_summaries.py`, `test_counseling_shared_summary_encryption.py`, `test_routine_interviews.py`, `test_routine_encounter_linking.py`, `test_appointment_management_scope.py`, `test_guidance_followups.py`, `test_assessment_records.py`, `test_referrals.py`, Inventory/Support and E-Counseling/media suites. Use isolated synthetic PostgreSQL for required DB scenarios; no deployed data/keys. CONT-0's executed subset is narrower and fully recorded in [validation](validation.md).

Each implementation PR should state changed behavior, database/API/encryption impact, exact focused checks, policy dependencies and rollback boundary. Keep the confidentiality correction separate from the high-risk cryptographic rename and both separate from new professional sharing.
