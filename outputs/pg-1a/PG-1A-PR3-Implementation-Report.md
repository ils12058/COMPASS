# PG-1A PR 3 Readiness & Implementation Report: Final Disposition Decommission & Historical Ledger Protection

- **Date:** 2026-10-16
- **Repository:** `ils12058/COMPASS`
- **Base (`origin/staging`):** `926d5c27737d5adb44a9cc32c174d0ac219181dc` ("refactor(privacy): introduce code-owned retention oversight (PG-1A PR 2) (#245)")
- **Worktree:** `/Users/reynantlntno/Projects/COMPASS-PG-1A-PR3`
- **Branch:** `refactor/pg-1a-final-disposition-decommission`
- **Recommendation:** `PR 3 PREPARED — RUNTIME GATE BLOCKED`

---

## A. Baseline

| Item | Value |
| --- | --- |
| `origin/staging` SHA | `926d5c27737d5adb44a9cc32c174d0ac219181dc` |
| PG-1A PR 1 merge SHA (#244) | `5b67b550a315d71c14e38b4f86104b251a47e89c` |
| PG-1A PR 2 merge SHA (#245) | `926d5c27737d5adb44a9cc32c174d0ac219181dc` |
| Live-staging deployed SHA (`/api/v1/meta`) | `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee` (`built_at`: `2026-10-11T09:00:30Z`) |
| Undeployed commits on `origin/staging` since `0512e9ec` | 27 commits (`git log 0512e9ec..926d5c27`) |
| Implementation worktree | `/Users/reynantlntno/Projects/COMPASS-PG-1A-PR3` |
| Implementation branch | `refactor/pg-1a-final-disposition-decommission` |
| Referenced ADRs | ADR-011 (Append-only Audit Trail), ADR-045 / ADR-061 (Privacy Notices & DPO boundary), ADR-069 (Prior descriptive registry removal), ADR-072 (Retired operational retention engine), ADR-073 (Curated activity retrieval), ADR-084 (Graduate Tracer confidential encryption), ADR-092 (E-Counseling media governance v2), ADR-112 (Graduate Tracer graduation classification & anonymization invariant), ADR-114 (Decommission in-app records disposition), ADR-115 (Code-owned retention policy register and read-only oversight) |

---

## B. Deployment Readiness Audit

### 1. Required 12-Point Runtime Evidence Inventory (Verified 2026-10-16T12:32+08:00)

| # | Required Evidence | Evidence Source | Verified Result | Status |
| --- | --- | --- | --- | --- |
| 1 | Exact live-staging backend build SHA | `GET https://staging-api.compass-gco.com/api/v1/meta`; `gh run list --workflow=deploy-staging.yml` (run `38126810483`, `2026-10-11T09:00:21Z`) | `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee` (`built_at`: `2026-10-11T09:00:30Z`) | **BLOCKED** (27 commits behind `origin/staging`) |
| 2 | Exact Celery worker build SHA | `deploy-staging.yml` (`38126810483`) and `be/compose.staging.yaml:95-117` (single `COMPASS_IMAGE` shared by `web`, `worker`, `beat`) | `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee` (direct container inspection requires SSH host credentials) | **BLOCKED** (still running pre-PR 1 image) |
| 3 | Exact Celery Beat build SHA | `deploy-staging.yml` (`38126810483`) and `be/compose.staging.yaml:118-132` | `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee` | **BLOCKED** (still scheduling `retention-*` Beat entries) |
| 4 | Whether PR 1's tombstone implementation has been deployed | `git merge-base --is-ancestor 5b67b550 0512e9ec`; `deploy-staging.yml` run history | **No.** PR #244 (`5b67b550`) was merged on 2026-10-16 and has never been deployed to `live-staging`. | **BLOCKED** |
| 5 | Whether PR 2's read-only APIs and retired capabilities have been deployed | `GET https://staging-api.compass-gco.com/api/v1/privacy/retention/policies` (`HTTP 404`); `GET https://staging-api.compass-gco.com/api/v1/privacy/retention/rules` (`HTTP 401`) | **No.** PR #245 (`926d5c27`) has not been deployed; the new `/policies` route returns `404` on live staging while the retired `/rules` route still returns `401`. | **BLOCKED** |
| 6 | Whether all old disposition-executing worker instances have stopped | Live build `0512e9ec` contains #162 (`ed14b758`) and #189 (`63c7d22a`) | **No.** The live-staging worker is still running `0512e9ec`, which registers the destructive executors (`execute_disposition`, `discover_retention`, `recover_disposition`). | **BLOCKED** |
| 7 | Whether any disposition task is currently active | Requires authorized SSH operator access on the staging Droplet (`celery --app config inspect active`) | Not inspectable without staging host SSH access | **UNKNOWN** |
| 8 | Whether Redis contains queued, reserved, unacknowledged, delayed, or retryable legacy disposition messages | Requires authorized SSH operator access on the staging Droplet (`redis-cli -n 0 LRANGE celery 0 -1` and `HVALS unacked`) | Not inspectable without staging host SSH access | **UNKNOWN** |
| 9 | Whether there are active retention rules | Requires authorized operator execution of `python manage.py retention_decommission_status` on the staging Droplet | Not inspectable without staging DB access | **UNKNOWN** |
| 10 | Whether historical disposition cases have unresolved states | Requires authorized operator execution of `python manage.py retention_decommission_status` on the staging Droplet | Not inspectable without staging DB access | **UNKNOWN** |
| 11 | Whether E-Counseling custody-transfer cleanup is healthy | Requires staging DB and worker log diagnostics | Not inspectable without staging host access | **UNKNOWN** |
| 12 | Whether old deployment or rollback artifacts could reintroduce destructive task executors | `.github/workflows/deploy-staging.yml:321-330` (`$DEPLOY_PATH/.deploy.env` and `.deploy.previous.env`) | **Yes.** `.deploy.env` currently points to `0512e9ec` and `.deploy.previous.env` points to `0179c6eb` (run `38112793937`). Even after the first post-PR 1/PR 2 deploy, `.deploy.previous.env` will retain `0512e9ec` until a second post-decommission deploy overwrites it. | **BLOCKED** |

### 2. Official PG-1A Runbook Gate Evaluation (G1–G10)

| Gate | Definition | Evidence Source | Verification Date/Time | Verified Result | Status | Required Operator Action |
| --- | --- | --- | --- | --- | --- | --- |
| **G1** | No `PROCESSING` disposition case | Live-staging PostgreSQL (`retention_decommission_status`) | 2026-10-16T12:32+08:00 | Live DB not accessible from build workspace (local dev DB has 0 rows, which does not certify live staging) | **UNKNOWN** | Run `docker compose -f compose.staging.yaml exec -T web python manage.py retention_decommission_status` on the staging host and verify `G1 PASS`. |
| **G2** | No `APPROVED` or `QUEUED` disposition requiring institutional review | Live-staging PostgreSQL (`retention_decommission_status`) | 2026-10-16T12:32+08:00 | Live DB not accessible | **UNKNOWN** | Run `retention_decommission_status`. If `case_approved_or_queued > 0`, obtain authorized institutional review and hold/retire before deploying. |
| **G3** | No unresolved `FAILED` or `RECONCILIATION_REQUIRED` cases without recorded authorized handling | Live-staging PostgreSQL (`retention_decommission_status`) | 2026-10-16T12:32+08:00 | Live DB not accessible | **UNKNOWN** | Run `retention_decommission_status`. Reconcile any unresolved cases or record an explicit owner carry decision before rule retirement. |
| **G4** | No `ACTIVE` operational retention rules | Live-staging PostgreSQL (`retention_decommission_status`) | 2026-10-16T12:32+08:00 | Live DB not accessible | **UNKNOWN** | Run `retention_decommission_status`. If any rule is `ACTIVE` on `0512e9ec`, the DPO must retire it via the pre-decommission UI before deploying. |
| **G5** | Completed-case evidence agrees with source state (`completed_media_without_disposed_marker = 0` and `completed_tracer_source_still_present = 0`) | Live-staging PostgreSQL (`retention_decommission_status`) | 2026-10-16T12:32+08:00 | Live DB not accessible | **UNKNOWN** | Run `retention_decommission_status` and confirm `G5 PASS`. |
| **G6** | No broker-resident `compass.privacy_governance.*` messages in Redis (`celery` queue and `unacked` hash) | Live-staging Redis DB 0 | 2026-10-16T12:32+08:00 | Live Redis not accessible; Beat on `0512e9ec` is still actively scheduling `discover_retention` (300s) and `recover_disposition` (60s) | **BLOCKED / UNKNOWN** | Deploy PR 1 + PR 2 (`926d5c27`) with tombstones intact first, then run the runbook G6 Redis count command to verify 0 queued and 0 unacked `compass.privacy_governance.*` messages. |
| **G7** | No old destructive executor running (`celery inspect active`) | Live-staging worker (`0512e9ec`) | 2026-10-16T12:32+08:00 | Worker is still running build `0512e9ec` with the pre-PR 1 destructive executors registered | **BLOCKED** | Verify `celery --app config inspect active` has no running `execute_disposition`, deploy `926d5c27`, and confirm `inspect registered` replaces the executors with PR 1 tombstones. |
| **G8** | E-Counseling custody-transfer cleanup remains healthy | Live-staging worker diagnostics & `retention_decommission_status` | 2026-10-16T12:32+08:00 | Live worker logs and DB counts not accessible | **UNKNOWN** | Confirm `PROVIDER_CLEANED` and `RECOVERY_SCAN_COMPLETE` diagnostics continue before and after deploying `926d5c27`. |
| **G9** | Retired capability synchronization and rollback state are understood | `retention_decommission_status` grant/override counts + `sync_identity_policy` output | 2026-10-16T12:32+08:00 | `sync_identity_policy` for ADR-115 has not yet run on live staging (`926d5c27` undeployed) | **BLOCKED** | Record `retention_capability_override`, `retention_designation_grant`, and `retention_role_grant` counts before deploying `926d5c27`, then verify `sync_identity_policy` deletes the `.retention.manage` and `.retention.approve` rows. |
| **G10** | Actual deployed build identities are verified | `GET https://staging-api.compass-gco.com/api/v1/meta`; `gh run list --workflow=deploy-staging.yml` | 2026-10-16T12:32+08:00 | Live staging is at `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee` (`2026-10-11T09:00:30Z`), 27 commits behind `origin/staging` (`926d5c27`) | **BLOCKED** | Complete the ADR-114 / ADR-115 deployment cycle and verify `/api/v1/meta` `build_id` matches the deployed post-PR 2 SHA before authorizing PR 3 tombstone removal. |

> **Stop Condition Triggered:** Because `live-staging` is still running `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee` (neither PR #244 nor PR #245 has been deployed) and G1–G10 are blocked/unverified on live staging, **the Celery tombstones in `be/compass/privacy_governance/tasks.py` and the fail-closed fallback services in `be/compass/privacy_governance/retention.py` are intentionally retained**.

---

## C. Runtime Inventory

### 1. Former & Transitional Task Registrations (`be/compass/privacy_governance/tasks.py`)

| Task Name | Current State on `origin/staging` (`926d5c27`) | Current State on `live-staging` (`0512e9ec`) | PR 3 Action (While Gate Blocked) |
| --- | --- | --- | --- |
| `compass.privacy_governance.discover_retention` | Non-mutating tombstone (`ignore_result=True`, 0 SQL queries, logs `retention_task_decommissioned`) | Active periodic discovery executor (Beat every 300s) | **Retained as tombstone** until post-PR 1/PR 2 broker drain is verified |
| `compass.privacy_governance.execute_disposition` | Non-mutating tombstone (`ignore_result=True`, 0 SQL queries, 0 Daily/S3 calls) | Active destructive executor (`acks_late=True`, `reject_on_worker_lost=True`) | **Retained as tombstone** until post-PR 1/PR 2 broker drain is verified |
| `compass.privacy_governance.recover_disposition` | Non-mutating tombstone (`ignore_result=True`, 0 SQL queries, 0 dispatches) | Active recovery & re-dispatch task (Beat every 60s) | **Retained as tombstone** until post-PR 1/PR 2 broker drain is verified |

### 2. Remaining Codebase Imports of `privacy_governance.tasks` and `privacy_governance.retention`

| Module | Imported Symbol(s) | Purpose |
| --- | --- | --- |
| Production code (`be/compass/**/*.py`) | **None** (`0` imports of `compass.privacy_governance.tasks` or `compass.privacy_governance.retention`) | Verified by AST audit (`test_no_production_module_dispatches_retired_tasks_or_writes_the_legacy_ledger` and `test_every_registered_operation_is_documented_and_none_reaches_disposition`) |
| `be/tests/legacy_disposition_fixtures.py` | `SUPPORTED_CONTRACTS` from `compass.privacy_governance.retention` | Test-only helper to construct valid synthetic historical `OperationalRetentionRule` rows |
| `be/tests/test_operational_retention.py` | `retention`, `TOMBSTONE_TASK_NAMES`, `discover_retention`, `execute_disposition`, `recover_disposition` | Verifies tombstone no-op behavior and fail-closed service refusal |
| `be/tests/test_ecounseling_media_v2.py` | `execute_disposition`, `retention` | Verifies tombstones and fail-closed services never touch V2 media storage or Daily |
| `be/tests/test_ecounseling_media_realtime.py` | `execute_disposition` | Verifies tombstones emit no realtime media hints |
| `be/tests/test_graduate_tracer_confidential_content_encryption.py` | `discover_retention`, `execute_disposition`, `recover_disposition` | Verifies tombstones never decrypt or anonymize Graduate Tracer rows |

### 3. Obsolete Execution Paths Already Removed in PR 1 & PR 2

- `be/compass/privacy_governance/media_disposition.py` (`execute_media_disposition`) — **Deleted in PR #244**.
- `be/compass/graduate_tracer/disposition.py` (`anonymize_response`) — **Deleted in PR #244** (`ANALYTICAL_FIELDS` and `verify_anonymized` retained for historical integrity verification).
- `be/config/settings.py` Beat entries `retention-eligibility-discovery` and `retention-approved-dispatch-recovery` — **Removed in PR #244**.
- `be/compass/privacy_governance/retention_api.py` 14 legacy rule/case/hold/approval endpoints — **Removed in PR #245** (replaced by `GET /api/v1/privacy/retention/policies`).

### 4. Supported Background Tasks & Schedules Preserved Unchanged

| Task Name | Module | Beat Schedule Key | Purpose |
| --- | --- | --- | --- |
| `compass.ecounseling.ingest_media_artifact` | `compass/ecounseling/tasks.py` | Dispatched on webhook/recovery | Private COMPASS custody transfer & verified Daily provider-copy cleanup |
| `compass.ecounseling.recover_media_artifacts` | `compass/ecounseling/tasks.py` | `ecounseling-artifact-recovery` (60s) | Retries incomplete custody transfer and pending provider-copy cleanup |
| `compass.ecounseling.reconcile_media_captures` | `compass/ecounseling/tasks.py` | `ecounseling-capture-reconciliation` (60s) | Bounded metadata-only capture state reconciliation |
| `compass.notifications.email.deliver` | `compass/notifications/tasks.py` | On-commit dispatch | Transactional email notification delivery |
| `compass.notifications.email.dispatch_due` | `compass/notifications/tasks.py` | `notification-email-recovery` (60s) | Outbox recovery for due email notifications |
| `compass.notifications.push.deliver` | `compass/notifications/tasks.py` | On-commit dispatch | Web Push notification delivery |
| `compass.notifications.push.dispatch_due` | `compass/notifications/tasks.py` | `notification-push-recovery` (60s) | Outbox recovery for due push notifications |
| `compass.authentication.email_change.recover_unsent_alerts` | `compass/authentication/tasks.py` | `email-change-security-alert-recovery` (60s) | Security alert email recovery |
| `compass.infrastructure.noop` | `compass/tasks.py` | Manual / diagnostic | Infrastructure correlation smoke task |

---

## D. Historical Ledger Audit & Database Guard Decision

### 1. Retained Historical Ledger Tables

| Model | Database Table | Migrations | Evidence Preserved |
| --- | --- | --- | --- |
| `OperationalRetentionRule` | `privacy_governance_operationalretentionrule` | `0005`, `0006` | Frozen rule metadata (`code`, `category`, `contract_version`, `trigger`, `duration_days`, `action`, `policy_reference`, `effective_on`, `status`, `revision`, actor FKs and timestamps) |
| `DispositionCase` | `privacy_governance_dispositioncase` | `0005`, `0006` | Frozen single-record disposition ledger (`rule`, `rule_revision`, `category`, `contract_version`, `source_id`, `source_updated_at`, `eligible_at`, `state`, `blocker`, `approved_by`, `approved_at`, `started_at`, `completed_at`, `claim_token`, `attempts`, `manual_retries`) |
| `DispositionHold` | `privacy_governance_dispositionhold` | `0005` | Administrative hold reason, placement provenance (`placed_by`, `placed_at`), and release provenance (`released_by`, `released_at`) |

### 2. Complete Inventory of Database Readers and Writers

- **Production Writers (`be/compass/`):** **None (0 writers).** Verified via AST inspection (`test_no_production_module_dispatches_retired_tasks_or_writes_the_legacy_ledger`).
- **Production Readers (`be/compass/`):**
  1. `compass/privacy_governance/models.py` — Re-exports the three models so Django keeps them registered and `makemigrations --check` sees no model deletion.
  2. `compass/privacy_governance/management/commands/retention_decommission_status.py` — Read-only aggregate preflight (`SET TRANSACTION READ ONLY` when outermost on PostgreSQL) evaluating G1–G5.
  3. `compass/ecounseling/webhooks.py:223-225` (`_protected`) — Queries `DispositionCase.objects.filter(source_id=capture.pk, state__in=("PROCESSING", "COMPLETED")).exists()` to prevent late Daily webhooks from resurrecting disposed media.
  4. `compass/ecounseling/reconciliation.py:157-159` (`_protected`) — Queries `DispositionCase.objects.filter(source_id=capture.pk, state__in=("PROCESSING", "COMPLETED")).exists()` to supersede capture reconciliation for disposed media (especially critical after a backup restore if a capture row predates completion).
  5. `compass/ecounseling/artifacts.py:213` (`ingest_artifact`) — Queries `DispositionCase.objects.filter(source_id=source.pk, state="PROCESSING").exists()` as an ingestion fence.
- **Test Writers (`be/tests/`):**
  1. `tests/legacy_disposition_fixtures.py` (`legacy_rule`, `legacy_case`) — Creates synthetic historical rows for decommission, oversight, fence, and preflight tests.
  2. `tests/test_operational_retention.py:597` — Calls `OperationalRetentionRule.objects.update(status="RETIRED")` to test G4 transition in `retention_decommission_status`.
  3. `tests/test_ecounseling_media_v2_migration.py:68-98` — Creates historical `OperationalRetentionRule` and `DispositionCase` rows at migration `0005` and verifies upgrade to `0006`.

### 3. Conditional Database-Level Write Protection Evaluation (Section 6)

| # | Section 6 Precondition | Assessment | Met? |
| --- | --- | --- | --- |
| 1 | All legitimate former writers have been retired | Retired in `origin/staging` source (`926d5c27`), **not** yet retired in `live-staging` runtime (`0512e9ec`). | **NO** (on live staging) |
| 2 | No old worker can write or execute external destructive actions | `deploy-staging.yml:314-332` runs `python manage.py migrate --noinput` **while the old `0512e9ec` worker and Beat are still running**. On `0512e9ec`, `execute_disposition` performs external Daily/S3 deletion outside SQL transactions and then updates `ECounselingMediaCapture.artifact_disposed_at` and `DispositionCase.state = 'COMPLETED'` in a second transaction. If `migrate` installs a `BEFORE UPDATE` trigger on `DispositionCase` while an old worker is mid-execution, the post-deletion transaction will fail and roll back `artifact_disposed_at` after the external artifact was already destroyed. | **NO** |
| 3 | Existing historical rows have been reconciled sufficiently for the protection decision | G1–G5 (`retention_decommission_status`) have not been executed on `live-staging`. If `live-staging` has `ACTIVE` rules or `APPROVED`/`QUEUED` cases, Runbook Stage A requires retiring rules or placing holds on the pre-decommission build before freezing the tables. | **NO** |
| 4 | The guard will not break required migrations | Existing `test_privacy_governance_migrations.py` migrates between `0002` and `0004` and leaves `privacy_governance` at `0004` in its `finally` block; `test_ecounseling_media_v2_migration.py` migrates to `leaf_nodes()`. | Conditional |
| 5 | E-Counseling readers remain unaffected | `SELECT` queries in `webhooks.py`, `reconciliation.py`, and `artifacts.py` are unaffected by `BEFORE INSERT OR UPDATE OR DELETE` triggers. | Yes |
| 6 | Restoration procedures account for the guard | Pre-PR 3 backups restored and migrated would activate the guard before post-restore reconciliation unless reconciliation is read-only on `DispositionCase`. | Conditional |
| 7 | Test setup can construct necessary synthetic historical fixtures safely | All 6 test suites using `tests/legacy_disposition_fixtures.py` write directly to the three tables via ORM `.create()` / `.update()`, which an unconditional DB trigger would reject unless wrapped in a session-variable bypass context. | Requires fixture bypass |
| 8 | The migration can be reversed under a controlled procedure | `DROP TRIGGER` + `DROP FUNCTION` in `reverse_sql` is cleanly reversible. | Yes |
| 9 | A full fresh-database migration replay remains valid | Valid for schema creation, since `0001`–`0006` insert no rows into the three tables. | Yes |

**Decision on Database-Level Write Protection:** **DEFERRED (Do Not Implement Speculative Migration Before Runtime Gate Passes).**
Per Section 6 ("If not safe or unnecessary: Document the decision clearly. Do not create a speculative migration merely because PR 3 was originally expected to include one. Do not substitute a broken migration for operational safety"), adding a PostgreSQL write-rejection trigger migration before `live-staging` has transitioned off `0512e9ec` and passed G1–G5 is unsafe because `deploy-staging.yml` executes `migrate` while the `0512e9ec` worker and Beat are still running. In addition, avoiding a premature `0007` trigger migration prevents unnecessary migration-graph churn ahead of the separately planned post-PG-1A canonical migration consolidation (Section 9).

---

## E. Implementation (Non-Destructive PR 3 Preparation)

### 1. Files Changed

| File | Change |
| --- | --- |
| `be/compass/privacy_governance/retention_models.py` | Updated module docstring to document that `OperationalRetentionRule`, `DispositionCase`, and `DispositionHold` form the preserved historical disposition ledger (ADR-114, ADR-115) and that `DispositionCase.source_id` fences E-Counseling webhook, ingestion, reconciliation, and backup-restore paths. |
| `be/docs/retention-disposition-runbook.md` | Documented the explicit PG-1A PR 3 readiness boundary: why the temporary Celery tombstones and fail-closed fallback services remain until ADR-114/ADR-115 are deployed and G1–G10 pass on live staging, why the legacy ledger tables are preserved for `DispositionCase.source_id` fencing, and why any PostgreSQL trigger guard migration is deferred until after the live-staging transition. |
| `be/tests/test_operational_retention.py` | Added `test_no_production_module_dispatches_retired_tasks_or_writes_the_legacy_ledger` (AST verification that no production module dispatches retired tasks or calls ORM write methods on the historical ledger models, and that only the 5 expected modules import those models) and `test_completed_disposition_case_fences_restored_capture_against_webhook_and_reconciliation` (proving that a restored capture with `artifact_disposed_at=None` is protected from both webhook resurrection and capture reconciliation solely by `DispositionCase.source_id`). |
| `outputs/pg-1a/PG-1A-PR3-Implementation-Report.md` | Created this evidence-based PR 3 readiness and implementation report. |

### 2. Files Deleted

- **None.** Both `be/compass/privacy_governance/tasks.py` (protective Celery tombstones) and `be/compass/privacy_governance/retention.py` (protective fail-closed fallback services) are retained while the live-staging runtime readiness gate is blocked.

### 3. Migrations Added

- **None** (`makemigrations --check --dry-run`: `No changes detected`).

---

## F. Testing & Validation Evidence

All validation commands were executed in `/Users/reynantlntno/Projects/COMPASS-PG-1A-PR3/be` using synthetic fixtures against local PostgreSQL 17.11 (`127.0.0.1:5432`) and Redis 8.10.1 (`127.0.0.1:6379`) with `tests.settings`.

| Command | Result |
| --- | --- |
| `python manage.py check --settings=tests.settings` | **0 issues** (`System check identified no issues (0 silenced).`) |
| `python manage.py makemigrations --check --dry-run --settings=tests.settings` | **No changes detected** |
| `python manage.py export_openapi --check --settings=tests.settings` | **Current** (`OpenAPI contract is current`) |
| `pytest tests/test_retention_policy_register.py tests/test_operational_retention.py tests/test_ecounseling_media_v2.py tests/test_graduate_tracer_graduation_classification.py tests/test_privacy_governance.py tests/test_privacy_governance_expansion.py tests/test_privacy_activity.py tests/test_privacy_governance_contract.py tests/test_privacy_pending_acknowledgment.py -q --reuse-db` | **180 passed, 0 failed** in 118.38s (including the 2 new PR 3 tests) |
| `ruff check compass/privacy_governance/retention_models.py tests/test_operational_retention.py` | **All checks passed!** |
| `ruff format --check compass/privacy_governance/retention_models.py tests/test_operational_retention.py` | **2 files already formatted** |
| `git diff --check` | **Clean** (0 whitespace or formatting errors) |

### Inherited Repository Failures (Unrelated to PG-1A; Not Modified per Section 9 & 10)

As documented in the PG-1A PR 1 and PR 2 reports, `origin/staging` carries pre-existing failures outside the PG-1A slice (left untouched per Section 9 & 10):
- `.github/scripts/backend_ci.py verify`: `test_domain_activity.py`, `test_good_moral_assisted.py`, and `test_graduate_tracer_graduation_classification.py` are not listed in shard `BUNDLES`.
- `ruff format --check .` / `ruff check .` across the full `be/` tree: 8 unformatted files and 38 lint findings inherited from earlier Graduate Tracer, report, and guidance-message commits.
- `test_accounts.py` role-grant count pin (`93` vs `95` from `#243` `good_moral.initiate`), `test_privacy_release_audit.py`, and `test_openapi_contract.py` operation count/filter pins.

**New regressions introduced by this branch:** **0**.

---

## G. Deployment Sequencing & Operator Runbook

Because `live-staging` is currently at `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee` (pre-PR 1 and pre-PR 2), operators must execute the transition in two distinct deployment phases:

### Phase 1: Deploy Merged PG-1A PR 1 (#244) + PR 2 (#245) (`origin/staging` `926d5c27`)

1. **Pre-deploy live-staging preflight (Stage A, read-only):**
   - Run the read-only preflight SQL (`PG-1A-Decommission-Runbook.md` §2.1) against live-staging PostgreSQL, or inspect via a one-off read-only query.
   - Verify **G1** (`0 PROCESSING`), **G2** (`0 APPROVED`, `0 QUEUED`), **G3** (`0 FAILED`, `0 RECONCILIATION_REQUIRED` unless recorded under an explicit owner decision), **G4** (`0 ACTIVE` rules), and **G5** (`0` completed-case mismatches).
   - If any rule is `ACTIVE` or any case is `APPROVED`/`QUEUED` on `0512e9ec`, resolve it on `0512e9ec` first (place holds or retire active rules through the existing audited flow) before deploying.
   - Record **G9** capability grant and override counts for `privacy_governance.retention.*`.
2. **Deploy backend (`deploy-staging.yml`) at `926d5c27` (or current reviewed `staging` SHA):**
   - Verify all 27 undeployed commits and migrations between `0512e9ec` and `926d5c27` have release approval.
   - `deploy-staging.yml` runs `migrate`, then `sync_identity_policy` (which deletes persisted `.retention.manage` and `.retention.approve` grants, overrides, and capability rows), then `up -d --remove-orphans`.
   - New `worker` starts with the three PR 1 tombstones (`discover_retention`, `execute_disposition`, `recover_disposition`) registered; new `beat` starts without `retention-eligibility-discovery` or `retention-approved-dispatch-recovery`.
3. **Deploy frontend (`vercel --prod`) from the same SHA:**
   - Serves the read-only Retention Policies workspace (`/portal/privacy/retention`) against `GET /api/v1/privacy/retention/policies`.
4. **Post-deploy verification (Stage C & D):**
   - Verify **G10**: `GET https://staging-api.compass-gco.com/api/v1/meta` `build_id` equals the deployed SHA.
   - Run `docker compose -f compose.staging.yaml exec -T web python manage.py retention_decommission_status` and confirm exit code `0` (`G1`–`G5` `PASS`).
   - Run the **G6** Redis check (`LRANGE celery 0 -1` and `HVALS unacked`) and confirm `0` `compass.privacy_governance.*` messages remain.
   - Run the **G7** worker check (`celery --app config inspect active` and `inspect registered`) and confirm no active disposition task is running and the three tombstones are registered.
   - Confirm **G8** E-Counseling custody-transfer cleanup diagnostics (`PROVIDER_CLEANED`, `RECOVERY_SCAN_COMPLETE`) continue normally.

### Phase 2: Complete Final PR 3 Tombstone & Fallback Removal (Only After Phase 1 Gate Passes)

Once Phase 1 is verified with G1–G10 passing on `live-staging` and after a second post-decommission deploy overwrites `.deploy.previous.env` so a single-step rollback cannot reintroduce `0512e9ec`:

1. Remove `be/compass/privacy_governance/tasks.py` (`discover_retention`, `execute_disposition`, `recover_disposition` tombstones).
2. Remove the five fail-closed fallback functions (`create_rule`, `update_rule`, `transition_rule`, `change_hold`, `approve_case`) from `be/compass/privacy_governance/retention.py` and relocate `SUPPORTED_CONTRACTS` to `tests/legacy_disposition_fixtures.py`.
3. Optionally apply a reversible PostgreSQL trigger migration (`BEFORE INSERT OR UPDATE OR DELETE` on `privacy_governance_operationalretentionrule`, `privacy_governance_dispositioncase`, `privacy_governance_dispositionhold`) if not superseded by the upcoming canonical migration baseline.

---

## H. Future Canonicalization Handoff (Not Implemented in PG-1A)

The following items are recorded for the upcoming repository-wide canonicalization and migration-consolidation milestone (Section 9) and were deliberately excluded from this PR:

1. **`be/compass/privacy_governance/tasks.py` and `be/compass/privacy_governance/retention.py`:** Remove once live-staging G1–G10 readiness evidence confirms the Phase 1 transition and broker drain.
2. **Historical `privacy_governance` migration consolidation (`0001`–`0006`):** Earlier migrations (`0002` creating `RetentionPolicy`, `ProcessingActivity`, `PrivacyReview`, `PrivacyIncident`; `0003` narrowing scope; `0004` removing `RetentionPolicy`; `0005`–`0006` creating `OperationalRetentionRule`, `DispositionCase`, `DispositionHold`) can be consolidated when the repository-wide canonical baseline migration graph and controlled staging database rebuild are executed.
3. **Order-fragile migration tests (`test_privacy_governance_migrations.py` and `test_ecounseling_media_v2_migration.py`):** `test_privacy_governance_migrations.py` currently migrates only to `0004` in its `finally` block instead of `leaf_nodes()`, and `test_ecounseling_media_v2_migration.py` can raise `InvalidMigrationPlan` when run after later `ecounseling` migrations. Both should be aligned with the canonical migration baseline.
4. **E-Counseling `PROCESSING` fence check (`be/compass/ecounseling/artifacts.py:211-215`):** Once live staging confirms `0 PROCESSING` cases (`G1 PASS`) and all executors are gone, the `state="PROCESSING"` check in `ingest_artifact` is permanently false (while the `COMPLETED` fences in `webhooks.py` and `reconciliation.py` remain necessary whenever historical disposed media rows exist).
5. **Inherited CI selector and Ruff formatting drift:** Register `test_domain_activity.py`, `test_good_moral_assisted.py`, and `test_graduate_tracer_graduation_classification.py` in `.github/scripts/backend_ci.py`, and reconcile the 8 unformatted / 38 lint-flagged Graduate Tracer and report files plus stale capability/OpenAPI test pins in `test_accounts.py`, `test_privacy_release_audit.py`, and `test_openapi_contract.py`.
