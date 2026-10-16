# CANON-1B — PG-1A reset handoff

Date: 2026-10-16 (Asia/Manila). Source baseline: `0d7fbd0a5fd0ee6d38aba091a27ffa4ed3ac4691`.

This is source review and preparation only. No database, migration, Celery registration, runtime,
infrastructure, provider artifact or storage object was changed for this handoff. A reset is a
separately authorized operation. The compatible CANON-1B PR must retain the transition safeguards.

## Evidence and current boundary

Owning decisions are `be/docs/decisions/ADR-114-decommission-in-app-disposition.md` and
`ADR-115-code-owned-retention-oversight.md`; ADR-072 and ADR-092 describe the historical execution
contracts and the surviving media custody boundary. Supporting evidence is
`outputs/pg-1a/PG-1A-PR2-Implementation-Report.md`,
`outputs/pg-1a/PG-1A-PR3-Implementation-Report.md`, and
`be/docs/retention-disposition-runbook.md`.

PR 3's recorded runtime snapshot found pre-decommission web/worker/Beat code and unverified live
broker/database gates. That report is historical evidence, not a fresh runtime certification. This
handoff inspected the current owning source but did not access a live database, broker, worker,
Daily account, object bucket or backup catalog. No live gate is certified here. In particular,
absence of source dispatchers does not prove absence of queued messages or old executors.

The normal `.github/workflows/deploy-staging.yml` still runs migrations and synchronization before
`compose up -d --remove-orphans` replaces application containers. It is unsuitable for removing the
ledger or installing a write-rejection trigger while old workers may still execute provider work.
An external delete can succeed before a later database write fails. Do not use normal deployment
ordering as the reset procedure.

## Removal classification

| Source/component | Compatible PR now | Reset-only canonical baseline |
| --- | --- | --- |
| `privacy_governance/tasks.py` and its three task names | Retain non-mutating tombstones. Source dispatch is gone, but delivery compatibility is still unverified. | Remove the module/registrations after the stopped-runtime and broker-isolation gates below. |
| `privacy_governance/retention.py` | Retain the five unconditional 409 fallback services for this transition. No production importer remains, so these are not active domain services. | Delete the module and its test dependencies together; do not restore mutation routes or executors. |
| `SUPPORTED` / `SUPPORTED_CONTRACTS` in `retention.py` | Test-only vocabulary can be relocated without changing behavior, if needed; relocation alone is not decommission completion. No such edit is required here. | Delete with legacy fixture machinery when no retained historical tests need it. If historical fixtures remain, keep their vocabulary under `tests/`, not production execution code. |
| `retention_models.py` and model re-exports in `privacy_governance/models.py` | Retain all three persisted models and vocabulary/constraints. They are registered schema and have real readers. | Remove models/re-exports and omit the tables from the future consolidated baseline only after removing/replacing every reader. No consolidation in CANON-1B. |
| `retention_decommission_status` command | Retain its read-only transition preflight; it is useful before reset and references all ledger models. | Remove it, or replace it with a separately named canonical health check that does not query removed tables. Preserve the reviewed pre-reset evidence externally. |
| E-Counseling `DispositionCase` reads | Retain all three queries. G1/source reasoning alone is insufficient while runtime state is unknown. | Remove only under the selected clean-reset retirement or replacement strategy below. |
| Retention register/API/page, Privacy Notices, Audit Trail, consent, custody | Preserve. These are canonical functionality. | Preserve and validate; no disposition engine reappears. |

There is no standalone PG runtime deletion recommended in this compatible PR. The deleted historical
Graduate Tracer/media executors are already absent. Removing protective code merely because it has
no source caller would mistake Celery wire compatibility and restore protection for dead code.

## Actual readers, entry points and test dependencies

Current production code has no import of `compass.privacy_governance.retention` or
`compass.privacy_governance.tasks`, and no disposition dispatch or ledger ORM writer was found in
the reviewed source. The three retained tasks accept arbitrary arguments, do not inspect them,
perform no database/provider/storage work, enqueue nothing and log only a minimized diagnostic.
Celery autodiscovery, rather than a Python application caller, keeps their wire names available:

- `compass.privacy_governance.discover_retention`
- `compass.privacy_governance.execute_disposition`
- `compass.privacy_governance.recover_disposition`

The five `retention.py` services are `create_rule`, `update_rule`, `transition_rule`, `change_hold`
and `approve_case`. Each immediately calls `decommissioned()` and raises 409
`retention_decommissioned`; there is no provider execution fallback. Historical contract vocabulary
is consumed by `tests/legacy_disposition_fixtures.py`, not the read-only register.

| Current ledger consumer | Exact behavior and consequence |
| --- | --- |
| `be/compass/privacy_governance/models.py` | Re-exports `OperationalRetentionRule`, `DispositionCase`, `DispositionHold` so Django registers the persisted schema. Removing these is a model/schema change. |
| `be/compass/privacy_governance/management/commands/retention_decommission_status.py:collect` | Counts rule states, cases, holds, completed-source mismatches, custody state, grants and historical actions. G1–G5 are database-only; G6–G10 are explicitly unverified. No mutation. |
| `be/compass/ecounseling/webhooks.py:_protected` | `DispositionCase.objects.filter(source_id=capture.pk, state__in=("PROCESSING", "COMPLETED")).exists()`. Called by `_apply` before changing capture state and by `_run_policy_stop` before provider mitigation. Protects restored captures even when their local disposal timestamp is absent. |
| `be/compass/ecounseling/reconciliation.py:_protected` | Same source/state query. Called by `claim_capture` and `apply_observation`, so the gate applies before a metadata fetch and again when applying its result. Protected recovery becomes superseded; it cannot recreate READY/custody state. |
| `be/compass/ecounseling/artifacts.py:ingest_artifact` | After locking capture/artifact, queries the same source UUID with `state="PROCESSING"` only; logs INELIGIBLE and returns. This is not a COMPLETED-ledger check. It additionally keeps `artifact_eligible` and artifact DISPOSED checks. |

The queries use source UUID and state, without category/contract filtering. Do not describe them as
rule eligibility evaluation. They are safety fences, and no public retention API exposes source IDs.
`DispositionCase.rule` and `DispositionHold.case` use PROTECT; actors also have protected provenance.
There is no safe ordinary cascade-removal shortcut.

`be/tests/test_operational_retention.py` verifies no production dispatch/writers and the completed-case
restore fence (`test_completed_disposition_case_fences_restored_capture_against_webhook_and_reconciliation`).
Other source references needing a reset-only edit are:

- `tests/legacy_disposition_fixtures.py`: writes synthetic rules/cases/holds and historical outcomes;
  imports `SUPPORTED_CONTRACTS` and the three ledger models.
- `tests/test_operational_retention.py`: task no-ops, 409 fallback services, historical ledger and
  preflight gates, source-reader inventory and restored-capture protection.
- `tests/test_retention_policy_register.py`: proves oversight is independent of synthetic ledger rows.
- `tests/test_ecounseling_media_v2.py`, `test_ecounseling_media_realtime.py`, and
  `test_graduate_tracer_confidential_content_encryption.py`: retired-task/service safety checks and
  historical outcome fixtures. Keep their independent custody, realtime privacy and encryption tests.
- `tests/test_graduate_tracer_graduation_classification.py`: anonymous historical contribution fixture;
  this is an additional historical-data concern, not justification to delete analytical invariants.
- `tests/test_ecounseling_media_v2_migration.py`: creates migration-era rules/cases; belongs with the
  future consolidated migration test replacement, not this compatible slice.

## Tombstone-free activation prerequisites

The forthcoming reset runbook must require recorded evidence for the exact environment and image,
not merely passing local tests or a merged PR. These are prerequisites for later work, not actions
performed or authorized by this document.

1. Inventory all web, worker, Beat, one-off processes, deployment projects/hosts and rollback paths
   that can use the old PostgreSQL/broker/provider configuration. Freeze competing deploys and
   prevent new legacy producers, including older web/worker/Beat instances.
2. Stop the previous web/worker/Beat runtimes before activating a tombstone-free image. Establish that
   no disposition executor is active on any worker; address interrupted external operations with
   recorded authorized handling. Do not infer safety from forcibly terminating a task whose provider
   operation may already have happened.
3. Collect `retention_decommission_status` and operator evidence while the old schema is available:
   G1 PROCESSING; G2 APPROVED/QUEUED; G3 FAILED/RECONCILIATION_REQUIRED; G4 ACTIVE rules; G5 completed
   source consistency. A clean-reset owner decision may supersede preservation of disposable staging
   rows, but must explicitly account for external effects and unresolved cases. This command never
   authorizes destruction and exits 3 while database gates are blocked.
4. Isolate all old task deliveries from the new runtime before activation. Inventory actual broker
   namespaces/routes, queue variants/priorities, reserved and scheduled/ETA work, retries, Redis
   unacknowledged messages/redelivery and persistent broker snapshots. An empty default `celery`
   list alone is insufficient. Use a separately approved isolated broker namespace or verified
   drain/quarantine procedure; do not issue a blind shared Redis purge. Old work must not be restored
   into the new broker later. Include other stale tasks that refer to old row IDs.
5. Prevent old images, `.deploy.env` / `.deploy.previous.env`, manual rollback commands and old
   schedules from reconnecting to the new database/broker. Merely overwriting one previous-image
   file does not invalidate every retained image or backup. A reset-only image must be explicitly
   gated against ordinary deployment to the old schema; an old image must not run against the new one.
6. Validate the selected capture-history strategy below, provider/callback inventory and storage
   ownership. Preserve/reconfigure secrets deliberately; database reset does not rotate or isolate
   provider credentials or webhook signing keys.
7. Activate the reviewed canonical schema/image on the isolated resources, synchronize current
   identity policy, and verify actual web/worker/Beat build identities, retired-task absence, current
   Beat schedule, read-only oversight, consent and custody recovery. Record evidence before lifting
   the deployment freeze. No old ledger query may reach a table omitted from the new baseline.

An alternative compatible, non-reset transition remains the ADR-114/115 sequence: first deploy
tombstones/read-only APIs, verify G1–G10 and broker drain, then remove registrations in a later
reviewed release. That sequence retains ledger-backed restore fences wherever history survives.

## Ledger elimination and resurrection protection

**Preferred strategy for the intended disposable-staging rebuild: retire the ledger dependency only
with a verified empty historical domain boundary.** The reset-only baseline can remove all three
models because no old rules/cases/holds/captures/rooms/receipt/recovery rows are imported, no old worker
can run, old broker work is isolated, and old callbacks cannot bind to new captures. New rooms must
have fresh, non-reused provider identities. Current `services._ensure_local_room_binding` generates
UUID4 room IDs and `ec-{room_id.hex}` names; the reset plan must prohibit importing/reusing old IDs
and verify provider configuration. Preserve unknown-room/instance rejection, verified provider
binding, conflict quarantine, consent checks and assigned authorization. A callback for an absent old
room must not create a room/capture/artifact or enqueue ingestion. Old recovery/receipt data must not
silently be seeded into the new database.

Under those verified conditions, remove only the `DispositionCase` import/query arms from the two
`_protected` predicates and the PROCESSING query in `ingest_artifact`. Preserve the remaining fences:

- Capture `artifact_disposed_at`; artifact STORED/DISPOSED, `disposed_at` and
  `provider_deleted_at` protections in webhook/reconciliation paths.
- Reconciliation terminal-state and quarantined-binding protections, claim-token/current-identity
  checks and bounded recovery.
- Ingestion's V2, READY, consent authorization, verified binding, disposal eligibility, advisory/row
  locks, current claim/source checks and storage verification.

Do not conflate `DispositionCase.state="PROCESSING"` with
`ECounselingMediaArtifact.status="PROCESSING"`. Artifact PROCESSING remains an active custody/retry
state after the disposition engine is removed.

**If any historical captures or pre-disposal backups can return, retirement is not justified.**
Capture timestamps alone are inadequate: a backup may restore `artifact_disposed_at=None` while the
protected completed case is the only remaining denial evidence. Before dropping the ledger, either
keep it available to the existing fences or implement a separately reviewed minimal deny/tombstone
store keyed by original capture identity, with protected restoration/import reconciliation. Carry
completed outcomes and unresolved PROCESSING outcomes until explicitly reconciled; do not erase an
uncertain external result by recasting it as success. Apply the replacement gate at webhook apply
and mitigation, reconciliation claim and apply, and ingestion. Preserve it independently from any
source snapshot that predates disposition, and block service activation until reconciliation is done.
Do not link an anonymous Graduate Tracer contribution back to its original response through this
replacement. A generic JSON archive or copying legacy rows into the register is not an approved
substitute. The reset-only implementation must select one strategy and prove its preconditions;
this report does not add a new persisted store or migration.

Only after these consumers are resolved should future canonical migration work omit
`privacy_governance_operationalretentionrule`, `privacy_governance_dispositioncase` and
`privacy_governance_dispositionhold` (historically created by 0005/0006), remove the decommission
command and replace historical tests with the applicable canonical absence/security tests. No
trigger migration or migration-history rewrite is proposed in CANON-1B.

## External artifacts, broker and backup boundary

PostgreSQL recreation removes neither Daily recordings/transcripts nor private object-storage
objects, Redis queues/unacked state, object versions, provider copies, snapshots, exports or backups.
Losing database references can instead make those objects harder to reconcile. The future operator
plan must inventory provider-held V1 artifacts and V2 local/provider custody state before removing
references, classify orphaned/retained resources and obtain separate authority for any cleanup.
This handoff authorizes no provider/object deletion, lifecycle expiry change or Redis purge.

Keep private storage isolation and the sensitive-storage prohibition on age-based expiration.
Keep `artifacts.ingest_artifact`, `delete_v2_provider`,
`compass.ecounseling.ingest_media_artifact`, `recover_media_artifacts`, capture reconciliation and
webhook replay. Verified deletion of a Daily copy after verified private COMPASS custody is the
existing custody transfer; it does not grant permission to delete retained COMPASS media by age.
Record backup retention and restore ownership separately. Old backups must not be restored into
the canonical runtime without an explicit historical-data and anti-resurrection compatibility plan.

## Required validation for the later reset-only implementation

- Static source/contract checks: no retired task registration, dispatch, five fallback services,
  ledger model/table/query or legacy mutation operation; current policy synchronization still
  retires `.retention.manage` and `.retention.approve` rather than granting them.
- Fresh canonical database/schema replay and migration-drift checks in the separately authorized
  consolidation slice; no dangling model import, management command or fixture dependency.
- Canonical policy register validation and authenticated `retention.view` GET: three code-owned
  entries, no seeded adoption/duration, no ledger query, no mutation endpoint. Preserve Privacy
  Notices/revisions/acknowledgments and current Audit Trail authorization/minimization.
- Late foreign callback and recovery tests: no matching old room/source means no capture/artifact
  creation, provider action, ingestion dispatch or content/realtime disclosure. Test the chosen
  restore fence with a pre-disposal source if historical restoration remains supported.
- Keep meaningful consent, assigned-access, provider-binding quarantine, duplicate delivery,
  claim-race, custody verification/provider-cleanup recovery and realtime privacy coverage. Test
  disposal/source markers independently of the removed ledger where those markers remain supported.
- Keep historical action definitions/presenters in the compatible build. A disposable staging
  reset is not evidence that audit vocabulary is unused by every retained environment/export;
  future removal needs its own scope/consumer proof. Do not rewrite append-only events.

Validation performed for this document: current source/consumer searches, direct inspection of the
listed functions, tests, ADRs and implementation reports, plus `git diff --check` for this artifact.
No runtime test result, clean broker, live reset rehearsal or successful deployment is claimed.
