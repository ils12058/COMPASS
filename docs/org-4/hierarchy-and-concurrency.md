# Identity, hierarchy and PostgreSQL concurrency

Catalog identity assurance: PASS within supported service/API paths and tested PostgreSQL
constraints. Campus UUID/code and College/Program UUID/code/parent remain stable through rename,
status and policy edits. Creation normalizes trim/uppercase codes; inactive records reserve codes.
Database uniqueness is on stored global Campus code or parent-qualified child code, not a SQL
normalization expression. Privileged SQL can bypass application immutability/ancestry checks.

Positive `resource_version` CHECKs exist for each model. Existing migrated and newly created rows
start at 1; actual change increments once; no-op preserves version/timestamp/Audit; stale positive
versions refuse; invalid raw SQL versions fail. Atomic failures preserve the previous state. The
real browser oracle checks UUID, parent, code, current state, actor and complete version sequences.
Populated 0003 migration tests compare every original field and reject zero directly in PostgreSQL.

Active child creation/reactivation requires active ancestors; Program additionally requires complete
configured policy. Inactive drafts may sit under inactive parents. No status command automatically
reactivates descendants, retires children, transfers parents or removes protected references.
PROTECT retains referenced identities; ordinary Catalog hard deletion has no exposed operation.

## Actual gates and ordering

`be/compass/organization/integrity.py` owns **477580715032**. Exclusive transaction advisory locking
serializes Catalog mutations; shared locking coordinates supported dependent writers. Initialization
uses distinct **477580715031** from `bootstrap.py`; no new locks were introduced by ORG-4.

Order is gate → current actor → active factor → session → Campus → College → Program. Dependent
writers acquire the shared gate before their pre-existing user/domain/mutex locks. Nested gates
remain held until outer commit. Shared-to-exclusive upgrades are unsupported. Future bulk paths
would need sorted same-level UUID ordering; this slice adds no bulk/move path.

Independent-connection tests use actual services, outer transactions, Events and `pg_locks` to
observe the contender's ungranted advisory lock before releasing the first writer. The history
read test intentionally does not wait: READ COMMITTED must hide uncommitted events. Sequential
HTTP tests and mocked UI scenarios are not counted as PostgreSQL races.

## Requested race matrix

Names abbreviated below are test function names in `test_catalog_concurrency.py` (C),
`test_catalog_final_integration.py` (F) or `test_organization_catalog.py` (I).

| # | Requested race | Executed evidence / result |
|---|---|---|
| 1–3 | Duplicate Campus/College/Program | C `test_duplicate_creates_have_one_identity_and_one_audit`, three entity cases; one identity/Audit, other conflict |
| 4 | Equivalent normalized codes | C normalized Campus plus F `test_normalized_duplicate_child_codes_have_one_committed_identity`, College/Program; safe duplicate conflict |
| 5–6 | Two renames; rename/status | C `test_two_renames_or_rename_versus_deactivation_reject_stale_writer`; stale contender refused |
| 7–9 | Child creation/activation versus parent retirement | C `test_child_create_or_activation_commits_before_parent_retirement_blocker_recheck` and `test_parent_retirement_first_prevents_concurrent_active_child_creation`; parent/child validity retained |
| 10–11 | Affiliation/responsibility versus retirement | C `test_relationship_assignment_vs_college_retirement`; initially allowed preview becomes blocked under exclusive recount |
| 12 | Account reactivation versus retirement | C `test_account_reactivation_vs_college_retirement`; unsafe restoration refused |
| 13–14 | Office/Follow-Up insertion versus Catalog | F `test_new_operational_work_waits_before_catalog_retirement_recount` and `test_catalog_change_first_serializes_new_operational_work_without_lost_relationship`; actual gate waits, retained work/relationships, explicit work blocker |
| 15 | Inventory selection versus retirement | C `test_program_retirement_vs_inventory_selection`; waiting selection refused |
| 16 | Inventory submission versus policy | C `test_policy_change_vs_inventory_submission_revalidates_membership`; incompatible draft remains unsubmitted |
| 17 | F4 creation versus policy, both orders | C `test_policy_change_vs_f4_creation_revalidates_classification`, `test_f4_creation_first_blocks_later_policy_mutation`; eligibility or pending-F4 barrier holds |
| 18 | F4 correction versus policy | C `test_pending_f4_correction_vs_policy_update`; pending policy refusal |
| 19 | Capability revoked while waiting | C `test_revoked_authority_during_wait_is_reloaded`; no stale authority commit |
| 20 | MFA expires while waiting/processing | C `test_mfa_expired_while_mutation_waited`; F late-expiry rollback adds synthetic time injection after Audit (separate non-race case) |
| 21 | Version increment then Audit failure | C `test_failed_transaction_rolls_back_before_waiting_writer_commits`, two faults; rollback leaves next valid writer able to commit |
| 22 | Concurrent initialization/adoption | I `test_concurrent_initialization_has_one_receipt_and_one_audit`, seed/adopt; one receipt/event |
| 23–24 | Lock timeout/deadlock | C `test_lock_timeout_returns_typed_safe_catalog_conflict`, `test_actual_postgresql_deadlock_is_translated_and_audit_rolls_back`; genuine PostgreSQL contention, `catalog_busy`, rollback |
| 25 | Stale impact preview | C relationship race begins with can_deactivate=true; committed dependency causes backend refusal with same target version |
| 26 | History/read versus change | F `test_history_reader_never_observes_uncommitted_catalog_event`; old state before commit, event/version after |
| 27 | Duplicate no-op intents | F `test_duplicate_noop_intents_share_gate_without_version_or_audit`; both succeed without fabricated change |
| 28 | Different parent/child operation orders | F `test_parent_child_rename_orders_complete_without_lock_inversion`, both orders; correct ancestry and independent version increments |
| Extra | Concurrent complete policy edits | F `test_two_complete_policy_changes_reject_stale_second_intent`; second policy refuses |
| Extra | Submission versus Program retirement | F `test_program_retirement_first_prevents_waiting_inventory_submission`; no stale submission |

Final counts are in evidence.json: 26 existing Catalog races, 12 additional ORG-4 independent-
connection cases and two initializer races, **40** distinct cases. Other selected Guidance/GM-OR
concurrency tests are backend regressions and are not added to this Catalog-specific total.
The 28 rows are requirement families, not 28 additional tests. Some families share a parametrized
case. A mapping does not assert every possible interleaving, engine, deployment locale or old writer.

Office/Follow-Up work-first fixtures already contain live affiliations/responsibilities, so their
initial preview is blocked; they additionally prove the work-specific blocker is counted. The
allowed-preview-to-blocked proof uses the separate relationship race. The reverse work case uses
a valid Catalog rename, since an already-dependent College cannot lawfully retire. These limits
are explicit rather than disguising impossible successful retirements as race evidence.

SQLSTATE 40P01/55P03/57014 is translated to a typed safe conflict; other failures propagate/roll
back. Cooperative locking and receipt checks do not stop old processes, privileged SQL or arbitrary
ORM writers. Operational exclusion and compatible recovery remain release blockers.
