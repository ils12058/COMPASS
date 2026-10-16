# CANON-1C — Staging Dataset v1 verification

All runs used disposable local containers (PostgreSQL 17.11 on `127.0.0.1:55432`, Redis 8.10.1 on
`127.0.0.1:56379`), `APP_ENV=local-staging`, `TIME_ZONE=Asia/Manila`, and throwaway Fernet keyrings
kept in the session scratch directory (never committed). No live, shared or user database, Redis,
object store or provider was used.

## Clean rehearsal (fresh database)

Transcript: [evidence/rehearsal-clean.txt](evidence/rehearsal-clean.txt).

| Step | Result |
| --- | --- |
| `migrate` on an empty database | 41 migrations applied |
| `check --database default` | no issues (history guard clean) |
| Four synchronizers | identity policy, Counseling Service, 8 form families / 13 revisions, 6 campuses / 10 colleges / 38 programs |
| `seed` (first run, preparation date 2026-10-16) | completed in 32 s; 113 accounts, 100 Students |
| `seed` (rerun) | **0 created, 399 reused** |
| `verify` (strict) | **PASSED** — 1,447 checks, 0 failures, 0 warnings |
| `report` | six documents written to [`uat/`](uat/) |

Verification sections on the clean rehearsal:

| Section | Passed | Failed | Warnings |
| --- | ---: | ---: | ---: |
| Schema readiness | 5 | 0 | 0 |
| Canonical configuration | 57 | 0 | 0 |
| Account readiness | 1,085 | 0 | 0 |
| Organization routing | 12 | 0 | 0 |
| Scenario initial states | 101 | 0 | 0 |
| Workflow integrity | 40 | 0 | 0 |
| Privacy and security | 142 | 0 | 0 |
| External side effects | 5 | 0 | 0 |

`verify` runs in a PostgreSQL `READ ONLY` transaction (asserted by
`test_verification_runs_in_a_read_only_transaction`: the first statement after `BEGIN` is
`SET TRANSACTION READ ONLY` and no `INSERT`/`UPDATE`/`DELETE` is issued).

## Findings during verification design

| Finding | Resolution |
| --- | --- |
| The unassigned Counselor's Work Queue was not empty. | Not a defect: `good_moral/work.py` documents Good Moral preparation/issuance as office-wide. The check now requires only office-wide kinds for a Counselor without responsibility; scenario wording (NEG-04, CNS-WQ-01) states the design. |
| Default credential issuance aborted on the onboarding account. | Fixed: default issuance covers UAT-ready credential accounts only; naming an onboarding or disabled account is refused. |
| A "reissue" for an account that never had a credential was audited as a reset. | Fixed: audited as `auth.password.initial_set` unless a usable password is being replaced. |
| Active-UAT verification failed a read-only scenario whose shared state another scenario legitimately consumes. | Fixed: states of accounts touched by any mutating scenario are warnings under `--allow-uat-changes`. |
| Seven current Students without an Inventory reported no year level. | Fixed: an explicit enrollment year level is part of each Student specification. |
| Several UAT-ready accounts had no Student-side scenario. | Fixed: 14 Student scenarios added; the manifest now refuses a UAT-ready account without a scenario. |

## Rerun preservation (simulated evaluator activity)

On the rehearsal database, an evaluator-style session cancelled `ar_03`'s Appointment, created a
Good Moral request as `ar_12`, and changed `ar_02`'s password; then `seed` ran again.

| Observation | Before rerun | After rerun |
| --- | --- | --- |
| `ar_03` Appointments | `["CANCELLED"]` | `["CANCELLED"]` (not re-booked) |
| `ar_12` Good Moral requests | 1 | 1 |
| `ar_02` password hash | unchanged prefix | identical |
| Items created by the rerun | — | 0 |

Strict `verify` then **failed visibly** (STU-APT-03, STU-GM-01, NEG-05 initial states and 2 email
intents created by the simulated actions). `verify --allow-uat-changes` **passed** with the same
items reported as "changed since seeding" warnings. The same behavior is covered by
`SeededDatasetTests.test_rerun_creates_nothing_and_preserves_evaluator_changes`.

## Credential issuance rehearsal

| Case | Result |
| --- | --- |
| Output path inside the repository | refused before any database work |
| Default issuance | 43 credentials (one participant already had a credential from an earlier reissue test), file mode `-rw-------`, header `account_key,institutional_id,email,role,temporary_password` |
| Same path again | refused ("already exists; never overwrite") |
| Rerun to a new path | 0 issued, 44 skipped, no file written |
| `--account onboarding` / `former_staff` | refused |
| `--reissue` without `--confirm-reissue` | refused |
| Restricted accounts named explicitly | issued (2) |

Automated (`test_credentials_are_distinct_hashed_protected_and_sign_in`): 44 distinct passwords of
24 characters; only PBKDF2 hashes stored; `check_password` succeeds; audit metadata never contains
a password; a Student signs in through `POST /api/v1/auth/login` with the issued credential and
gets a live session; reissue replaces the password and revokes that session; the source-tree and
existing-file refusals hold. Handoff files from the rehearsal stayed in the session scratch
directory and were not committed.

## Safety and isolation tests

`tests/test_staging_seed.py` — 38 tests (one shared seed in `setUpTestData`), all passing:

| Area | Coverage |
| --- | --- |
| Environment | Guard allowlist and opt-in matrix (10 cases); every mode refused for disabled live-staging, `production` and an unknown future mode with **zero queries** |
| Configuration and timeline | `STAGING_SEED_*` only; live-staging requires a bare domain; preparation-date window, future and lag refusals; Asia/Manila |
| Manifest | 100 Students (11/24/65), 13 staff, canonical roles, `STG-` identifiers, every UAT-ready account has a scenario, disabled ⇒ restricted, pending scenarios carry no checks |
| Lineage and conflicts | `DEMO-2026-` accounts refused; an identity conflict stops before any `STG-` account or Inventory |
| Concurrency | Holding the advisory lock from another connection makes `seed` refuse with nothing written |
| Seeded dataset | No account has a usable password; onboarding unverified; disabled accounts inactive; 86 CURRENT; strict verification passes; action-ready states exist through domain services |
| Side effects | Seeding with Daily, outbound HTTP and object storage patched to fail; no mail sent; no email/push intents; no E-Counseling room; in-app Notifications kept |
| Documents | Six documents; CSV columns and row order match the manifest; 100 Student rows; every account in the catalog; summary totals; blank assignment template limited to UAT-ready accounts; refuses to write after failed verification; secret scan |
| Command | `verify` and `report` modes end to end |

Related suites updated to the new package and passing: `test_exit_interview_opportunities.py`,
`test_feedback_confidential_content_encryption.py`, `test_graduate_tracer_confidential_content_encryption.py`,
`test_runtime_secrets.py`, `test_runtime_secrets_compose.py`.

## Not verified here

- A live-staging seed, email domain or mailbox; live Daily, object storage or push.
- Browser-level UAT walkthroughs of each scenario on a seeded database (scenario initial states
  are verified in the database; the browser regression suite uses synthetic fixtures).
- Broker contents during seeding: services enqueue harmless email-kick tasks on commit that find no
  delivery; no broker inspection was performed.
