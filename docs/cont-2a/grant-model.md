# Grant persistence and immutable selection

The existing Counseling Django app registers `CounselorCaseContinuityGrant` and `CounselorCaseContinuityScope` from `continuity_models.py` through `models.py`. There is no new application or parallel permission store.

The UUID Grant protects Student, receiver, requester, decision/revocation actors and nullable original Counselor with `PROTECT` relationships. Original Counselor is historical provenance and may be absent for unexpected absence; it never becomes a primary-Counselor assignment. Fields record coverage kind, bounded reason, requested timestamp, explicit start/expiry, persisted decision, paired decision actor/time, paired revocation actor/time/reason, positive version, policy version/evidence/digest, affiliation marker, sealed snapshot digest, actor-scoped request-intent UUID and creation/update timestamps. No confidential free text or ciphertext belongs to this model.

Coverage kinds are `PLANNED_HANDOFF` and `TEMPORARY_COVERAGE`. Technical reason categories are `PLANNED_ABSENCE`, `UNEXPECTED_ABSENCE`, `TEMPORARY_SUPPORT`; the policy provider must explicitly approve a subset. Revocation codes are `COVERAGE_ENDED`, `AUTHORITY_CHANGED`, `REQUEST_WITHDRAWN`. These enums are representational bounds, not a claim of institutional acceptance.

Persisted transitions are REQUESTED → APPROVED / DECLINED / CANCELLED and APPROVED → REVOKED. Decision actor/time records approval, decline or cancellation; revocation retains the original approval identity/time and adds its own actor/time. No update, extension, receiver substitution or renewal-in-place API exists. New material intent requires a new request and independent approval.

Scope rows contain stable UUID, protected Grant, exact source UUID, typed kind/projection, structural revision and creation time. Only these pairs exist:

| Kind | Fixed projection identifier | Structural validation |
| --- | --- | --- |
| ENCOUNTER | ENCOUNTER_METADATA_V1 | Exact Student, historical Counselor if specified, existing assigned-author relationship or explicitly policy-approved office requester; `updated_at` marker |
| ROUTINE_EVALUATION | FINALIZED_EVALUATION_V1 | Same identity checks; submitted Intake, finalized Evaluation, correctly matched linked Encounter; SHA-256 over Routine and linked Encounter update timestamps |

`continuity_sources.py` contains narrowly bounded structural selectors using `.only()` and no ciphertext fields. They return revision markers, never source bodies or enumerated history. Request and approval validate these selectors. Office metadata selection is denied without approved policy. Referral/Follow-Up projections are deferred because their source-specific minimum disclosure remains unresolved. Student Session Summary, Intake, Inventory, assessments, media/transcripts, messages, credentials and exports are unrepresentable scope kinds.

A sorted snapshot seals Student, original/receiver/requester identities, purpose, interval, policy/evidence, affiliation and exact kind/UUID/projection/revision rows. Datetimes normalize to UTC so equivalent offsets have the same binding. Approval and metadata recheck the seal. Service/API users cannot append or change scope; tests simulate privileged direct-ORM corruption and verify subsequent metadata/approval fails closed. This is application integrity, not a claim of tamper resistance against a database owner capable of rewriting both rows and digests.

Additive `counseling/migrations/0003_case_continuity_foundation.py` is registered in `common/canonical_migrations.json`. Baselines and CONT-1B migrations are unchanged. PostgreSQL enforces required non-null identities, valid enums, positive versions, `isfinite(start/expiry)`, ordered interval, decision/revocation metadata consistency, non-empty policy/snapshot evidence, unique `(requester,request_id)`, unique `(grant,kind,source_id,projection)`, fixed kind/projection pairs and non-empty revisions. Indexes cover overlap, requester and receiver ordering. Cross-row eligibility and immutable lifecycle rules belong to the atomic services. No migration provisions policy or grants capabilities automatically.

Fresh install, existing-graph upgrade preserving source/identity/Audit rows, model/graph agreement, declared PostgreSQL constraints and empty-foundation rollback/reapply are validated. Rollback rehearsal does not authorize removal of retained grants; preserve their provenance and audit evidence under an approved recovery procedure.
