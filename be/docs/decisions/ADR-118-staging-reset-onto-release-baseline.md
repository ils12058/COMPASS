# ADR-118: Staging reset onto the release baseline

- Status: Accepted provisional Phase E owner decisions; implementation does not authorize a live run.
- Date: 2026-11-09
- Supersedes in part: ADR-117's blanket deploy refusal and ADR-116's runtime/database lineage.
- Preserves: immutable schema/manifests, every feature, keyring, policy and Dataset v1 contract.

## Decision

1. Keep `compass_postgres_canonical_d86ddc08`, `compass_redis_canonical_d86ddc08`,
   `compass_caddy_data`, `compass_caddy_config` and `compass_canonical_d86ddc08`, with the existing
   pinned identity, timestamps and labels. Empty PostgreSQL and Redis in place; recreate all
   containers from the new manifest. Preserve Caddy TLS data. Never create/delete storage resources.
2. Dump/export/restore nothing. Leave external objects, Daily resources and Droplet backups untouched
   under ADR-116; no old data enters the new database. Discard old queued work without a drain.
3. Pin routine lineage to `385c074dfe6a38d89363f123c51307ab7d65dfbc` in runner and host preflight.
   Old runtime ancestry and old migration history independently refuse routine deployment.
4. Promote reviewed integration to staging by fast-forward, preserving SHAs; leave main alone.
   Every operation requires successful Backend full regression on the exact promoted SHA;
   a PR run with that head SHA counts. Dispatch the workflow from staging.
5. Add `deploy` (default), `reset-preflight` and `reset`. Reset requires the exact
   `RESET STAGING <first 12 lowercase SHA hex>` phrase and a lowercase DNS dataset domain;
   both reset operations require catalog action `check`. Deploy refuses nonempty reset inputs.
6. Before any drop, verify resource identity, no freeze, free host lock, runtime source metadata,
   candidate settings without database tags, and realtime Origins. Inspect migration class and counts
   using SELECT only. The candidate image pull and temporary settings-check container are explicit
   preflight exceptions to read-only Docker inspection; they never alter existing runtime or data.
7. Lock, compare the unlocked/locked snapshots, verify the image, stop/remove apps, recreate database
   and clear Redis, recreate storage, bootstrap, seed and verify, start apps, smoke/health/image check,
   publish the atomic single-file selector, validate routine preflight, then write a mode-0600 receipt.
   No automatic rollback. Before the destructive boundary preserve the running old apps; afterwards
   disable restart policies and keep apps stopped on failure.
8. Recovery uses a protected mode-0600 checkpoint bound to SHA, digest and domain. Only a confirmed
   reset retry for that exact candidate may accept its incomplete release graph or unavailable
   storage, restoring only storage containers on already verified pinned resources before repeating
   the complete reset. Ordinary preflight still refuses incomplete/unknown history. Other candidates
   and changed resource identity are refused. This resolves partial-step recovery without a general
   history/health bypass. The checkpoint is cleared only after durable receipt creation.
9. Counts come from the candidate's manifest and strict `seed_staging_dataset verify`, including E5's
   allocation. Only seed/verify one-offs receive `STAGING_SEED_ENABLED=true`. Reuse the reported email
   domain. Optional `STAGING_SEED_ONBOARDING_EMAIL` travels in SSH stdin/transient environment; if
   absent, continue and report its absence. Do not log its value or persist it in runtime configuration.
10. No password setting or credential issuance in automation. After freeze and separate approval,
    issue credentials on the host for exactly the allocated manifest accounts; IT Administrators
    enroll TOTP at first sign-in. Independent keyrings and all authorization policies stay intact.
11. Freeze later with annotated tag `evaluation-freeze-2026-11` on the deployed SHA and a freeze
    record. During Evaluation staging receives only owner-approved fixes. No host freeze file.
12. Schema and API contract are frozen. This package changes no models, migrations, release manifests,
    frontend or seeder. Full regression remains CI's responsibility; local verification is targeted.

## Consequences and operator defaults

The current Compose source declares the documented 25-source inventory plus Handoff (26 sources).
Use the actual checker/grants, and require non-empty independent Handoff and Follow-Up rings before
reset. Domains have multiple DNS labels, a nonnumeric final label and the seeder's maximum length;
no URLs, uppercase, IP literals, wildcards or trailing dots. Reset-preflight allows an empty domain
for discovery and refuses a destructive confirmation. No existing network creation timestamp is
pinned in the source: inspect and compare its actual creation/identity across the lock boundary and
recovery checkpoint, without inventing a pin or replacing the resource.

[Staging deployment](../staging-deployment.md) contains operation inputs, sequence, failures and
recovery. Receipts contain only names/counts, SHA/digest, verification results and UTC timestamps.
Local unit tests and disposable PostgreSQL/Redis rehearsals cannot establish real host configuration,
live recovery, provider behavior, frontend readiness, human UAT or permission to deploy.

Before crossing the destructive boundary, reset also requires the manifest's pinned PostgreSQL,
Redis and proxy images to be present locally for `--pull never`. It never silently pulls them after
a drop. If missing, the operator must resolve image availability under separate live authorization.
A checkpoint-bound recovery may fence/remove a leftover web one-off only when its image matches
the exact candidate, its name/labels are Compose-owned, and its mounts/network are canonical.
Foreign one-offs remain refused; no unrelated process or provider operation is purged.

Canonical classification includes the known Group Sessions and Follow-Up `0001_initial` additions
alongside the old canonical baselines; these were proven by the origin/staging local rehearsal.
Other unknown initial histories and mixed release/canonical histories remain refused.
