# CONT-1A — Student-facing summary confidentiality correction

Implementation record, 2026-10-23. Planning baseline: the merged [CONT-0 audit](../cont-0/README.md), especially its [summary audit](../cont-0/student-session-summary-audit.md), [access matrix](../cont-0/confidential-access-matrix.md), [threat model](../cont-0/threat-model.md), and [implementation plan](../cont-0/implementation-plan.md). Historical audit documents are unchanged.

## Baseline and confirmed issue

- Repository: `ils12058/COMPASS`; target: `integration/ux15-modernization`.
- Fetched integration HEAD before work: `5fcc3fe7ce2f9b07486c353fd662cc765c1f6f4f`; re-fetched before publication and confirmed the same HEAD.
- Branch: `feature/cont-1a-summary-confidentiality`, in the isolated managed worktree `cont-1a-summary-confidentiality/COMPASS`.
- `list_context_shared_summaries()` selected published summaries by Student without filtering the author. The Context endpoint decrypted and returned those records to another eligible provider, including a provider from another College.
- Before implementation, the existing positive `test_context_shared_summaries_are_published_only` passed (1 test). The replacement negative Appointment case failed against the old implementation because the decryption spy was called. These establish the exposure independently of frontend controls.

## Change and preserved boundaries

`be/compass/counseling/context_services.py` removes the summary projection, dataclass, imports/exports, and overview section. `context_api.py` removes the route `/api/v1/counseling/context/{anchor_type}/{anchor_id}/shared-summaries`, operation `counselingContextListSharedSummaries`, two response schemas, and `SHARED_SUMMARIES` enum member. There is no replacement historical-summary endpoint or compatibility alias. Direct requests now return 404 before summary decryption.

`fe/src/features/counseling/counseling-workspace.tsx` removes the history tab, historical author/content rendering, generated query/hook/type/key consumers, and Context publication callback/editor. Its E-Counseling embed drops the corresponding unused props. No Context summary query remains, including when a stale overview still advertises the old section or a legacy query cache contains a previous publication.

Encounter Detail retains its existing author-scoped editor. The existing **View encounter** link is offered only after the independently authorized ordinary Encounter GET confirms the Encounter ID, current Counselor, and Student; a Context reference alone does not establish ownership. A denied canonical refresh hides the link even when an older response remains cached. Backend authorization remains authoritative.

The ordinary author GET/PUT/publish and Student own-published list/detail APIs, capability policy, summary model/storage, publication immutability/idempotency, audit/notification production, crypto code, keys and ciphertext bindings are unchanged. Negative tests compare every summary-row field before/after Context reads. Existing encryption tests run only against synthetic records in disposable test infrastructure; no environment records or keys were changed.

`context_access.py`, Context settings/defaults, and non-summary projection implementations are unchanged: exact provider, cross-College eligibility, Appointment/Direct Routine Interview anchors, cancellation invalidation, 24-hour pre-Appointment window, 24-hour uncompleted grace, and seven days after a matching completed Encounter. Inventory, Support, History, Routine Interview, encounter recording/linking, expiry handling, independent assigned-record access, and Appointment Messages remain available under existing policy. E-Counseling media permissions are unchanged.

## Authorization evidence

| Scenario | Executed evidence |
| --- | --- |
| A — Different author | Counselor A's encrypted published/draft records cannot be read through B's legitimate Context; ordinary other-author GET is denied. |
| B — Cross-College | Student affiliation and B's College responsibility differ. Overview, Inventory, Support, and History remain 200 while summary URLs are 404. |
| C — Head provider | Exact Head Appointment provider gets legitimate Context without a previous author's summaries; existing tests also deny unrelated Head access. |
| D — Direct anchors | WALK_IN, CALLED_IN, REFERRED each exercise submitted-intake Context and the same negative disclosure assertions. |
| E — Capabilities | Five anchor/provider cases × baseline, absent, and explicitly revoked summary-view capability = 15 cases. Ordinary capability does not establish authorship. |
| F — Removed route | Six URL/query variations, alternate `include` on overview, decryption-failure spies, no discovered IDs/body/ciphertext/author-publication metadata, unchanged rows. Corrupt published/draft/other-Student tokens also cannot trigger decryption through removed URLs. |
| G — Authorized lifecycle | Existing author draft/replacement/publication/repeated publication/immutability/audit/notification tests; Student own-published pagination/detail, hidden drafts and other Students, and authorization-before-decryption tests. Browser verifies existing editor save → publish → locked reload and own/denied Student detail. |
| H — Relationship lifetime | Existing exact-provider/cancellation, uncompleted grace, completed Encounter extension, direct matching/mismatching Encounter, and own Encounter access after Context expiry tests; removed route stays 404 after expiry. |
| I — Frontend | Legacy section/cache ignored; generated operation absent; no background history requests across all four anchors with/without summary capabilities; denied Context refresh clears protected presentation; canonical ownership controls links; keyboard tab navigation and phone layout checks. |

Backend coverage is in `test_counseling_context.py`, `test_shared_summaries.py`, `test_counseling_shared_summary_encryption.py`, and related Counseling/linking/contract tests. New frontend coverage is in `counseling-context-confidentiality.test.mjs` and `.browser.mjs`, using `support/cont1a-summary-fixtures.mjs`. The existing embedded Context hierarchy test is updated for the narrower component props.

## Validation actually executed

Backend commands below ran from `be/` with `DJANGO_SETTINGS_MODULE=tests.settings`, a Python 3.13.12/Django 6.1.1 environment, and dedicated local PostgreSQL 17/Redis processes on temporary ports. `--nomigrations` builds only disposable test tables from model definitions. No application migration command or existing database reset was run. Synthetic test databases were created/dropped by pytest; no worker, provider, or outbound mail delivery was started.

```sh
python -m pytest --nomigrations -q \
  tests/test_counseling_context.py tests/test_shared_summaries.py \
  tests/test_counseling_shared_summary_encryption.py \
  tests/test_openapi_contract.py::test_counseling_context_contract_is_anchor_based_and_read_only
# 100 passed in 74.30s

python -m pytest --nomigrations -q \
  tests/test_counseling.py tests/test_counseling_frontend_readiness.py \
  tests/test_routine_encounter_linking.py tests/test_openapi_contract.py
# 85 passed in 98.70s; five existing Django Ninja tuple-response deprecation warnings
```

These are **184 unique backend tests / 185 successful test executions**; the focused contract test overlaps both commands. The initial baseline/red tests are separate from these final counts.

The repository's `export_openapi` command and `export_openapi --check` passed under `tests.settings`, with database connection opening blocked in the export subprocess. Structural comparison against the baseline proves the only contract changes are one removed path, two removed schemas, and one removed enum value. Ordinary APIs are identical. Then, from `fe/`:

```sh
pnpm api:generate
pnpm typecheck
pnpm lint
pnpm exec node --import ./tests/support/register-tsx.mjs --test --test-concurrency=1 \
  tests/counseling-context-confidentiality.test.mjs \
  tests/counseling-encounter-consistency.test.mjs \
  tests/routine-encounter-linking.test.mjs tests/ui-information-hierarchy.test.mjs
COMPASS_API_BASE_URL= NEXT_TELEMETRY_DISABLED=1 pnpm build
```

All passed: **46 Node tests**, lint with zero warnings, typecheck, and ordinary production build with 95 static pages. Orval-generated output contains no removed Context summary symbols; ordinary author/Student operations remain generated. Generated clients remain ignored and are not committed. No dependencies or lockfiles changed.

Against that production build, on a local `pnpm start --hostname 127.0.0.1 --port 49617` server, each browser command below ran once for `COMPASS_UI_BROWSER=chromium` and once for `webkit`, with `COMPASS_UI_BASE_URL=http://127.0.0.1:49617`:

```sh
node tests/counseling-context-confidentiality.browser.mjs
# 15/15 Chromium and 15/15 WebKit

COMPASS_UI_CHECK='^(?!ecounseling-dialog-keeps-times-and-call$)' \
  node tests/counseling-encounter-consistency.browser.mjs
# 13/13 Chromium and 13/13 WebKit
```

**56 successful browser scenarios total.** Browser APIs are synthetic mocks; external traffic/service workers are blocked by the existing harness. Desktop Context, phone Support, and published author summary screenshots were visually inspected. The one excluded active-call case requires the separate `NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1` fake-Daily build; that case was not run. The ordinary production build did not enable the test seam.

Ruff lint and format checks passed for all five changed Python files. `git diff --check` passed. Source comparison confirms the ordinary summary API/service/model/crypto, Context resolver/settings, and policy files are unchanged. No migration file was added or modified.

## Limits and CONT-1B handoff

Local focused tests and mocked-browser results do not establish live runtime state, real-device behavior, manual assistive-technology acceptance, or hosted CI. No live configuration, existing data, SSH, DigitalOcean, deployment, capability expansion, continuity grant, handoff mechanism, or protected-branch update is part of this change. The implementation stops at an open integration PR without merging. CI state must be reported from that PR separately.

The removed route is intentionally incompatible with older clients: they receive 404. An already-open older frontend may retain content fetched before rollout until refreshed; this PR neither changes deployed clients nor retroactively retracts prior disclosures. Coordinated release and session/client refresh decisions require separate deployment authorization. The updated frontend never renders the removed historical panel, including seeded stale-cache cases.

CONT-1B must first re-inventory the merged implementation and approve the complete Student Session Summary naming/contract/notification/capability cutover. It must resolve institutional retention and whether any dataset is explicitly disposable, choose a retention-preserving authenticated ciphertext rebind/re-encryption versus an expressly authorized reset, define key/configuration/mount changes and rollback, and rehearse both fresh installation and existing-data upgrade. Existing ciphertext bindings must not be changed by a plain identifier rename. No such rename, migration, reset, key operation, notification-event change, or ordinary endpoint rename is implemented here; use the [CONT-0 final recommendation](../cont-0/final-recommendation.md) as that next slice's baseline.
