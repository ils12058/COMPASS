# COMPASS-DEPLOY-1 — Implementation report

Date: 2026-10-17, Asia/Manila. Repository `ils12058/COMPASS`; PR target `staging`.

## Outcome and scope

Restores manually dispatched deployments onto the initialized canonical staging lineage. The
transitional unconditional refusal is replaced by fail-closed source, cloud, host, storage,
configuration, database-history and migration-plan checks. The ordinary path neither creates
storage nor resets/reseeds data. No live deployment, migration, restart, image pull/push, account
change or persistent-resource change was performed during implementation.

The additional name-only environment audit is complete: all five obsolete `DEMO_*` assignments and
`STAGING_SEED_ENABLED` were already absent. No `.env` rewrite or secret rotation was needed.

## Actual read-only runtime findings

| Item | Observed identity/state |
| --- | --- |
| DigitalOcean project | `compass-project`, Staging, `1bb58307-ec9c-4af1-98c4-4177c636e567` |
| Droplet | `602091909`, `compass-staging-api-01`, `157.245.60.65`; verified through DO API and host metadata |
| Firewall | `3d6403c7-9acc-4faf-b6a4-fa5bb092e108`, attached only to that Droplet |
| SSH | Existing `compass` identity and pinned ED25519 known-host key; strict checking enabled |
| Root/project | `/opt/compass`, Compose project `compass` |
| PostgreSQL | `compass_postgres_canonical_d86ddc08`, local, project `compass`, created `2026-10-16T21:31:13Z` |
| Redis | `compass_redis_canonical_d86ddc08`, same creation time and ownership |
| Network | `compass_canonical_d86ddc08`, project `compass`, network key `default` |
| Caddy resources | `compass_caddy_data`, `compass_caddy_config`, original `2026-09-20T05:47:56Z` volumes |
| Current image | Local immutable ID `sha256:5042141ab5d8084208c3cc20f31b8dc999d275c71bee564a84605c14b08bb9f7` |
| Current build | `d86ddc08285f16740848dc5880d9d2285e7dbce8`, consistent web/worker/Beat/realtime |
| Current selector | `COMPASS_IMAGE` local ID; explicit secrets directory; two-file canonical reset Compose selection; realtime profile active |
| Release layout | `/opt/compass/releases/<SHA>`; active baseline manifest plus `compose.live-reset.yaml`; `.env` links to `/opt/compass/.env` |
| Legacy fencing | Old release manifests remain `.PRE_CANONICAL_FENCED`; previous selector refuses pre-canonical rollback |
| Database | 41 applied migrations, including all 26 canonical baselines; 113 accounts still present |
| Services | Healthy web, PostgreSQL, Redis, realtime and proxy; running worker and one Beat |
| Beat | Existing four recovery jobs: media artifact, notification push, notification email, email-change alerts |

All canonical-volume consumers and network members were verified. The new manifest's rendering and
host guard were exercised read-only on this actual destination, using a protected temporary
directory that was removed afterward. No live release manifest was installed/overwritten. Running
container identities were identical before/after validation. Metadata access used the DO metadata
endpoint; the unprivileged SSH user could not read the DMI UUID, which was not required.

## Implementation

- `compose.staging.yaml`: fixed external names for all four existing volumes and the canonical
  network, independent of image SHA/project defaults; app images use explicit pull control.
- `run_staging_deploy.py`: exact DO project/Droplet/firewall verification, owned temporary IPv4 `/32`
  lease, pinned SSH, non-overwriting exact-source staging, current/candidate ancestry checks,
  digest-based rollout, retries only for byte-identical files, and credential/firewall cleanup.
- `host_preflight.py`: original volume identity/creation/ownership, actual mounts/exclusive consumers,
  network/project/health, immutable selector and mixed-revision checks, exact database/broker
  endpoints, initialized canonical history, and PostgreSQL/Redis infrastructure-drift refusal.
- `database_preflight.py`: candidate-side read-only database inspection, immutable baseline file
  hashes, known/consistent applied migrations, forward-only atomic migration allowlist, retired
  ledger/task refusal, preservation of current Beat jobs, and idle worker/broker inspection.
- `deploy.sh`: host lock and revalidation, stop producers then drain/warm-stop worker, fence old
  restart policies, recheck migration plan, migrate/synchronize/check with old consumers stopped,
  update only app/proxy services with `--no-deps`, preserve realtime, verify health/noop and exact
  public/actual image identities before publishing the canonical selector. No automatic rollback.
- Workflow retains exact-SHA full-regression gating, immutable OCI build metadata, short-lived
  registry authentication, runtime-secret checks and independent public identity verification.
  Existing registry SHA tags are reused without rebuilding/overwriting their metadata; future
  selectors use `<SHA>@sha256:<digest>`. The local baseline image needs no registry conversion.
- Runtime-secret checker additionally rejects obsolete demo assignment names. Active secrets,
  keyrings, credentials and secret filenames are unchanged.
- Updated ADR-116's accepted/operational status, current staging/seeder/README instructions and
  historical retention runbook pointer without deleting the historical transition record.

Routine migration operations are intentionally conservative: `CreateModel`, `AddIndex`, and nullable
non-primary-key `AddField` without Python/database defaults. Alter/rename/delete/data/custom,
non-atomic/backward/conflicting or unknown history requires a separately reviewed coordinated
procedure. No bypass switch is provided. Failure before migrations can resume the exact old
containers; after the migration boundary the application stays stopped for canonical forward
recovery, preserving PostgreSQL/Redis and UAT state.

## Environment cleanup result — names only

Inspected these assignment names in `/opt/compass/.env` and the running web, worker, Beat and
realtime environments:

- `DEMO_SEEDING_ENABLED`
- `DEMO_ACCOUNT_PASSWORD`
- `DEMO_ACCOUNT_PASSWORD_FILE`
- `DEMO_EMAIL_DOMAIN`
- `DEMO_ONBOARDING_EMAIL`
- `STAGING_SEED_ENABLED`

All absent. Atomic update was therefore unnecessary. Existing UID/GID/mode and unrelated contents
were preserved. The existing runtime-secret metadata checker passed afterward; the updated checker
also passed during candidate validation. No `.env` contents, value diff, keyring, token, password,
provider URL or private record was printed, logged or committed. Participant/UAT credentials and
all seeded records were untouched.

The audit helper was capable of removing only the named obsolete assignment lines with a
same-directory atomic replacement, original ownership/mode, fsync and concurrent-update checks;
that write branch was not exercised because the environment was already clean.

## Validation

- **54** `.github/scripts` unit/self-tests passed, including destination mismatch, volume replacement,
  ownership/exclusive consumers, immutable selector parsing, endpoint redirection, migration-baseline
  hashes, cloud identity, exact owned-rule cleanup, preserved preexisting access and ordering guards.
- **99** focused backend tests passed: deployment migration operations, runtime-secret handling,
  and both Docker Compose delivery contracts. The standalone local `docker-compose` CLI rendered
  synthetic configurations; no daemon or live secret values were needed.
- Actual Droplet Docker Compose configuration validation and host preflight **passed read-only**.
- Rendered a different project and candidate image: canonical volume/network selections remained
  identical. The actual guard then rejected the incorrect project. No resource was created.
- Migration allowlist tests cover permitted additive operations and refusal of destructive/custom,
  data, required/defaulted-field, non-atomic and backwards operations.
- Actionlint **1.7.12**, Bash syntax, Ruff formatting/lint, and `git diff --check` passed.
- Original 26 canonical baseline migration files are unchanged. CI bundle/shard mapping includes
  the new deployment migration test.
- Temporary SSH `/32` access was removed after every inspection; original firewall rules remained.

An initial guard comparison rejected Compose v5's extra empty `ipam` normalization object; validation
now checks the explicit network identity/external contract and has a regression case for that
representation. Initial local CI self-tests also found only generated cache remnants under the
retired demo module; those cache-only files were removed locally, with no tracked source change.

Not performed: deployment workflow dispatch, production-style image build/push/pull, live migration,
worker quiescence/restart, full authenticated browser UAT, reseeding, credential issuance, external
provider actions or storage operations. The coordinated rollout is source/order validated and is
not represented as an executed live rollout. GitHub PR CI runs separately; the first merged staging
commit still must pass its exact full backend regression before deployment.

## First post-reset deployment prerequisites

1. Review/merge this PR into `staging`; wait for **Backend full regression** to pass for that exact
   merged SHA.
2. Dispatch from **branch `staging`**, with the same full `expected_staging_sha`, for example:
   `gh workflow run deploy-staging.yml --ref staging -f expected_staging_sha=<MERGED_SHA>`.
   Both the workflow ref/SHA and current staging tip must match.
3. Choose a short coordinated UAT outage window, allow active work to finish, and ensure no operator
   freeze or competing deployment/restore is active. Do not issue credentials or seed from deployment.
4. No new environment variable, volume, network, secret provisioning or baseline-image upload is
   required for the verified target. Continue the independent backup policy; no backup was created,
   removed or restored by this task.
5. The repository default is `main`, and the staging environment currently has no branch allowlist.
   This staging-targeted PR does not update main's historical workflow or repository settings.
   **Do not dispatch from main.** Restricting the staging environment to branch `staging`, or a
   separately reviewed promotion of the updated workflow to main, is the owner follow-up to close
   that historical dispatch path. The new workflow itself rejects a non-staging ref.

No application source, schema, dataset, authentication state or live persistent resource was changed.
