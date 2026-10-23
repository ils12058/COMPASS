# Executed validation and limits

Baseline: `0ba5024a8468b3e27b2b1b3723cf431bf0390f61`. All backend data is synthetic in a newly created, dedicated local PostgreSQL 17 cluster and Redis instance, on temporary loopback ports. Python 3.13.12, Django 6.1.1. The ordinary test database installs the full real migration graph. Upgrade tests create/drop additional isolated databases and migrate historical baseline state forward; no deployed database or key is involved. No worker or delivery provider is started.

## Backend commands

Run from `be/`, with `DJANGO_SETTINGS_MODULE=tests.settings` and database/cache environment pointing only to the dedicated temporary services. Tests use real migrations; **no `--nomigrations`**.

```sh
python -m pytest -q \
  tests/test_student_session_summaries.py tests/test_student_session_summary_encryption.py \
  tests/test_student_session_summary_cutover.py tests/test_student_session_summary_contract.py \
  tests/test_counseling_context.py tests/test_counseling.py tests/test_routine_encounter_linking.py \
  tests/test_openapi_contract.py tests/test_accounts.py tests/test_staging_seed.py \
  tests/test_notification_email_links.py tests/test_notification_cross_channel.py \
  tests/test_operational_email_presentation.py tests/test_transactional_email.py \
  tests/test_runtime_secrets.py tests/test_runtime_secrets_compose.py \
  tests/test_canonical_baseline.py tests/test_counseling_frontend_readiness.py \
  tests/test_notification_push.py --maxfail=1
```

**1,037 distinct backend cases passed across the focused and keyring groups.** The original 916-case focused selection completed in recorded partitions: 147 passed; the corrected fixture case passed separately; 406 further passed; the catalog snapshot case passed separately; 262 further passed; the canonical-label email privacy case passed separately; the final 98 passed. This is complete case coverage across interrupted/resumed runs, not a claim of one uninterrupted green run. Nine additional later-purpose separation cases and 112 non-overlapping cross-domain configuration cases bring the distinct total to 1,037. Preliminary/targeted overlapping reruns are not added to that total.

Resume commands used exact collected node IDs from the same selection and excluded only previously passed cases and separately corrected/passed cases. Partitions ended with `406 passed / 148 deselected` and `262 passed`, then `98 passed`; stopped failing executions remain documented below. Initial targeted evidence: 69 summary lifecycle/encryption tests passed before additional cases; 15 contract/cutover tests passed; the populated upgrade and content-type rename plus corrected seed-clock test passed 2/2; dedicated four-fixture regeneration passed 1/1. These preliminary runs overlap the final group and are not added as unique tests.

The first large group stopped at 141 passed / 1 failed, and the next at 147 passed / 1 failed: two pre-existing seed tests canceled fixtures anchored on 2026-10-15 using current wall-clock time. Both now pass `now=dataset_now()` to the existing service; cancellation policy and assertions are unchanged. The later catalog-hash assertion exposed approved summary terminology changes in snapshot text. All frozen hash constants remain unchanged: a narrowly enumerated terminology projection restores historical spelling only for that historical comparison; identities, structure, counts and unrelated text remain hash-sensitive. Current canonical fixtures are separately regenerated/verified. The email privacy assertion retains all protected terms, including session: only the exact canonical resource label is stripped before checking for protected detail. Template-context tests still prohibit record/domain context. Initial browser failures were test-only asynchronous navigation and the existing not-found heading, corrected through targeted 3/3 reruns in each engine before full reruns. No failed run is represented as green.

## Frontend and contract commands

```sh
pnpm install --frozen-lockfile --offline
pnpm api:generate
pnpm typecheck
pnpm lint
COMPASS_API_BASE_URL= NEXT_TELEMETRY_DISABLED=1 pnpm build
pnpm exec node --import ./tests/support/register-tsx.mjs --test --test-concurrency=1 \
  tests/counseling-context-confidentiality.test.mjs tests/counseling-encounter-consistency.test.mjs \
  tests/routine-encounter-linking.test.mjs tests/ui-information-hierarchy.test.mjs \
  tests/notification-route-contract.test.mjs tests/notification-email-auth.test.mjs \
  tests/portal-command-palette.test.mjs
```

128/128 Node tests passed. Typecheck and lint passed, lint with zero warnings. Ordinary production build passed with 95 static pages; no fake-Daily test seam was enabled. Offline install reused the existing store; no dependency/lockfile changes. The generated Next type-reference file is restored as build output, not committed.

Backend `export_openapi` and `export_openapi --check` passed using `tests.settings` with database connection opening explicitly blocked in the export subprocess, followed by successful Orval generation. Generated clients contain only canonical ordinary summary operations; Context historical-summary operations remain absent. Generated files are ignored and uncommitted.

Browser commands ran against local production `pnpm start --hostname 127.0.0.1 --port 49618`, each with `COMPASS_UI_BASE_URL=http://127.0.0.1:49618` and once each for `COMPASS_UI_BROWSER=chromium` and `webkit`:

```sh
node tests/counseling-context-confidentiality.browser.mjs
COMPASS_UI_CHECK='^(?!ecounseling-dialog-keeps-times-and-call$)' \
  node tests/counseling-encounter-consistency.browser.mjs
```

Final canonical/confidentiality suite: **20/20 Chromium and 20/20 WebKit**. It exercises all four Context anchors with and without summary capabilities, absence of old/new Context history requests, stale-denial clearing, owned/denied Encounter links, author save/publish/locked reload, Student own/denied detail, desktop/phone list/detail/back, keyboard Notification deep links with allowed/denied destinations, and old route without redirect/body. API responses are synthetic mocks; server-side authorization/decryption is separately covered by PostgreSQL-backed tests.

Existing encounter suite: **13/13 Chromium + 13/13 WebKit**, bringing the distinct browser scenarios to **66 (33 per engine)**. Desktop publication and phone Context screenshots were visually inspected. Final Ruff lint/format and diff checks are recorded with the PR; hosted CI is inspected separately. The one excluded active-call case needs a separate `NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1` fake-Daily build. No real-device, manual assistive-technology, live provider, deployed environment or operational readiness proof is claimed.

CI planner: `python -m unittest discover -s .github/scripts -p test_backend_ci.py` — **38/38 passed**. Backend migration/static scope changes select the repository's conservative CI behavior. Integration workflows currently filter other target branches, so local tests do not imply hosted CI.

## Final PostgreSQL schema review

A real populated rehearsal exposed PostgreSQL retaining the former generated PK/unique/FK names after Django's table rename. The additive migration now renames those constraints explicitly; the strict final introspection asserts exactly the four canonical constraint names, and the content-type identity is renamed through the normal management migration path. The targeted populated test passed after the correction. After the correction, this final focused rerun passed **191/191 in 87.79s** with real migrations, covering a fresh schema, model/lifecycle, all cutover/refusal cases, retired contracts, canonical graph/hash/model agreement, complete email-template regressions and the full-dataset scoped regeneration case. These overlap the existing distinct total.

```sh
python -m pytest -q tests/test_student_session_summaries.py \
  tests/test_student_session_summary_cutover.py tests/test_student_session_summary_contract.py \
  tests/test_canonical_baseline.py tests/test_transactional_email.py \
  tests/test_staging_seed.py::SeededDatasetTests::test_cont1b_scoped_summary_regeneration_is_repeatable_and_preserves_dataset --maxfail=1
```

Final backend Ruff lint and format checks passed for all 54 affected/new backend Python files; `git diff --check` passed. Baseline migration and Context runtime files remain byte-identical to the starting commit.

## Additional key-separation commands

```sh
python -m pytest -q \
  tests/test_account_profile_confidential_content_encryption.py \
  tests/test_referral_confidential_content_encryption.py \
  tests/test_exit_interview_confidential_content_encryption.py \
  tests/test_inventory_confidential_content_encryption.py \
  tests/test_graduate_tracer_confidential_content_encryption.py \
  tests/test_guidance_messages.py tests/test_assessment_records_configuration.py \
  -k 'settings or setting_required or required_keyring or other_key_entries or pointer_loaded or keyring_rejects or file_keyring or ordered_config or config_rejects or file_configuration or runtime_keyring or invalid_or_duplicate_config' --maxfail=1
# 112 passed / 775 deselected in 7.86s
python -m pytest -q tests/test_student_session_summary_encryption.py::test_every_later_purpose_ring_rejects_summary_key_reuse
# 9 passed in 0.68s
```

The cross-domain group uses another explicitly isolated test database name on the same dedicated local cluster. It does not share the running focused group's database. CI duration entries for renamed/new suites use measured pytest phase times (11.7s model/lifecycle, 16.5s encryption, 52.9s cutover, 1.2s retired-contract tests), excluding shared interpreter startup. The nine later-purpose cases were validated separately after that measurement; duration entries are scheduling estimates, not fabricated timings.

## Failure-scenario disposition

| Failure | Evidence or explicit operating boundary |
| --- | --- |
| Missing new ring / old-only configuration | Startup parser tests refuse; fresh migration/test startup needs only new ring. |
| Wrong ring, binding, tamper, malformed or unsupported version | Codec tests fail generically; no blank-body fallback or log disclosure. |
| Old token, including rotated old token | Frozen oracle tests reject it under the new binding; rotation is not conversion. |
| Existing legacy draft/publication or orphan Notification | Forward migration refuses before schema rename. |
| Capability REVOKE/expiry or mixed code collision | IDs/override fields preserved, deny semantics checked, collisions abort; stale sessions invalidated. |
| Pending/claimed old delivery | Pending dependent rows are scoped cleanup; processing email/Push blocks execution. Old consumers must be stopped; queued removed UUIDs cannot claim a missing row. |
| Partial/interrupted purge | Atomic rollback test preserves summary/Notification/delivery rows. |
| Migration fails after scoped purge | Stay in maintenance, diagnose/resume or restore full recovery unit; code-only rollback prohibited. Accounts migration can have committed independently. |
| Seeder/regeneration fails | Bounded transactions roll back; unknown or differing fixture refuses overwrite. Keep consumers stopped, inspect safe counts, retry only after diagnosis. |
| New code with old schema / old code with new schema | Unsupported mixed versions. Maintenance fencing is mandatory; no aliases or fallback to old table/binding. Not rehearsed as a live rollout. |
| Old frontend or stale email URL | Backend old endpoints 404 without decrypt; old frontend detail route is not-found without redirect. Already received messages/content cannot be recalled. |
| Duplicate publication identity | Existing unique logical-event constraint and repeated-publication tests preserve idempotency; scoped regeneration repeat creates no duplicate. Conflicting persisted capabilities require review, never merge-by-guess. |
| Repeated migration/seed verification | Empty migration plan after success; fresh/repeat seed and dataset verification; regeneration repeat creates zero. |
| Cross-Counselor or unsupported actor | Author/Student negative matrix and decryption spies, including unrelated College, Head, IT Admin, GSS, inactive/revoked identities; Context never returns summary bodies. |

No remote SSH, keys, database reset/migration, worker/service mutation, deployment, merge or `staging`/`main` change was performed. Staging prerequisites and recovery are in [migration-and-cutover.md](migration-and-cutover.md).
