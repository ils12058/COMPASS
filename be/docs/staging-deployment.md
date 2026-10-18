# Routine canonical staging deployment (COMPASS-DEPLOY-1)

The current Compose/runtime-secret source contract is **25 files**, including the dedicated
non-empty `guidance_followup_encryption_keys` key granted to web only. See
[`runtime-secrets.md`](runtime-secrets.md) for the authoritative list and service grants. RELEASE-UNBLOCK-1 retires the global Follow-Up gate. Before controlled release, verify
ADR-FUP-1A governance, the independent keyring, identity policy and current resource access.
The repository contract does not prove that the host file is present or that UAT is approved.

COMPASS-LIVE-RESET-1 completed on **2026-10-17**. Initial baseline installation required that
separate reset; subsequent deployments **reuse its initialized storage**. No reset, import, seed,
credential issuance, authentication reset, task purge or data-volume deletion belongs in this flow.

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

1. Merge the reviewed change into `staging`.
2. Wait for **Backend full regression** to complete successfully for the resulting exact commit.
3. Dispatch **Deploy staging backend** **from branch `staging`** with `expected_staging_sha` set
   to that full SHA (UI branch selector, or `gh workflow run deploy-staging.yml --ref staging
   -f expected_staging_sha=<FULL_SHA>`). The
   workflow checks out/fetches current `staging` and refuses a moved branch, a different workflow
   revision/ref, or failed/missing CI. The repository default branch is `main`; its historical
   workflow is not updated by this staging-targeted PR. Do not dispatch that old workflow from main.
   Inspection found no environment branch allowlist. Restricting the GitHub staging environment to
   branch `staging`, or separately promoting this workflow to main, is the repository-owner follow-up
   for closing that historical dispatch path; this PR does not change repository settings.
4. The revision must descend from both the canonical baseline and the currently running revision.
   Baseline migration files must match the accepted baseline byte-for-byte. Feature migrations
   extend `0001_canonical_baseline`; never regenerate, fake or edit applied migrations.

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

### Reviewed COMPASS-INT-FINAL exceptions

The following six additive migrations are individually source-digest pinned in
`database_preflight.py`. The exception is limited to these exact files and forward, atomic plans;
editing a reviewed migration changes its digest and fails preflight until it is reviewed again.
It does not permit arbitrary constraints, defaults, `RunPython`, or `RunSQL`:

- `appointments.0002_appointment_reminders` adds reminder revision fields to existing
  appointments and creates new occurrence/batch tables with their indexes and uniqueness rules.
  The existing-row revision value is `1`; reminder dispatch remains disabled by default.
- `guidance_followups.0001_initial` and `guidance_followups.0002_guidancefollowupmutation` create
  new Follow-Up tables and constraints. They do not import or rewrite existing records.
- `group_sessions.0001_initial` creates new Group Session tables, indexes, and constraints.
- `service_catalog.0002_booking_pathways` creates the pathway table and backfills
  `FLEXIBLE_APPOINTMENT` for existing Services whose legacy booking flag is enabled. The reviewed
  backfill reads in batches of 500 and uses conflict-safe inserts; it does not enable new pathways.
- `service_catalog.0003_fixed_date_slots` creates the new fixed-date slot table, indexes, and
  time-order constraint.

### Reviewed CORR-1A/1B lifecycle exceptions (2026-10-18)

Three further migrations from the CORR-1A/1B service-catalog work are source-digest pinned the same
way. They are not additive: each changes Django-level delete behavior and installs PostgreSQL
lifecycle triggers, and `group_sessions.0003` adds constraints that existing rows must satisfy.

- `group_sessions.0002_alter_groupsessionfacilitator_group_session` changes the facilitator's
  Group Session foreign key from `CASCADE` to `PROTECT` (Django-level only; the database constraint
  stays `NO ACTION`) and installs a `BEFORE DELETE` trigger that refuses to delete Group Sessions.
- `group_sessions.0003_group_session_scheduling_and_external_facilitators` keeps the facilitator
  user column (`counselor_id`, renamed in Django only to `internal_user`) and makes it nullable for
  external guests. It adds `schedule_revision` (existing rows `1`), `kind` (`INTERNAL`),
  `external_display_name`, `display_name_snapshot` (backfilled from the user's name), and
  `removed_at`. It replaces the old session/counselor uniqueness with an identity check, an
  active-internal uniqueness rule and **at most one active lead per session**, and installs a
  `BEFORE DELETE` trigger that turns facilitator deletion into `removed_at`.
- `service_catalog.0004_serviceappointmentslot_withdrawn_at_and_more` adds nullable `withdrawn_at`,
  changes the slot's appointment and Service foreign keys to Django `PROTECT`, creates the
  append-only `ServiceAppointmentSlotBooking` history (unique slot/appointment), backfills one
  history row per currently booked slot in batches of 500, and installs triggers that record
  future bookings and refuse slot/history deletion.

Live UAT evidence (read-only, 2026-10-18 UTC 21:19, before any of the three ran): `group_sessions`
was at 0001 and `service_catalog` at 0003; there were 0 Group Sessions, facilitators, registrations
and Fixed Slots; none of the five trigger function names existed; and the booking history table did
not exist. The only data-dependent failure is the active-lead uniqueness in 0003. The deployed code
assigns at most one lead per session (a single lead ID over deduplicated facilitators), so it cannot
arise through the application, only through a manual database edit.

`tests/test_corr_migration_rehearsal.py` rehearses the exact plan on PostgreSQL from the live state
with representative rows (two Group Sessions with one and two facilitators, a registration, a booked
and an open Fixed Slot). It verifies row preservation, the backfilled facilitator and booking history,
each trigger, and the new constraints. It also proves the failure mode: if a session had two leads,
0002 commits, 0003 rolls back completely (no new columns), and the plan continues forward once the
data is reviewed. Because a failed `migrate` stops the deployment after the migration boundary with
application services left stopped, check `SELECT group_session_id FROM
group_sessions_groupsessionfacilitator WHERE is_lead GROUP BY 1 HAVING count(*) > 1` returns no rows
immediately before dispatching a release that contains 0003.

All nine migrations use Django's atomic migration behavior on PostgreSQL. The deployment stops
application producers before applying them and never starts or recreates PostgreSQL or Redis.
Each migration and its migration-history row commit together; an interrupted atomic migration is
rolled back by PostgreSQL, while previously committed migrations remain recorded for forward
recovery. The deployment does not roll back schema or restart an old application image after the
migration boundary. Before the first live rollout of each reviewed plan, rehearse it on a
disposable database with the canonical baseline and representative pre-existing rows; record
row-preservation, resulting backfilled rows, transaction recovery, and observed migration duration
in the execution report. The COMPASS-INT-FINAL six-migration plan was the first such rollout; the
CORR-1A/1B plan's rehearsal is `tests/test_corr_migration_rehearsal.py` (about 7 seconds per full
back-and-forward cycle with its representative rows on a local disposable PostgreSQL 17.11).

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
   database/broker. Preserve whether realtime was active. Run health checks and
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

Merge DEPLOY-1, let exact merged-SHA full regression pass, and dispatch that SHA **using `--ref staging`**.
The earlier DEPLOY-1 inspection and its no-new-secret conclusion predate the Follow-Up source added
to the current manifest. Current deployment preflight requires the 25-source inventory, including
the dedicated Follow-Up key; do not infer host-file presence from that source contract. The CORR-5
read-only attempt could not establish the host file or effective application configuration because
SSH timed out. Provisioning remains a separate authorized operator action. Even after provision, the
secret does not constitute the institutional approval required to enable Follow-Ups. Ensure no
competing deploy/freeze or active work, and retain the normal independent backup policy. CORR-5 made
no deployment, migration, seeding, secret operation, restart or live configuration change.
