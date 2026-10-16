# CANON-1 architecture audit — initial repository-wide inventory

Verified 2026-10-16 (Asia/Manila), base `d353108d1f757386b9020c4d1297e081258d2e4e`.
This report replaces the unverified claims in the recovered audit commit `b06d8379`.
It establishes candidate decisions and safe implementation boundaries. Unresolved candidates are
explicitly REVIEW_REQUIRED; it does not claim exhaustive dead-code proof or completed canonicalization.

## Repository and runtime baseline

- Fetched origin/staging; 2,184 tracked files at the base revision.
- No open PRs at initial inspection. The existing main checkout is on
  `fix/form-ui-1b-form-guidance`; it was not modified.
- Numerous existing worktrees were found, including live-staging-deployment and active feature
  checkouts. Several registered paths no longer exist. None were pruned, removed or overwritten.
  [Inventory](evidence/worktrees.txt).
- A missing CANON worktree still had an audit-only commit on
  `fix/canon-1a-ci-and-regression-baseline`. A new managed worktree was created from that commit
  and continued on `codex/canon-1a-ci-coverage`. The old branch is preserved.
- Public `GET https://staging-api.compass-gco.com/api/v1/meta` was rechecked read-only:
  live-staging still runs `0512e9ec3533f59b9a90038a50b2d5b122b2e5ee`, built 2026-10-11.
  [Response](evidence/staging-meta.json). Worker images, queue contents, external objects and
  database records cannot be inferred from this endpoint and were not inspected live.
- 102 numbered Django migrations across 27 apps, eight frozen migration helper modules,
  28 `*models.py` modules, 117 frontend `page.tsx` files, 355 OpenAPI operations with no duplicate
  operation IDs, 167 backend test files, 29 initial frontend unit files and 31 browser suites.
  Source policy defines five roles, two institutional designations and 78 capabilities.
  Role grants, overrides and effective capabilities still require database validation.

## Supported architecture and audit scope

Django/Ninja owns authorization, lifecycle transitions, encrypted persistence, audits and
notifications. Next.js consumes the committed OpenAPI contract through generated Orval clients
and the shared authenticated transport. Generated frontend clients are ignored by repository
policy; regenerate from the contract and validate consumers rather than committing generated code.
Celery handles asynchronous tasks; Beat schedules work; a separate Django-free realtime service
publishes bounded hints through Redis. Provider/media custody and private storage remain backend-owned.

The migration inventory covers every app: Accounts, Announcements, Appointments, Assessment Records,
Audit, Authentication, Availability, Call Slips, Counseling, Documents, E-Counseling, Exit Interviews,
Feedback, Good Moral, Graduate Tracer, Guidance Messages, Institutional Forms, Inventory,
Notifications, Organization, Platform Operations, Privacy Governance, Referrals, Resources,
Routine Interviews, Service Catalog and Student Support. Projection-only modules (Activity,
Student Actions, Work Queue, Guidance Operations, Overview, Reports), common crypto and integrations
were included in import/candidate scans. App presence is not proof that each operation has been
reviewed for duplication; domain-by-domain service/API/frontend tracing remains a later gate.

The [removal matrix](CANON-1-Removal-Matrix.csv) records explicit classifications, consumer evidence,
security relevance, risks, replacements, affected tests, intended PR and cutover condition.
Keyword-only findings are REVIEW_REQUIRED, never an automatic deletion list. Static imports miss
dynamic dispatch, external consumers and bookmarks; those require runtime/contract evidence.

## Principal findings and decisions

1. **PG-1A is transition-safe, not cutover-complete.** Three retired Celery names are non-mutating
   tombstones. Retired mutation services return 409. Rule/case/hold models remain historical ledgers.
   E-Counseling artifact ingestion, reconciliation and webhook handling query DispositionCase;
   deleting that model without updating these consumers would break custody fences. Keep all
   transition safeguards in this staging-compatible slice. Final elimination belongs on the reset
   integration branch after old workers/Beat, broker redelivery and callbacks are isolated.
2. **Read-only retention oversight is current functionality.** Keep the code-owned policy register,
   DPO authorization and absence of mutation APIs. Disposed artifact markers are distinct from
   the retired executor and may still be needed after reset.
3. **Identity bootstrap mixes canonical sync with transition handling.** The old-name guard refers
   to migration 0006; the retired-capability purge removes grants and user overrides for retired
   codes. Rework empty-baseline transition handling separately while preserving drift detection,
   effective capability semantics and the supported capability-override feature.
4. **Encryption compatibility is not automatically obsolete.** The shared bound Fernet primitive
   supports ordered keyrings and key rotation. Routine's adapter preserves domain binding/error
   semantics. Rotation commands inspect for old plaintext columns before operating. Review each
   wrapper by its callers; no secrets were printed or rotated. Contrary to the recovered audit,
   Inventory and Graduate Tracer runtime schemas do not import their frozen migration helpers.
5. **ServiceProviderRole is a removal candidate with a schema boundary.** Current provider
   qualification uses Counselor coverage and ServiceCounselorProvider. Remove its historical table
   only with reviewed model/consumer tests and schema comparison on the reset branch.
6. **Frontend legacy terms describe different things.** The retired retention wildcard redirect is
   removable after route review. The Platform index redirect is a current default-tab destination.
   Unrecorded Program report buckets, saved Exit Interview variants and historical issuance origin
   enums need separate decisions; their names alone do not make them obsolete. Archived frontends
   remain reference-only under fe/AGENTS.md.
7. **Seeder upgrade history needs a reset-specific pass.** Dataset v2 documents 57 Students
   (11 rich personas plus 46 population Students), not 57 total accounts. `demo-seed-v1` remains an
   intentional additive-upgrade namespace. Keep current safety, synthetic domains, credentials,
   environment opt-in and concurrent-run exclusion. The proposed 85–100 Student expansion is not
   approved by this milestone. Actual seeded counts and rerun evidence remain pending.
8. **CI discovery is incomplete.** Three current backend files are unbundled; eight browser files
   lack package registration and three more are absent from CI regressions. Model paths selected
   only domain suites. CANON-1A repairs these infrastructure defects and lint without changing
   domain rules or accepting application regressions as correct.
9. **Contract reachability needs review, not deletion by name.** All 355 operation IDs are unique.
   Four of 650 schema components have no path-rooted $ref reachability: AssessmentRecordFilters,
   OrganizationRole, StudentActionsQuery and WorkQueueQuery. Query types may be flattened inline;
   each is REVIEW_REQUIRED. [Inventory](evidence/contract-inventory.json) records every operation.
   The task scan identifies 15 shared_task declaration sites ([inventory](evidence/task-inventory.json));
   it is not a claim that Celery built-ins or dynamic registrations are absent.

## Infrastructure and clean-reset boundary

Inspected `.github/workflows/{backend-full,backend-targeted,frontend-targeted,deploy-staging}.yml`,
CI selector and exact-revision deployment guard, `be/compose.yaml`, `be/compose.staging.yaml`,
runtime secret/Redis configuration, existing retention and staging-seeding runbooks, and integration
seams for Daily, email and object storage. Backend full regression has six shards; the final
aggregator checks plan/static/shard results. Deployment requires the exact successful revision.
Those gates are preserved.

Ordinary deployment pulls images, starts PostgreSQL/Redis, migrates and syncs configuration before
replacing the app/worker/Beat containers. Old workers can therefore overlap schema changes.
This procedure is unsuitable for replacement migrations or a tombstone-free release.

The reset design must separately inventory PostgreSQL volumes and bookkeeping; Redis broker,
unacked/ETA tasks, caches, sessions and realtime; every worker/Beat/web/realtime instance; private
and public storage prefixes, uploads, profile images and generated certificates; Daily rooms,
recordings/transcripts and callback credentials/subscriptions; email intents and provider delivery;
backups/snapshots; encryption keyrings and deployment/rollback images. PostgreSQL disposability
confers no disposal permission for those resources. Classification and operator approval are pending.

No live reset procedure has been rehearsed, and no reset automation is introduced here.
See the [PR roadmap](CANON-1-PR-Roadmap.md) for prerequisites and later evidence.

The current-history fresh database was introspected read-only: 98 tables, 981 columns, 557 constraints,
429 indexes and zero user-defined triggers. [Snapshot](evidence/existing-schema.json). It contains
no account/content records or secrets. No canonical schema comparison has yet been performed.
