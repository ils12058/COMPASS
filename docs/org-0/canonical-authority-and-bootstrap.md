# Canonical authority and bootstrap

**VERIFIED CODE FACT** unless explicitly marked otherwise. All source links pin the inspected SHA.

## What sync actually does

`sync_organization_catalog()` wraps the entire operation in `transaction.atomic()`. Exact identities
are Campus code, Campus+College code, and College+Program code. Existing rows are locked; absent-row
creation uses an inner savepoint and IntegrityError retry against database uniqueness. Name matching
never merges entities. `_repair_row` updates name, active flag and updated_at only, so UUIDs survive.
All current registry entries are active; existing canonical retirements are therefore undone.
New rows rely on the models' active default (the create helpers do not pass the definition's active
flag; a future inactive seed entry would require deliberate handling).

After processing canonical identities, active unknown Programs are set inactive with no historical
FK rewrites. Then unknown active Colleges are retired only if they have **no affiliation row and no
responsibility row**, and no remaining active Program. Unknown active Campuses require no active
College. Program retirement happens before the College checks, so unknown descendants may retire
in the same transaction; a relationship conflict rolls back all earlier creates/repairs/retirements.
This differs from the proposed future **no silent cascade** administration rule.

One SYSTEM `organization.catalog_synced` event records bounded created/updated/deactivated counts
only when persisted state changed. It is in the same transaction. No-op sync emits no event.
Audit persistence failure propagates and rolls back state; only the documented sync/integrity/model
exceptions are translated into CanonicalOrganizationSyncError.
Sources: [be/compass/organization/bootstrap.py:48](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L48);
[be/compass/organization/bootstrap.py:81](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L81);
[be/compass/organization/bootstrap.py:160](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L160);
[be/compass/organization/bootstrap.py:182](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L182);
[be/compass/organization/bootstrap.py:220](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L220);
[be/compass/organization/bootstrap.py:230](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L230).

**TESTED BEHAVIOR:** existing catalog tests cover exact baseline, idempotency, identity/name repair,
legacy Program FK preservation, relationship-conflict rollback and no name-based merge. See
[validation](validation.md); they verify the old authority contract, not the proposed migration.

## Invocation and canonical-consumer inventory

Read/mutate column concerns institutional data, not merely local report files. Future ownership is
assigned explicitly so a direct-function caller cannot survive a command-only fix.

| File/symbol (source) | Current purpose; read/mutate; overwrite risk | Required future behavior / slice / regression |
|---|---|---|
| [be/compass/organization/bootstrap.py:230](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/bootstrap.py#L230) and `_sync_organization_catalog` | Mutating reconciliation; high overwrite/reactivation/retirement risk | ORG-1 replace public behavior with seed-only compatibility wrapper or retire with clear error; remove destructive private path. Test direct caller and command preserve admin edits |
| [be/compass/organization/management/commands/sync_organization_catalog.py:11](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/management/commands/sync_organization_catalog.py#L11) | Explicit operator command invokes sync; mutates | ORG-1 retain safe deprecated alias to controlled initialization/check, never implicit repair; repeat after edits |
| [be/deploy/staging/deploy.sh:97](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/deploy/staging/deploy.sh#L97) | Every invocation of deployment bootstrap calls command after migrate; mutates | ORG-1 new initialization/check behavior, same on repeats; no overwrite on deployment retry |
| [.github/workflows/deploy-staging.yml:1](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/workflows/deploy-staging.yml#L1) → [.github/scripts/run_staging_deploy.py:202](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/scripts/run_staging_deploy.py#L202) | Manual authorized workflow invokes the Python orchestrator and deployment script; indirect mutation path | ORG-1 verify image/scripts come from compatible revision; synthetic preflight only, no dispatch during ORG-0 |
| [be/compass/staging_seed/seed.py:132](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/seed.py#L132) / `_run` / `seed_staging_dataset` | Direct sync, bypassing command; seed and repeated seed mutate | ORG-1 remove reconciliation call; require/adopt initialized DB, baseline only on explicit fresh fixture installation. Test repeat seed preserves rename/retirement/addition |
| [be/compass/staging_seed/management/commands/seed_staging_dataset.py:84](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/management/commands/seed_staging_dataset.py#L84) | Default/`seed` mode invokes writer; verify/report do not call sync; reports write files | ORG-1 preserve mode distinction; verify/report must remain database read-only |
| [be/tests/test_organization_catalog.py:121](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_organization_catalog.py#L121) | Direct calls mutate synthetic rows; pin 6/10/38 and current repair semantics | ORG-1 retain baseline fixture test, replace repair tests with seed/adoption preservation tests; ORG-4 concurrency |
| [be/tests/test_organization.py:142](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_organization.py#L142) and [be/tests/test_inventory.py:86](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_inventory.py#L86) | Explicit synthetic test setup calls sync | ORG-1 use controlled fixture helper; runtime tests must accept additional Programs |
| [be/tests/conftest.py:7](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/conftest.py#L7) | Autouse sync is **Institutional Forms only**, not Organization | No hidden catalog bootstrap; do not accidentally add global Organization sync |
| [be/compass/organization/canonical.py:225](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L225) | Pure code read/import validation; no DB; expected counts and classes | ORG-1 freeze baseline data/version; counts apply only to seed, never live catalog readiness |
| [be/compass/organization/canonical.py:295](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L295) / `CANONICAL_CAMPUS_CODES` | Pure registry indexes; no external production references found for these two | ORG-1 keep only as seed internals if needed; no request-time whitelist |
| [be/compass/organization/canonical.py:299](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L299) / `CANONICAL_PROGRAM_IDENTITIES` | Derived identity sets; tests pin structure | ORG-1 baseline tests only; approved additions need no Python entry |
| [be/compass/organization/canonical.py:308](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L308) / `canonical_program_metadata` | Exact-code metadata map/function; no DB write, but determines policy | ORG-1 move all live readers to one persisted-policy accessor; freeze map only for data migration |
| [be/compass/organization/api.py:207](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L207) | Read projection; canonical policy overrides no DB field because none exists | ORG-1 DB policy with identical nullable wire shape; canonical/noncanonical read tests |
| [be/compass/inventory/services.py:560](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/services.py#L560) | Read metadata during Inventory writes; can reject academic facts | ORG-1 persisted accessor, same configured/pending compatibility; ORG-4 policy changes |
| [be/compass/good_moral/services.py:452](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L452) | Read policy; rejects unknown/non-Bachelor/unsupported year | ORG-1 persisted accessor and fixed template-supported set; new approved Bachelor test |
| [be/compass/good_moral/api.py:685](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/api.py#L685) | Direct `CANONICAL_CAMPUSES` enumeration, active Bachelor **names**; advisory F6 options | ORG-1 DB-based active-chain Bachelor suggestions, same response type; free text/history preserved |
| [be/compass/staging_seed/verify.py:420](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/verify.py#L420) | Read-only requirement that every seed Program be active | ORG-1 separate synthetic baseline verification from live catalog validity; legitimate retirement must not fail general readiness |
| [be/compass/staging_seed/reports.py:95](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/reports.py#L95) | Code-keyed constant names; read-only DB impact, stale report labels/cross-parent collisions | ORG-1 fetch persisted identity/name or label explicitly frozen scenario data; ORG-4 renamed report test |
| [be/compass/staging_seed/organization.py:80](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/organization.py#L80) / `program_for`; `staff.py`, `students.py` personas | Hardcoded campus/college/program codes resolve fixtures; relationship writes use services | ORG-1/4 retain synthetic persona mappings with parent-qualified identities; fail preflight on unavailable fixture, never reactivate real catalog |
| [be/tests/test_good_moral.py:70](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_good_moral.py#L70) | Builds synthetic Program facts from registry | ORG-1 fixture conversion, add noncanonical approved Program coverage |
| [be/tests/test_openapi_contract.py:1433](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_openapi_contract.py#L1433) | Pins response keys, enum values and Inventory 1–10 domain | ORG-1 compatibility assertion; ORG-2 explicit new contract tests |
| [be/README.md:13](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/README.md#L13), `be/docs/staging-deployment.md`, ADR-064/067/116, `outputs/canon-1*`, reset checklists | Documented/manual replay routes; historical evidence is not executable code | ORG-1 replace current runbook instructions; annotate archived evidence as historical, never use old command semantics during recovery |

`AcademicClassification` and `YearLevelPolicyStatus` are defined in canonical.py and imported by API,
F4 and tests as shown above. Enum vocabulary may move to an Organization policy module without
changing wire values. `EXPECTED_*_COUNT` is local registry validation only. The whole-repository
search, including hidden tracked automation and archived source, found no other production importer
of these identifiers. Frontend consumes the contract values, not Python symbols.


### Hardcoded identities outside direct imports

A separate literal-code scan of current backend/frontend/automation source found additional fixture
coupling in [be/compass/staging_seed/manifest.py:42](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/manifest.py#L42),
[be/compass/staging_seed/content/inventory_data.py:95](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/content/inventory_data.py#L95),
[be/compass/staging_seed/content/narratives.py:193](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/content/narratives.py#L193), and
[be/compass/staging_seed/scenarios/rich.py:341](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/scenarios/rich.py#L341).
The manifest keys pin synthetic UAT allocations; content/scenarios write or describe synthetic
academic/narrative snapshots through domain seed operations, not catalog reconciliation. They cannot
overwrite official catalog names/status, but code/parent restructuring could invalidate persona
lookups or labels. ORG-1/4 must keep them explicitly fixture-owned, preflight unavailable identities,
and use staging-manifest/persona regressions. Do not rewrite saved historical free text after a
catalog rename. No corresponding literal institutional-code whitelist was found in current
frontend/runtime selection logic outside the seed/registry areas. This negative finding concerns
this inspected revision only, not external consumers or deployed scripts.

## Negative-path audit and limits

Inspected `organization/apps.py`, package initialization, WSGI/ASGI/Celery setup, registered migrations,
common canonical-baseline guard, container commands, Compose web/worker/Beat services, GitHub workflows,
management commands, task modules and `CELERY_BEAT_SCHEDULE`. Organization AppConfig has no ready
hook. Organization baseline only creates schema; accounts' pre_migrate receiver checks lineage and
syncs no organization data. Container processes start servers/workers; schema/bootstrap are explicit.
The Beat schedule lists reminders, email/push recovery and media recovery/reconciliation, not catalog
synchronization. No request-time/health sync or HTTP reconciliation endpoint was found.
Sources: [be/compass/organization/apps.py:4](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/apps.py#L4);
[be/compass/accounts/apps.py:10](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/apps.py#L10);
[be/compass/organization/migrations/0001_canonical_baseline.py:18](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/migrations/0001_canonical_baseline.py#L18);
[be/config/settings.py:848](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/config/settings.py#L848); [be/compose.yaml:16](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compose.yaml#L16);
[be/compose.staging.yaml:63](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compose.staging.yaml#L63); [be/config/celery.py:1](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/config/celery.py#L1);
[.github/workflows/backend-targeted.yml:1](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/workflows/backend-targeted.yml#L1); [.github/workflows/backend-full.yml:1](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/.github/workflows/backend-full.yml#L1).

This establishes the checked-in call graph, not the absence of external cron jobs, old binaries,
manual shell commands or direct SQL in deployed environments. Those are **UNVERIFIED DEPLOYED
STATE** and require an authorized operator inventory before cutover. Archived frontend topology
editors are reference-only and not imports in the current frontend; they are not a supported writer.

## Why ordinary CRUD would conflict

| Approved database operation | Next old sync |
|---|---|
| Canonical rename | Restores Python name on same UUID |
| Canonical retirement | Reactivates same row |
| New approved Program | Deactivates it, even when Inventory references it |
| New College with Students/Counselor | Sync raises and rolls back unrelated changes; deployment can fail |
| Code or parent change | New canonical identity can be created, old identity retired/conflicted; no alias resolution |

## Authority alternatives

| Option | Benefit | Cost/risk | Recommendation |
|---|---|---|---|
| A. Keep recurring code authority | Existing deterministic installation | CRUD requires Python approval round trip; dual authority/overwrites remain | Reject for ordinary institutional maintenance |
| B. DB authority + controlled initial seed | Small change around existing identities and services; admin changes persist | Requires complete writer retirement, metadata persistence, recovery rules | **Select** |
| C. DB authority + separately versioned approved imports | Supports a future institutional feed with explicit diff/conflicts | Needs import ownership, approvals, version mapping, dry-run and reconciliation not requested yet | Defer; layer on B only with real feed contract |

**PROPOSED DESIGN:** freeze a seed version and the exact policy backfill in the migration. Add one
initialization receipt (singleton initialized_at, source `SEEDED`/`ADOPTED`, baseline_version nullable)
plus a transaction-level PostgreSQL advisory initialization mutex. This records whether installation
already occurred, including a deliberately emptied catalog, without making Python a live authority.
It is not a runtime CODE/DB switching state machine or protection against unmodified old writers.

| Situation | Safe proposed behavior |
|---|---|
| Empty fresh installation | Explicit initialize command takes mutex, checks all three tables empty/no receipt, creates baseline+policy+receipt+Audit atomically |
| Existing pre-ORG-1 database | Add policy columns/backfill; explicit adoption receipt; no sync repairs, missing-entity insertion or status/name changes |
| Existing modified records | Preserve edits; exact-code match for metadata only; unknowns remain unresolved; report review issues without mutation |
| Ordinary application start | No catalog writes; read initialized data or explicit configuration failure |
| Repeated deployment/init | Existing receipt means validate/report only; never use get_or_create to top up a managed catalog |
| Nonempty database without receipt | Refuse implicit seed; explicit adoption workflow/check, no merge-by-name |
| Intentional baseline correction | Separate reviewed bounded admin correction/import with expected versions and Audit; changing seed constants affects future installations only |
| Disaster recovery | Restore DB+receipt+Audit+compatible image together; do not regenerate UUIDs from a seed |
| Old/new versions coexist | No activation or mutations until old binaries/commands are retired; legacy reads also misclassify new Programs |

Details, rollback and why an ignored database marker is insufficient: [migration](migration-and-rollback.md).
