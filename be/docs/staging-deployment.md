# Staging deployment and Phase E reset (ADR-118)

The current Compose/runtime-secret source contract contains the **25-source inventory plus the
web-only Handoff source (26 declared sources)**, including the dedicated
non-empty `guidance_followup_encryption_keys` key granted to web only. See
[`runtime-secrets.md`](runtime-secrets.md) for the authoritative list and service grants. RELEASE-UNBLOCK-1 retires the global Follow-Up gate. Before controlled release, verify
ADR-FUP-1A governance, the independent keyring, identity policy and current resource access.
The repository contract does not prove that the host file is present or that UAT is approved.

COMPASS-LIVE-RESET-1 completed on **2026-10-17**. Initial baseline installation required that
separate reset; subsequent deployments **reuse its initialized storage**. No reset, import, seed,
credential issuance, authentication reset, task purge or data-volume deletion belongs in the
**routine deploy operation**. Phase E uses the separate reset path below.

## Phase E reset

[ADR-118](decisions/ADR-118-staging-reset-onto-release-baseline.md) replaces the blanket workflow
refusal with an explicit reset operation and the new release lineage
`385c074dfe6a38d89363f123c51307ab7d65dfbc`. The old runtime fails that ancestry gate and its
`0001_canonical_baseline` database fails the routine release-history gate independently.
Ordinary deploys are accepted only after the reset. This tooling has been rehearsed locally;
no real host reset or readiness is established by its implementation.

Promote the reviewed integration SHA to `staging` by **fast-forward**, preserving its exact SHA.
Leave `main` and its historical workflow alone. A successful **Backend full regression** on that
exact SHA is mandatory for every operation; the PR's own run counts. Dispatch from `staging`.

| Input | Contract |
| --- | --- |
| `operation` | `deploy` (default), `reset-preflight`, or `reset` |
| `expected_staging_sha` | Full SHA of the reviewed, promoted staging revision |
| `organization_catalog_action` | `check` for both reset operations |
| `confirm_reset` | `reset` only: exactly `RESET STAGING <first 12 lowercase SHA hex>` |
| `dataset_email_domain` | Required for reset: plain lowercase DNS domain, reused from preflight |

`deploy` refuses filled reset inputs. `reset-preflight` refuses a confirmation phrase; its domain
may be empty for discovery. Supplied domains are validated for both reset operations. The optional
staging environment secret `STAGING_SEED_ONBOARDING_EMAIL` reaches reset one-offs via SSH stdin and
transient environment only. Its value is never an argument, log, receipt, or persisted configuration.
If absent, the reset says so and seeds without onboarding delivery. Automation never issues passwords.

1. Stage the exact release under `/opt/compass/releases/<SHA>` and acquire short-lived image-pull
   credentials. `reset-preflight` checks the Droplet/root, free host lock and absent freeze file,
   pinned storage/labels/timestamps, exclusive container mounts and read-only database history.
   It reports database class, migration/account counts, synthetic email domains, safely readable
   selector revision and realtime state. It also validates runtime-source metadata, realtime Origins,
   and candidate `check --deploy` **without database tags**. This transient candidate configuration
   probe and candidate image pull are the only Docker changes; the existing runtime is untouched.
2. `reset` checks candidate ancestry and rechecks the staging tip, then takes
   `/opt/compass/.live-reset.lock` with `flock -n`. Repeat the preflight and refuse any snapshot drift.
   Pull and verify the immutable candidate image and configuration before the destructive boundary.
3. Write a mode-0600 content-free checkpoint tied to SHA/image/domain, disable app restart policies,
   stop and remove proxy, web, worker, Beat and realtime. Old work is discarded without draining.
4. Through the running storage containers, execute `DROP DATABASE … WITH (FORCE)` and
   `CREATE DATABASE … OWNER …` using PostgreSQL's own DB/user, and `FLUSHALL` using the Redis
   entrypoint's password-file normalization. Keep all four existing volumes and the network.
   Recreate PostgreSQL and Redis from the new manifest with `--no-deps --force-recreate --pull never`
   and wait for health. Caddy's TLS volumes and all runtime secret values remain intact.
5. Run, with no pulls or dependencies: migrate, identity policy, Services, institutional forms,
   Organization `--seed --reference reset:<SHA>`, Organization `--check`, migration check, deployment
   database check, Dataset v1 `seed`, then strict `verify`. Only the last two get a transient
   `STAGING_SEED_ENABLED=true`. Counts come from the candidate manifest, including E5's allocation.
6. Start every app/proxy with the routine wait settings, run worker smoke, and verify public metadata
   plus each actual app image. Publish the shared atomic **single-file** selector and previous-selector
   refusal. Run the routine host preflight against the resulting release database.
7. Write and print `/opt/compass/operator/resets/<SHA>-<UTC>.json`, mode `0600`: SHA, image digest,
   original database class, before/after counts, verification section counts and UTC timestamps.
   The checkpoint is cleared only after durable receipt creation.

A pre-boundary failure leaves the old runtime running. A failure once the app fence starts keeps app
services stopped, disables automatic restarts and retains the checkpoint. There is **no rollback**.
Rerun `reset` with the same SHA, image and domain for recovery; it repeats the complete clean rebuild.
The protected checkpoint admits only this reset's incomplete release history or unavailable storage;
a normal `reset-preflight` remains strict. On such a retry only, restore missing/stopped storage
containers from the already verified candidate on the same pinned resources before repeating the SQL.
Unknown or mixed history and changed resources remain refused. A stale `.next` state write can be
replaced only when it is a regular mode-0600 file owned by the operator.

The reset never dumps, exports, imports or restores data; never creates/deletes volumes or networks;
never touches object storage, Daily resources or Droplet backups; never rotates keys, resets a role
password, issues participant credentials or modifies `.env`. Provider/object remnants stay untouched
under ADR-116. Freeze and later credential issuance require separate owner go-aheads.

## Release catalog initialization boundary

The old Organization upgrade/backfill is retired. `organization.0001_release_baseline` now creates
`CatalogInitialization` and the current catalog fields. Its guard migration installs the year-level
function before the policy CHECK. The entire graph is immutable and reset-only; no baseline or guard
migration is a routine `REVIEWED_MIGRATIONS` exception.

For a fresh release database, synchronize identity policy, Services and institutional forms, then
run `initialize_organization_catalog --seed`. This is explicit bootstrap configuration, never a
migration side effect. On an already compatible initialized release database, catalog action
`check` remains the default; an approved compatible catalog may use deliberate `adopt`. Old-history
staging is never adopted into the release graph and requires the separate Phase E reset.

The deployment script retains stop/restart fences and catalog receipt checks. Phase D does not
execute the workflow or inspect live staging. The historical destination contract below records
the earlier verified environment; Phase E must verify and preserve these resources while establishing the new database/runtime lineage
before normal deployment resumes.

## Verified destination and stable resources

Read-only inspection on 2026-10-17 confirmed:

| Resource | Required identity |
| --- | --- |
| Project | `compass-project`, `1bb58307-ec9c-4af1-98c4-4177c636e567` |
| Droplet | `602091909`, `compass-staging-api-01`, `157.245.60.65` |
| Firewall | `3d6403c7-9acc-4faf-b6a4-fa5bb092e108`, attached only to that Droplet |
| Host / Compose project | `/opt/compass` / `compass` |
| PostgreSQL volume | `compass_postgres_canonical_d86ddc08`, created `2026-10-16T21:31:13Z` |
| Redis volume | `compass_redis_canonical_d86ddc08`, same creation timestamp |
| Network | `compass_canonical_d86ddc08`, Compose project `compass`, network key `default` |
| Caddy volumes | `compass_caddy_data`, `compass_caddy_config`, created `2026-09-20T05:47:56Z` |
| Secrets | `/opt/compass/secrets`; pointer-only runtime `/opt/compass/.env` |

The `d86ddc08` suffix is a **fixed storage-lineage identifier**, never the candidate image SHA.
`compose.staging.yaml` declares all four volumes and the network as external with exact names.
Missing resources fail; they are never implicitly created. The host guard also checks original
creation timestamps, Docker ownership labels, actual container mounts, exclusive consumers,
network membership, health, deployment selection and initialized migration history. Familiar
container names alone do not establish ownership.

At inspection all app services ran baseline `d86ddc08285f16740848dc5880d9d2285e7dbce8` via local image
`sha256:5042141ab5d8084208c3cc20f31b8dc999d275c71bee564a84605c14b08bb9f7`. Its selector uses
`compose.staging.yaml:compose.live-reset.yaml`. The first successful normal deployment writes a
single-file selector for the new stable Compose manifest. The old overlay/release is not edited.
The live database had 41 applied migrations (26 canonical COMPASS baselines) and 113 accounts.
These counts are observations, not fixed gates that could reject legitimate future UAT activity.

## Dispatch and image identity

1. Fast-forward `staging` to the reviewed integration head; preserve the exact SHA and leave `main` alone.
2. Require a successful **Backend full regression** for that exact commit; its PR run counts.
3. Dispatch **Deploy staging backend** **from branch `staging`** with `expected_staging_sha` set
   to that full SHA (UI branch selector, or `gh workflow run deploy-staging.yml --ref staging
   -f expected_staging_sha=<FULL_SHA>`). The
   workflow checks out/fetches current `staging` and refuses a moved branch, a different workflow
   revision/ref, or failed/missing CI. The repository default branch is `main`; its historical
   workflow is not updated by this staging-targeted PR. Do not dispatch that old workflow from main.
   Inspection found no environment branch allowlist. Restricting the GitHub staging environment to
   branch `staging`, or separately promoting this workflow to main, is the repository-owner follow-up
   for closing that historical dispatch path; this PR does not change repository settings.
4. A routine deploy must descend from both `385c074dfe6a38d89363f123c51307ab7d65dfbc` and the currently running revision.
   Baseline migration files must match the accepted baseline byte-for-byte. Feature migrations
   extend the immutable `0001_release_baseline`, links and guard graph; never regenerate, fake
   or edit applied migrations. Reset skips only the incompatible old-runtime ancestry check.

GitHub Actions builds the amd64 backend from the reviewed SHA and OCI revision/version/build-time
metadata. A SHA tag already in the registry is reused after metadata validation, never overwritten
by a rerun. The actual selector is `registry.digitalocean.com/compass/compass-backend:<SHA>@sha256:<digest>`.
The current local baseline image remains valid for destination checks; it need not be pushed or
retagged. The first normal release is a **new merged SHA**, not a rebuild of the baseline tag.

The workflow uses existing environment variables/secrets, pinned SSH known-host material and
short-lived registry credentials. It validates project/Droplet/firewall ownership before granting
TCP/22 from the runner's actual public IPv4 `/32`. Preexisting access is not removed. A process
cleanup handler and an `always()` fallback revoke only the rule this run owns. HTTP/HTTPS and all
other firewall rules are preserved. Hard loss of the runner can interrupt any cleanup mechanism;
check the saved lease/rule before manually removing only that run's source if needed.

## Guarded rollout and migration policy

A new release is staged in `/opt/compass/releases/<SHA>` without overwriting active manifests.
A retry accepts only byte-identical staged files. A healthy, already selected identical image is
a no-op. Different content/digest for the same SHA or an incomplete staging directory requires
operator review rather than overwrite. The host lock `/opt/compass/.live-reset.lock` excludes
competing coordinated work; `/opt/compass/.deployment-freeze` blocks normal deployment.

Before runtime changes, the workflow verifies external resource identity/existence and compares
PostgreSQL/Redis service configuration with the current rendered configuration. Infrastructure or
Redis-start-script changes require a separate coordinated review. Normal rollout **does not pull,
recreate, restart or upgrade PostgreSQL/Redis**. Docker resources are checked again under the host
lock; candidate database inspection runs in a PostgreSQL read-only transaction.

Only forward atomic migrations containing these operations enter the routine path:

- `CreateModel`;
- nullable, non-primary-key `AddField` without Python/database defaults;
- `AddIndex`.

Destructive/alter/rename operations, required fields, data migrations (`RunPython`, `RunSQL`),
custom operations, state/database separation, conflicts, unknown applied migrations and non-atomic
or backward plans fail **before downtime**. There is no bypass input. Plan and separately review a
coordinated migration procedure for those changes, including preservation of UAT data and queued
work; do not weaken this guard to push a release through.

### Immutable release schema and future migrations

The release has 36 immutable files across 29 apps: one `0001_release_baseline` per app,
Appointments' Django-generated `0002_release_baseline_links`, and six `0002_database_guards`
files (Counseling, Good Moral, Group Sessions, Organization, Referrals and Service Catalog).
`baseline-sha256.json` and `canonical_migrations.json` pin every file. `additive_migrations` is
empty at release; later features explicitly register ordinary additions.

The guard files reproduce the final catalog definitions, including unconditional Good Moral
Official Receipt guards, Group Session and facilitator deletion protections, Fixed Slot booking
history and deletion protections, immutable Referral provenance/administration, and Organization's
year-level validation function. Counseling preserves three historical constraint identities and
their backing indexes. The Organization CHECK that calls the function runs after its creation.
The code-owned function/trigger list in `tests/test_canonical_baseline.py` prevents silent loss
in a future squash. [ADR-117](decisions/ADR-117-release-baseline.md) lists each app's files.

All prior coordinated migration exceptions are retired. The routine preflight refuses every
release baseline, link and guard migration even if someone adds a source-digest exception.
A candidate must find every immutable release migration already applied and no unknown COMPASS
history. `organization.0001_release_baseline` creates `CatalogInitialization`; its migration record
and receipt table must agree. Explicit fresh bootstrap synchronizes identity policy, Services and
institutional forms, then initializes the empty Organization catalog with `--seed`. Migrations
perform no configuration writes or data backfills. Existing old-history databases are refused.

Phase E performs the reset through its separate approved procedure. Afterwards normal releases
use only the forward policy above; any future exception needs exact source review, disposable
migration rehearsal, recorded row-preservation and transaction-recovery evidence. No baseline
file is regenerated and no old-history database is made compatible by faking records.

Order for an accepted routine release:

1. Stop proxy/web, Beat and active realtime; allow current requests to finish. Keep the worker
   alive to drain. Inspect active/reserved/scheduled work by counts only and check broker lists and
   unacknowledged messages without printing arguments. Work remaining or a nonresponsive worker
   aborts the release; nothing is purged or force-killed.
2. Warm-stop the worker, confirm all old application containers stopped, and disable their restart
   policies before the schema boundary. Recheck the candidate migration plan.
3. Run `migrate --noinput`, the four canonical synchronizers, `migrate --check`, and Django
   deployment/database checks. No old web/worker/Beat remains running during these operations.
4. Start only application services/proxy with `--no-deps --pull never`; reuse the already healthy
   database/broker. Start realtime with the other app services. Run health checks and
   `compass_doctor --worker-smoke --worker-timeout 10` (harmless diagnostic task).
5. Confirm actual app image revisions and public `/api/v1/meta` application, environment, SHA,
   version and build time; only then publish the new selector. Independently check public identity
   from the GitHub runner. Remove registry credentials and temporary firewall access.

This creates a short coordinated service outage. Before dispatch, choose an appropriate UAT window
and allow ongoing work to finish. There is one Beat instance. Its four existing 60-second recovery
jobs remain; configured optional media-reconciliation/replay jobs are not toggled by deployment.
Realtime continues to receive only Redis configuration and allowed Origins.

## Failure and rollback fencing

A failure before migrations resumes precisely the old stopped application containers and their
normal restart policy. After entering migrations, a failure keeps application services stopped;
PostgreSQL/Redis remain intact. No automatic database or image rollback occurs, even if an earlier
migration committed successfully. Resolve with a reviewed canonical forward recovery; a failed
post-migration state is intentionally refused by the normal destination-health preflight.

Pre-canonical manifests stay `.PRE_CANONICAL_FENCED`; old volumes stay absent. The previous selector
remains a refusal, not a shell command that can resurrect pre-baseline code. Do not restore old
snapshots/backups, reenable old containers or source archived image selections against canonical
storage. Legitimate recovery of current UAT data is a separately reviewed operation.

## Environment and UAT preservation

The DEPLOY-1 name-only audit found none of `DEMO_SEEDING_ENABLED`, `DEMO_ACCOUNT_PASSWORD`,
`DEMO_ACCOUNT_PASSWORD_FILE`, `DEMO_EMAIL_DOMAIN`, `DEMO_ONBOARDING_EMAIL` in the live `.env` or
application container environments. `STAGING_SEED_ENABLED` was also absent. No `.env` update was
needed; ownership, permissions, all active keyrings and credentials were untouched. The metadata
checker passed. It now rejects these obsolete names as well as a persistent staging opt-in.

Future cleanup must inspect names only. If obsolete assignments occur, remove only those lines
using an atomic same-directory replacement with original UID/GID/mode and concurrency checks;
never print/diff/copy the environment into logs, rotate active secrets or restart services solely
for cleanup. Staging opt-in and credential handoff inputs remain one-off operator settings.

Normal deployment synchronizes code-owned configuration but never seeds or verifies pristine UAT
scenario states, issues credentials, changes passwords, clears sessions, or resets records. The
existing seeder's strict verification can legitimately report evaluator-modified scenarios; it is
not a normal deployment gate. Participant credentials and email/media-enabled UAT remain separate
owner decisions under [the dataset runbook](staging-dataset-v1.md).

## First post-reset prerequisites

- [ ] Reviewed integration head promoted by fast-forward, with successful exact-SHA Backend full
  regression (the PR run counts); every dispatch uses `--ref staging`.
- [ ] Name-only host audit of the 25-source runtime inventory **plus the Handoff source** (26 declared
  sources). Required pointers, permissions, ownership and service grants pass the current checker.
  Historical 25-file wording does not prove current host provisioning.
- [ ] Independent, non-empty Handoff and Follow-Up keyrings, with approved custody/recovery and
  institutional policy decisions; preserve all active keys and previous key order.
- [ ] Host `COMPASS_PORTAL_ORIGIN` is the approved canonical HTTPS frontend origin.
- [ ] `REALTIME_ALLOWED_ORIGINS` is set for the realtime service, and Vercel
  `NEXT_PUBLIC_REALTIME_URL` is configured to the public realtime WebSocket endpoint.
- [ ] Read-only reset preflight recorded; operator reuses its dataset email domain and has reviewed
  the optional onboarding-delivery choice. No competing host operation or freeze file exists.
- [ ] Owner separately authorizes the live reset, then the ordinary no-op deploy, frontend deploy,
  smoke checks and freeze. Freeze uses annotated tag `evaluation-freeze-2026-11` and a record;
  no host freeze file is created. Evaluation accepts only owner-approved staging fixes.
- [ ] After freeze and a separate authorization, issue credentials on the host only for the manifest's
  allocated accounts. Seeded IT Administrators enroll TOTP and save recovery codes at first sign-in.

Earlier DEPLOY-1/CORR-5 observations are historical. Current source/configuration checks must pass
before any drop; source code, synthetic rehearsal and a green PR do not establish live UAT readiness.

Before crossing the destructive boundary, reset also requires the manifest's pinned PostgreSQL,
Redis and proxy images to be present locally for `--pull never`. It never silently pulls them after
a drop. If missing, the operator must resolve image availability under separate live authorization.
A checkpoint-bound recovery may fence/remove a leftover web one-off only when its image matches
the exact candidate, its name/labels are Compose-owned, and its mounts/network are canonical.
Foreign one-offs remain refused; no unrelated process or provider operation is purged.

Canonical classification includes the known Group Sessions and Follow-Up `0001_initial` additions
alongside the old canonical baselines; these were proven by the origin/staging local rehearsal.
Other unknown initial histories and mixed release/canonical histories remain refused.
