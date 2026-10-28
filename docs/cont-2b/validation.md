# Executed validation

Verified base: `7afd4a41fe0a02b9723b5b4d22036beaef86f514` on `origin/integration/ux15-modernization`, fetched again before publication. Final implementation SHA and current hosted checks are recorded on the PR. Tests used only a dedicated temporary loopback PostgreSQL **17.11** cluster, dedicated Redis instance and synthetic users/records/policies/keys. Actual migrations installed into the empty scratch database; pytest did not use SQLite, mocked database locks or `--nomigrations`. No deployed database, real professional record, live key, SSH or deployment was accessed.

## Backend evidence

**399 unique PostgreSQL backend cases passed across three nonoverlapping final runs**, not one uninterrupted 399-case suite:

| Run | Result |
| --- | --- |
| Coherent selected-read/security/domain regression selection | 390 passed in 248.32s; one existing Ninja tuple-response deprecation warning in an ordinary Routine test |
| Additional Appointment-parent eligibility and durable outer-transaction cases | 8 passed in 9.07s |
| Exact half-open start/expiry boundary | 1 passed in 5.85s |

There were no runtime implementation changes between those three runs. The latter two add tests for supported Appointment parent facts, rejection inside an uncommitted outer transaction, and `starts_at <= now < expires_at`. A JUnit `(classname, name)` union confirms 399 distinct cases, including all 106 selected-access and all 32 real concurrency cases.

| Covered file/domain | Passed cases |
| --- | ---: |
| Selected access | 106 |
| Release concurrency | 32 |
| Existing CONT-2A | 116 |
| Continuity contracts | 3 |
| Canonical baseline | 5 |
| Account Management / capability dependencies | 25 / 12 |
| Counseling Context | 30 |
| Student Session Summary ordinary / contract / selected encryption boundaries | 7 / 5 / 13 |
| Routine ordinary / selected encryption boundaries | 24 / 2 |
| Appointment management scope | 13 |
| Selected Follow-Up / E-Counseling authority regressions | 4 / 2 |

The coherent run covered the complete files `test_continuity_access.py`, `test_continuity_release_concurrency.py`, `test_continuity.py`, `test_continuity_contract.py`, `test_canonical_baseline.py`, `test_capability_dependencies.py`, `test_account_management.py`, `test_counseling_context.py`, `test_student_session_summaries.py`, `test_student_session_summary_contract.py`, `test_routine_interviews.py` and `test_appointment_management_scope.py`. Additional selected node groups were:

- Summary encryption: exact-text/legacy binding, denied actors, removed Context endpoint (including corrupt Summary ciphertext).
- Routine encryption: record/section ciphertext binding and denied actor/draft Intake isolation.
- Follow-Up: source classification, Student/current actor matching, capability/deactivation/object scope, no GSS confidential source options.
- E-Counseling: no GSS/IT/Head blanket authority and read-only relationship-scoped workspace without provisioning.

Reproduction uses the repository's Python environment and test settings against separately provisioned empty local services: `python -m pytest -q <the above tests/... targets>`. For the additional coverage, run `tests/test_continuity_access.py::test_appointment_backed_source_lifecycle_is_independently_checked`, `::test_prepared_content_cannot_escape_an_outer_uncommitted_transaction` and `::test_selected_content_half_open_start_and_expiry_boundaries`. Running the current complete selected-access file includes those additions. Local final reports were `cont2b-final.xml`, `cont2b-additional.xml`, `cont2b-boundary.xml` in the session's temporary directory; they are execution evidence, not deployed artifacts.

The 32 concurrency cases use independent real PostgreSQL connections/threads and observed lock waits. They cover both reader/writer orderings, actual account/designation/override/affiliation/revocation services, all ten authority relations, missing-row REVOKE insertion, source-first/User inversion, policy invalidation fences, exact expiry after a real User wait, concurrent successful reads, Audit failure and guessed unrelated Grant contention. Thread connections explicitly close. See [release synchronization and limits](concurrency-and-release.md).

Denied recipients, Head/IT/GSS/Student/original-author actors, missing policies, changed policy/field manifests, lifecycle/source/scope tampering and expired/revoked sessions cannot obtain the protected body. Spies verify preauthorization denial does not decrypt. Evaluation success calls only the existing Evaluation section decryptor, with deliberately unreadable Intake left deferred; ciphertext corruption or binding/key unavailability returns safe 503. Audit failures and post-decryption/post-Audit expiry return no prepared body and commit no successful read event. API success/error/no-policy responses preserve `private, no-store`.

## Schema, static and client checks

- `python manage.py check --database default`: passed on scratch PostgreSQL.
- `python manage.py makemigrations --check --dry-run`: no changes detected. There are no model or migration changes; canonical migration files, baseline hash registry and CONT-1B/2A migrations remain byte-identical to the base.
- `ruff check .` and `ruff format --check .` from `be/`: passed; 812 Python files formatted. `git diff --check`: passed.
- Database-connection-blocked `export_openapi`, followed by `export_openapi --check`: passed. Structural comparison confirms every existing path and component schema remains identical. Exactly two selected GET paths and their new explicit DTOs are added; existing seven continuity metadata operations are unchanged.
- Real offline frozen frontend dependency installation, `pnpm api:generate` (Orval), `pnpm typecheck`, `pnpm lint` and `pnpm build`: passed. Generated API files remain generated/ignored; there are no handwritten frontend changes. Build-only `next-env.d.ts` route-type churn was restored to baseline. No new UI or browser/UAT claim is made.
- `python -m unittest discover -s .github/scripts -p test_backend_ci.py`: **38 planner tests passed**, counted separately from backend cases. `python .github/scripts/backend_ci.py verify`: **181 test files bundled exactly once across six regression shards**. The two new files are in Counseling's targeted bundle; measured JUnit weights are 55.3s for selected-access and 16.0s for concurrency. Existing weights are preserved.

This is focused security/domain validation, not a full backend-suite run or production contention benchmark. Hosted CI may not trigger on this integration target; inspect the PR's actual check rollup rather than treating local tests as hosted CI or deployment proof.

## Default denial and release limits

Both default policy providers still return None, with explicit contract/default-denial tests. No production policy provider, verified evidence repository, Handoff model, keyring, notice delivery or UI is activated. A typed evidence reference validates shape and binding; it cannot establish institutional sign-off. D01–D10 and relevant D13–D18, provider publication/invalidation/storage coordination, mixed-version deployment coordination and CONT-3 client behavior remain separately authorized prerequisites. See [CONT-3 handoff](cont-3-handoff.md).

Supported PostgreSQL DML synchronization is exercised; arbitrary privileged schema/SQL rewriting or an uncoordinated external provider is not claimed safe. Already committed responses may arrive after expiry/revocation and cannot be recalled. No live migration/reset, deployment, SSH, key provisioning, notification or merge was performed. The focused PR is opened against integration and left unmerged.
