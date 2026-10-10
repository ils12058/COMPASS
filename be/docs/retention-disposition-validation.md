# Operational retention and disposition implementation report

Date: 2026-10-04. Repository: `ils12058/COMPASS`. This is a reviewable implementation; no production
migration, adopted retention schedule, production disposition, merge or deployment is claimed.

1. **Base:** latest fetched `origin/staging`, `d63d9d023a836390f30245730cd29215b57c9b93`.
2. **Branch:** `codex/operational-retention-disposition` in the dedicated managed worktree.
3. **PR:** one PR against `staging`; intentionally left unmerged. Its URL is supplied with delivery.
4. **ADR:** [ADR-072](decisions/ADR-072-operational-retention-and-disposition.md), proposed, explicitly
   refines/supersedes ADR-069's operational boundary while preserving its historical text.
5. **Capabilities:** `privacy_governance.retention.view`, `.manage`, `.approve`. Manage and approve
   depend on view; only DPO designation receives baseline grants. Effective overrides still apply.
   No underlying domain-content capability is granted.
6. **Supported categories:** `GRADUATE_TRACER`, `ECOUNSELING_RECORDING`, `ECOUNSELING_TRANSCRIPT` only.
7. **Actions:** `ANONYMIZE` for Graduate Tracer; `DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE` for each media
   category. There is no generic DELETE executor.
8. **Eligibility:** Graduate Tracer requires identifiable SUBMITTED schema-v1, `submitted_at` plus
   approved whole elapsed days. Media requires READY, known stored provider artifact, reached room
   expiry and `ready_at` plus approved whole elapsed days. One day is exactly 86400 seconds in UTC.
   An ACTIVE rule must have reached its institutional `effective_on` date; source/rule revisions and
   holds are rechecked before approval and execution. No active rule means no treatment.
9. **Approval/MFA:** one case freezes one source and exact rule revision. Normal authorization for
   drafts/holds; recent MFA for activation, retirement, approval and retry. Canonical setup/verify
   refusals are preserved. Verification never replays the consequential action. Stale review is
   closed/rejected and requires re-review; conflicting draft input is preserved.
10. **Holds:** management authority can place/release a bounded administrative reason with provenance.
    Placement cancels queued approval. Release never reapproves. PROCESSING/COMPLETED cannot be
    stopped by a hold; retirement also conflicts with an in-flight operation.
11. **Graduate Tracer map:** the exact field-by-field table and all 20 retained analytical names are
    in ADR-072. Student FK becomes NULL; original UUID/row and all education/exam/training children
    are removed. A new independent UUID preserves only the report contribution. All identity,
    birthdate, detailed location, free text and unused analytical arrays are emptied. Submission and
    operation timestamps are coarsened to institutional calendar days. No old/new ID map is stored.
    A separate Student/schema/day participation marker prevents repeat participation without a
    response/case/anonymous-row relationship. Identifiable APIs exclude anonymous contributions;
    self-service returns `graduate_tracer_disposed`. Aggregate reporting retains its contribution.
    Historical audit actors/original UUIDs remain append-only; rare analytical combinations and
    privileged/prior export knowledge remain governance considerations.
12. **Daily:** metadata-only preflight followed by documented exact-ID recording/transcript DELETE.
    Recording needs `deleted: true` and matching `id`; transcript needs matching `transcriptId` and
    `t_deleted`. Already-deleted transcripts can reconcile without another DELETE. Recording 404
    is not proof of erasure. Custom-storage markers require external reconciliation and never
    produce automatic COMPLETED. Local provider reference clears only after verified completion;
    `artifact_disposed_at` is separate from capture/consent. Consent/withdrawal evidence survives;
    late telemetry cannot restore the artifact. Official provider links are in ADR-072.
13. **Persistence:** new operational rule, disposition case and hold tables; three schema-only
    migrations; nullable Graduate Tracer Student FK with identity-shape constraint and anonymization
    marker; minimal disposed participation table; media artifact disposition timestamp. One active
    category rule, one category/source case and one active case hold are enforced. No active rules
    or destructive data migrations are seeded.
14. **Audit:** `privacy.retention.rule.{created,updated,activated,retired}`,
    `privacy.retention.hold.{placed,released}`,
    `privacy.disposition.{approved,started,completed,failed,retry.authorized}`. Metadata is minimized
    rule/case/category/revision/count/state/blocker. Legacy presentations and append-only safeguards
    remain. No domain content, provider URL/token or original-to-anonymous ID mapping is recorded.
15. **Background/retry:** existing Celery/Beat; discovery every 300s (200 new and 200 refreshed review
    cases per category); approved dispatch recovery every 60s (100 rows). Commit QUEUED before
    dispatch; unique claim and row locks; at-least-once delivery, no exactly-once claim. Three total
    automatic provider attempts with 60/120s delays, then truthful FAILED/reconciliation state.
    Stale 15-minute claims need deliberate reconciliation. Up to three recent-MFA manual retry
    authorizations; custom-storage retry is unavailable. Tracer source, verification, completion and
    audit commit atomically. Provider completion/audit failure retains local evidence for recovery.
16. **Backups/restore:** live treatment does not erase historical backups, exports or devices.
    Infrastructure owns backup expiry. Isolate historical restores, recover authoritative completed
    decisions, reapply/reconcile treatment, and verify before releasing restored user traffic or
    workers. No backup subsystem or invented erasure period exists. See the deployment/restore
    [runbook](retention-disposition-runbook.md).
17. **Unsupported/future:** Customer Feedback/CSM needs a separate tested minimization contract.
    Inventory, Routine/Exit Interview, Counseling/Shared Summary, Referral, Call Slip, Appointment,
    Good Moral and Audit Trail are not executable categories; their protection graphs remain.
18. **Contract/client:** canonical backend schemas/router exported to `contracts/openapi.json`;
    14 new operation IDs plus media disposition projection and three capability values. Orval
    regenerated from the contract. Generated frontend files remain ignored/uncommitted, with no
    hand edits. UI uses generated hooks/types and repository primitives.
19. **Automated validation:** final exact results and commands below.
20. **Manual verification:** isolated PostgreSQL (5433), Redis (6381), Django (8100), Next (3100) and
    Chrome/Playwright, using explicitly synthetic local accounts/data/policy fixtures. DPO empty
    view and draft creation; actual TOTP verification with no automatic activation replay; explicit
    activation; safe discovery counts; place/release hold; fixed single-record approval; QUEUED then
    verified completion; an actual isolated Celery worker consumed a committed approval and UI
    polling showed completion. Concurrent draft editing preserved input and required explicit
    re-review/save; concurrent hold closed an open approval without authorization. IT Admin was
    refused by the workspace gate and backend; DPO domain detail request returned 403. Verified
    390px viewport, table-local scrolling, filter dialog, Escape and focus return; inspected desktop
    and mobile screenshots. Local anonymous contributions verified identity removal and a report
    count of three preserved contributions. Provider outcomes used fakes in tests only; real Daily
    deletion, production backup deletion and deployed staging were not manually exercised.
21. **Institutional input:** UCN/DPO must supply adopted category durations, policy/basis references,
    effective dates, exceptional capability holders and actual hold decisions. Future reporting/
    minimization changes need approval. Infrastructure must confirm Daily ownership/custom storage,
    backup expiry, disposition evidence preservation and restore reconciliation procedures. No
    institutional schedule is invented by this PR.

## Validation commands and final results

The isolated test environment uses repository `tests.settings`, PostgreSQL 17 on port 5433 and Redis
on port 6381. No production/local-primary data was modified. All provider test clients are fakes.

From `be/`, with `POSTGRES_PORT=5433`, `REDIS_URL=redis://127.0.0.1:6381/0` and
`REDIS_CACHE_URL=redis://127.0.0.1:6381/1`:

```sh
uv run pytest tests/test_operational_retention.py -q --reuse-db
uv run pytest tests/test_operational_retention.py tests/test_privacy_governance.py tests/test_privacy_governance_expansion.py tests/test_privacy_activity.py tests/test_privacy_release_audit.py tests/test_privacy_governance_contract.py tests/test_privacy_governance_migrations.py tests/test_privacy_pending_acknowledgment.py tests/test_accounts.py tests/test_capability_dependencies.py tests/test_audit.py tests/test_graduate_tracer.py tests/test_graduate_tracer_reports.py tests/test_graduate_tracer_xlsx.py tests/test_ecounseling.py tests/test_ecounseling_media.py tests/test_step_up_policy.py tests/test_authentication.py tests/test_openapi_contract.py -q --reuse-db
uv run ruff format --check .
uv run ruff check .
uv run python manage.py check --settings=tests.settings
uv run python manage.py makemigrations --check --dry-run --settings=tests.settings
uv run python manage.py export_openapi --check --settings=tests.settings
```

New workflow suite: **42 passed in 33.29s**. Broader touched-domain suite: **266 passed, 2 failed
in 206.32s**. Both failures are the unchanged staging OpenAPI assertions listed below. All Ruff,
Django system, migration-drift and canonical OpenAPI checks passed.

The two known OpenAPI assertions were reproduced unchanged on the exact staging base with the same
Python runtime:

- `test_organization_person_projection_schema_is_dedicated_and_complete`: existing
  `responsibility_scope` property is absent from its expected field set.
- `test_core_schemas_and_realistic_error_responses_are_typed`: existing nullable percentage schema
  lacks the top-level `type` expected by the assertion (`KeyError: 'type'`).

Their source/schema behavior is outside the retention slice. They remain visible failures; this
report does not call the broader contract suite or repository CI green. The full unrelated backend
suite was not run.

From `fe/`: `pnpm api:generate`, `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`.

All commands passed. Frontend tests: **114 passed, 0 failed**. Production build completed successfully.

Repository `git diff --check` passed. No generated frontend API files are tracked in the change.
A clean isolated database applied all migrations successfully. Backend and frontend tests additionally
cover required audit rollback, hold/no-approval provider suppression, verified/unverified/transient/
permanent/custom-storage outcomes, lost-response transcript reconciliation, bounded retry/recovery,
legacy audit presentation, immutable audit storage, dependency overrides and protected projections.
