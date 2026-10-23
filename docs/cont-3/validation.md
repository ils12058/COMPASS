# Executed validation and limits

Verified starting integration SHA `dedf1a649c8adb4f8a5508a513d8bf0dd994fa1d`. Execution used the isolated CONT-3 worktree, a dedicated temporary loopback PostgreSQL 17.11 cluster and Redis, ephemeral synthetic keys/users/records and explicit synthetic policy providers. Real migrations installed into an empty scratch database; no SQLite, mocked database locks, `--nomigrations`, live data or deployed environment was used. Final implementation SHA and actual hosted checks are on the PR.

## Backend

Final coherent focused run: **630 unique cases passed in 373.13 seconds**, with one existing Ninja tuple-response deprecation warning in an ordinary Routine test. Distinct `(classname, name)` JUnit identities confirm the count; repeated exploratory/repair executions are not added. This is a focused security/domain regression selection, not the whole backend suite.

| File/group | Unique passed cases |
| --- | ---: |
| Handoff domain/HTTP/privacy/policy | 101 |
| Real Handoff concurrency | 14 |
| Handoff configuration/key separation | 19 |
| Handoff constraints/populated migration rehearsal | 5 |
| CONT-2A lifecycle | 116 |
| CONT-2B selected access / real release concurrency | 106 / 32 |
| Continuity wire contracts | 3 |
| Runtime-secret inventory / Compose | 89 / 2 |
| Canonical baseline / protected-floor upgrade | 5 / 1 |
| Account Management / capability dependencies | 25 / 12 |
| Counseling Context | 30 |
| Student Session Summary ordinary / contract / selected encryption boundaries | 7 / 5 / 13 |
| Routine ordinary / selected encryption boundaries | 24 / 2 |
| Appointment management scope | 13 |
| Selected Follow-Up / E-Counseling authority boundaries | 4 / 2 |

The new 101-case file covers planned/requested/scheduled/active/expired/revoked author/receiver/approver separation, absent original, independent backup/no-backup cases, exact office selection, default/missing/changed/expired/unsupported policies, current affiliation/role/capability/session changes, no-decrypt denials, content-free Audit rollback/final expiry, immutability/idempotency/version conflicts, direct HTTP/CSRF/no-store, no Student disclosure/Notification intents, wrong bindings/swapped tokens/corruption/legacy envelopes, strict text, independent keyring and verified rotation. Body reads use only the Handoff decryptor; selection uses structural source helpers, never general detail trimming or Intake/Evaluation body reads.

Fourteen concurrency cases use independent real PostgreSQL connections/threads and observed lock waits: receive/submit before waiting revoke/deactivation/ciphertext writers; writer-first Grant/User/Handoff/policy conflicts; simultaneous draft writes/submission; policy publication fence; expiry after an actual User-row wait. The expiry test controls backend time after the real lock wait; it is not an assertion that wall time alone advanced by a specific duration. Existing CONT-2B cases retain the ten authority-relation/missing-row phantom/source-order proofs. Connections close explicitly. Local correctness is not a production contention benchmark.

The coherent selection runs the full new Handoff/config/concurrency/migration files, runtime-secret and Compose files, canonical/postbaseline files, CONT-2A/B/contract files, Account/capability, Context, Summary ordinary/contract, Routine ordinary and Appointment scope files. Selected existing nodes cover Summary exact-text/legacy binding/denied actors/removed Context endpoint; Routine record/section binding and denied actor/draft Intake; Follow-Up source classification/Student/actor/capability/GSS boundaries; E-Counseling blanket-capability denial and read-only relationship workspace.

Reproduce with the project Python environment/test settings against separately provisioned local empty services: `python -m pytest -q <the above tests/... files and node groups> --junitxml=<local report>`. The final local report is `cont3-final.xml`; its full target list is `cont3-final-targets.txt` in the session temporary directory. Neither artifact is a deployed record or institutional approval.

## Migration and configuration evidence

Fresh PostgreSQL installation, test-database initialization, populated current integration `counseling.0003` → new `0004`, disposable rollback/reapply and protected historical references/constraints passed. Existing Grant and Encounter fields/rows remain identical in the new populated rehearsal. A repaired existing upgrade rehearsal now preserves the irreversible CONT-1B `accounts.0002` + `counseling.0002` dependency unit while reversing later additions. Its earlier attempt to reverse the Summary cutover failed as intended by that historical migration guard; the fix changes the rehearsal target, not any migration or guard. Targeted repair passed, then the final coherent 630-case run passed.

`manage.py check --database default` and `makemigrations --check --dry-run` pass; no ungenerated model changes. All 104 existing migration/historical CONT-document files are byte-identical to integration. Canonical baseline hashes are unchanged, with exactly one new registered additive migration. A disposable reversal drops the new Handoff table; it is not a safe retained-data live rollback.

Nineteen direct settings tests verify absent/invalid/duplicate rings, protected `_FILE` configuration, direct/file conflict, and separation from all 14 existing application/purpose secrets. Inventory tests use temporary synthetic source files and metadata-only preflight. Both local/staging Compose contracts render without a Docker daemon; web-only custody and worker/Beat blank overrides are checked. No key was provisioned or live configuration inspected.

## Contracts, static and frontend

- Database-connection-blocked OpenAPI export and `--check`: passed. Exactly seven new workflow/Handoff paths. All existing continuity/selected-source paths and DTOs remain identical. The only existing schema/path change advertises the two new no-default capability codes through `CapabilityCode` and Account override parameter enumeration.
- Frozen offline frontend installation, Orval generation, TypeScript, ESLint and production build: passed. Build produces 96 static pages plus dynamic routes, including coverage detail. Generated clients remain generated/ignored; no hand edits or committed generated output. Build-only `next-env.d.ts` churn is restored before publication.
- **47 focused frontend unit cases passed**: 14 new field-projection/cancellation-generation cases plus existing Context/Encounter/account-ownership/portal regressions. No new body storage or server-state framework.
- The final production-browser evidence below includes confirmation/version and stale-draft checks. Fixtures mock API interactions and block outbound provider/live requests; they are separate from real backend authorization proof.
- Backend Ruff check/format passed (823 files), dependency lock check/compile checks and `git diff --check` passed. CI planner: **38 tests passed**, separately counted; **185 test files** bundled exactly once across six regression shards. New measured weights: Handoff 61.2s, concurrency 10.1s, configuration 0.1s, migrations 4.0s. Existing weights are preserved.

## Browser evidence

**41/41 production-browser scenarios passed in Chromium and 41/41 in WebKit (82 engine/scenario outcomes)** against the final production build. The same 41 scenarios run in each engine, so they are not 82 distinct business scenarios. Final local reports/screenshots: `cont3-final-browsers/chromium/case-coverage/results.json` and `cont3-final-browsers/webkit/case-coverage/results.json` under the session temporary directory. Earlier repair executions are not added to these counts. The final guards verify that background server-version drift closes an open confirmation without mutation, and a stale own-draft save retains unsaved input until deliberate saved-version review.

Coverage scenarios include workspace navigation/empty/default denial, contextual exact request/form validation/confirmation, planned/unexpected absence, approval/decline/cancel/revoke/self-approval hiding, 409 with no replay, scheduled→active, expiry/revocation, selected Encounter and allowlisted Evaluation omission/null/empty values, optional draft/submit/read-only/absent Handoff, approver no body fetch, late response, offline/reconnect, hidden tab, changed policy, account switch/logout, no persistent body storage, mobile/desktop, keyboard/Escape/return focus, 200% CSS zoom, long wrapping and exact-scope phone confirmation. Real-device and assistive-technology/institutional UAT are not claimed.

## Remaining limits

All three production providers still return None. No institutional policy, consent/basis, delegation, retention/correction/acknowledgment rule, notification recipient/channel or real key custody/recovery is approved by these tests. No Notification producer is added; positive Handoff operations leave Notification rows unchanged. Tab hints invalidate only and cannot authorize. Remote changes require the next backend check/bounded polling; already released content cannot be recalled.

Hosted CI must be read from the actual PR rollup and may not trigger for this integration target. Local validation is not hosted-CI, merge, deployment or live activation proof. No SSH, DigitalOcean operation, real secret read/provisioning, deployed migration/reset, outbound notice, deployment or automatic merge is performed. See [release gates](release-gates.md).
