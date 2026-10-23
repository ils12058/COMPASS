# Candidate and dependency manifest

Fetched `integration/ux15-modernization`, `staging`, and `main` before creating an isolated managed worktree. Integration matched the supplied last verified SHA exactly. Runtime source tested: **`33d645db7fb5599fb916bac36c691539ec5aa675`**, plus the CONT-4 test/documentation diff identified by the PR head. No application fix was needed by the completed checks. Publication must recheck upstream drift.

| Prerequisite | Verified merged commit | Implementation commit |
| --- | --- | --- |
| [#314 CONT-0](https://github.com/ils12058/COMPASS/pull/314) | `5fcc3fe7ce2f9b07486c353fd662cc765c1f6f4f` | `06e8c7913c58c143790fbf9f4caac648366436be` |
| [#315 CONT-1A](https://github.com/ils12058/COMPASS/pull/315) | `0ba5024a8468b3e27b2b1b3723cf431bf0390f61` | `44e7eb6f50c9965b0a401959df31facdf61a56ec` |
| [#316 CONT-1B](https://github.com/ils12058/COMPASS/pull/316) | `1cdad9dd9378b1307140ba92a1023ed0e68a720f` | `44a7790a7bc29517efc1a3bdd49433a2cbf3a322` |
| [#317 CONT-2A](https://github.com/ils12058/COMPASS/pull/317) | `7afd4a41fe0a02b9723b5b4d22036beaef86f514` | `5c39292c342e84d3f8ecdd4f2143f9111d4471d3` |
| [#318 CONT-2B](https://github.com/ils12058/COMPASS/pull/318) | `dedf1a649c8adb4f8a5508a513d8bf0dd994fa1d` | `2d2e9ad6642c61a2df4463fd1fdc11eaa34f1e37` |
| [#319 CONT-3](https://github.com/ils12058/COMPASS/pull/319) | `33d645db7fb5599fb916bac36c691539ec5aa675` | `c88b2331f0c506230c8413fb938e9e0454aebaeb` |

Git ancestry and merged implementation files, rather than report assertions alone, establish presence. Initial remote snapshots: `staging=0a843dae20c01984d0fb9aa46d5eef34102ab386`; `main=1a9933535a0b8c0cbd7764c35f301e8402f48375`. These are observations, not deployment claims. Machine-readable hashes, migration leaves and exact operation IDs are in [static manifest](evidence/static-manifest.json).

Migration lineage is additive: canonical baselines → `accounts.0002_student_session_summary_capabilities` → `counseling.0002_student_session_summary_contract` → `counseling.0003_case_continuity_foundation` → `counseling.0004_counselor_handoff_summary`. The Counseling cutover also depends on the Notification baseline. The canonical registry is `be/compass/common/canonical_migrations.json`. No migration is edited, faked or squashed.

The backend owns `contracts/openapi.json`; Orval owns ignored `fe/src/lib/api/generated/`. The continuity prefix is `/api/v1/counseling/continuity-grants`: list/request; exact Grant metadata; approve/decline/cancel/revoke; selected Encounter metadata and Routine Evaluation GETs; workflow configuration/selection; Handoff metadata/author/submitted GETs, draft PUT and submit POST. The manifest enumerates every method and operation ID. There is no generic arbitrary-resource or history/export operation.

Capabilities: `counseling.continuity.view/request/approve/revoke/read_selected`, plus `counseling.handoff.manage_own/read_received`. These have no role/designation defaults; dependency closure and exact role/relationship checks still apply. Student communication uses the independent `student_session_summaries.view_self/view_assigned/manage_assigned` family.

Frontend routes: `/portal/counseling/coverage`, `/portal/counseling/coverage/[grantId]`, author tools on `/portal/counseling/encounters/[encounterId]`, and `/portal/counseling/student-session-summaries/[summaryId]`. The removed Shared Summary and Context summary-history contracts have no aliases.

Active configuration names (source inspection, not live values): required `STUDENT_SESSION_SUMMARY_ENCRYPTION_KEYS[_FILE]` and `ROUTINE_INTERVIEW_ENCRYPTION_KEYS[_FILE]`; optional inert-startup `COUNSELOR_HANDOFF_SUMMARY_ENCRYPTION_KEYS[_FILE]`. Handoff uses source `counselor_handoff_summary_encryption_keys`, web-only. All supplied rings are independently validated against the existing purpose/application secrets. File-backed configuration is parsed through `compass.common.config`; deployment inventory and Compose determine mount custody.

Runtime dependencies: PostgreSQL READ COMMITTED and supported row/table/advisory locks; synchronized identity policy; exact schema/backend/frontend/OpenAPI versions; protected purpose keys and retained backup keys; opaque session/CSRF; Redis and compatible worker/Beat/notification consumers; maintenance and Summary cutover/recovery procedures. No worker implements Grant effectiveness or expiry. Real policy publication/storage, secret custody, environment classification and institutional approvals remain separate blockers.
