# CANON-1C — PG-1A decommission verification

Implements the reset-only retirement in
[CANON-1B-PG-1A-Reset-Handoff.md](../canon-1/CANON-1B-PG-1A-Reset-Handoff.md), on
`codex/canon-1c-schema-uat-dataset` only. The deployed compatible runtime keeps the ADR-114
tombstones and ledger until its operator cutover; nothing here changes it.

## Removed (reset-only)

| Component | Removal | Proof |
| --- | --- | --- |
| `privacy_governance/retention_models.py` — `OperationalRetentionRule`, `DispositionCase`, `DispositionHold` | Models and the re-export in `models.py` deleted; tables absent from the baseline | `test_ledger_models_tables_and_preflight_command_are_absent`; schema comparison (3 tables, 48 columns, 26 constraints, 18 indexes only in A) |
| `privacy_governance/tasks.py` — `discover_retention`, `execute_disposition`, `recover_disposition` tombstones | Module and Celery registrations deleted | `test_retired_disposition_task_names_are_not_registered` (after `autodiscover_tasks(force=True)`); `verify` schema section |
| `privacy_governance/retention.py` — five 409 fallback services, `SUPPORTED`/`SUPPORTED_CONTRACTS` | Deleted | `test_retired_engine_modules_are_not_importable` |
| `retention_decommission_status` command (and the now-empty `management` package) | Deleted | Absent from `get_commands()` |
| Ledger arms of `ecounseling/webhooks.py:_protected`, `reconciliation.py:_protected`, and the `DispositionCase` PROCESSING query in `artifacts.ingest_artifact` | Removed; nothing else in those predicates changed | AST scan `test_no_production_module_references_the_retired_engine` (no import, name, task string or `retention_decommissioned` code anywhere in `compass/` outside migrations) |
| `tests/legacy_disposition_fixtures.py`, `tests/test_operational_retention.py`, retired-executor/hold tests in media, realtime and Graduate Tracer encryption suites | Deleted or replaced | Ledger-free `tests/historical_outcome_fixtures.py` keeps the anonymous-contribution and disposed-media writers |
| CI selector entries | `test_operational_retention.py` → `test_disposition_decommission.py`; model-layout example updated | `backend_ci.py verify`, selector self-tests pass |

No disposition subsystem replaces the ledger. No retention duration, rule or adoption was created.

## Preserved

| Boundary | Where | Evidence |
| --- | --- | --- |
| Capture disposal marker `artifact_disposed_at`; artifact STORED/DISPOSED, `disposed_at`, `provider_deleted_at` | `webhooks._protected`, `reconciliation._protected` | `test_disposal_markers_fence_late_provider_callbacks_without_a_ledger`; media v2 `test_historically_disposed_v2_media_stays_fenced_against_ingestion_and_late_events` |
| Terminal capture states, quarantined provider binding, claim tokens, bounded recovery | `reconciliation._protected`, `claim_capture`, `apply_observation` | E-Counseling reconciliation and concurrency suites (unchanged) |
| Unknown room / unknown instance rejection with durable receipt and no provider action | `webhooks` resolution | `test_callback_for_a_room_absent_from_the_new_database_creates_nothing` (no room, capture, artifact or dispatch); `test_unknown_room_has_durable_closed_evidence_without_provider_action` |
| Ingestion: V2, READY, consent authorization, verified binding, `artifact_eligible`, advisory and row locks, storage verification | `artifacts.ingest_artifact` | Media v2, storage-namespace and realtime suites |
| Artifact `PROCESSING` (custody retry state) | unchanged; distinct from the removed `DispositionCase.state="PROCESSING"` | Media v2 retry tests |
| Custody transfer `delete_v2_provider` and Daily artifact paths | unchanged | `test_daily_artifact_resource_paths_used_by_custody_cleanup_stay_documented` |
| Code-owned retention register, `GET /privacy/retention/policies`, DPO read-only scope | unchanged | `test_retention_policy_register.py` (ledger-free), `test_dpo_keeps_only_retention_view_and_no_confidential_content`, `test_retired_ledger_routes_are_unreachable_and_the_register_is_served` |
| Retired capabilities `.retention.manage` / `.approve` | still in `RETIRED_CAPABILITY_CODES`; never granted | `verify` configuration section; DPO capability equals the DPO designation |
| Historical audit vocabulary and presenters | unchanged | `test_historical_audit_vocabulary_is_still_presented` |
| Graduate Tracer anonymous-contribution integrity and report exclusions | unchanged readers | `test_historical_anonymized_contribution_keeps_its_integrity_and_exclusions` |

## Strategy and its preconditions

The handoff's **clean-reset strategy** was selected: the ledger dependency is retired because the
canonical database has an empty historical domain. That is only true if, at cutover:

1. no historical capture, room, receipt, recovery, rule, case or hold row is imported;
2. old room and capture identities are never reused (new rooms get UUID4 IDs and `ec-<hex>` names);
3. old Daily callbacks cannot bind to anything (unknown-room rejection, proven above);
4. no old web, worker or Beat process can reach the new database or broker;
5. old queued messages are isolated in a separate broker namespace and never restored;
6. no pre-reset backup is restored into the canonical runtime;
7. provider and object-storage resources are inventoried and classified separately.

Items 1 and 6 are partly enforced in code: the pre-canonical history guard (`compass.E001` and the
`pre_migrate` receiver) refuses any database carrying old migration records, which blocks a
restored old dump from being migrated or checked into service. A data-only import into a fresh
schema is not detectable by the application and is prohibited by the cutover plan. Items 2–5 and 7
are operator gates in [CANON-1C-Cutover-Dependencies.md](CANON-1C-Cutover-Dependencies.md); they
are not certified by this branch. If any cannot be guaranteed, this branch must not be activated:
the minimal protected deny store described in the handoff would be required first.

## Validation

- `tests/test_disposition_decommission.py`: 20 passed (including parametrized cases).
- Affected suites (`test_retention_policy_register.py`, `test_ecounseling_media_v2.py`,
  `test_ecounseling_media_realtime.py`, Graduate Tracer encryption and classification): passed.
- Full backend regression: see [CANON-1C-Regression-Report.md](CANON-1C-Regression-Report.md).
