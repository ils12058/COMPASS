# Curated activity retrieval validation

Validated on 2026-10-04 in the isolated `codex/activity-retrieval-and-supervision` worktree.
Staging base: `ed14b7580b5fc825bd49675f4a93e3c93c441ec2` (#162 included).
Design/scope and all 22 admitted supervised actions are specified in
[ADR-073](decisions/ADR-073-curated-activity-retrieval-and-supervision.md).

## Backend checks

The focused command covers audit, self/supervised activity, account policy/dependencies,
organization/supervision, Platform, Privacy, release audit, retention/disposition and OpenAPI:

```sh
POSTGRES_PORT=5434 uv run pytest \
  tests/test_activity_retrieval.py tests/test_activity.py tests/test_audit.py \
  tests/test_accounts.py tests/test_capability_dependencies.py tests/test_organization.py \
  tests/test_platform_activity.py tests/test_privacy_activity.py \
  tests/test_privacy_release_audit.py tests/test_operational_retention.py \
  tests/test_openapi_contract.py -q
```

The new retrieval tests exercise actual 10001-row rejection, projection-before-pagination,
capability dependencies/revokes, current scope/no-op/reassignment/removal boundaries, all action/
target pairs, hidden-field search isolation, malformed payloads, institutional dates, Unicode,
formula prefixes, export snapshot and fail-closed audit. Five existing assertions were updated to
the new canonical capability counts/grants and closed activity type enum. No unrelated domain
behavior or validation rule was relaxed.

Two existing OpenAPI tests were independently reproduced on an archive of the exact staging base
using the same environment (2 failed in 5.11s):

- `test_organization_person_projection_schema_is_dedicated_and_complete`: stale expected field set
  omits the existing `responsibility_scope`.
- `test_core_schemas_and_realistic_error_responses_are_typed`: stale top-level numeric `type`
  assertion for the existing nullable `DistributionRow.percentage` (`anyOf`).

These remain visible failures rather than being skipped or repaired outside this slice.
Final focused result: **255 passed, 2 failed in 300.57s**. All **91 new retrieval cases passed**;
the only failures were the two independently reproduced baseline assertions above.
`ruff format --check` (486 files), `ruff check`, Django system check, migration drift check and
OpenAPI drift check passed. A clean isolated database applied all existing migrations successfully;
this feature adds none. `git diff --check` passed.

## Frontend and browser checks

Canonical backend OpenAPI export and Orval generation completed. Generated clients are not
hand-edited or committed. Frontend lint, typecheck, test and production build passed.
Frontend tests: **130 passed**, including 15 new activity cases plus CSV Blob parsing.

Local Chrome/Playwright used synthetic accounts, events and an isolated database; no live account
data, provider action or retention mutation was used. Completed browser checks:

- Student and GSS: My/Security only; no supervisory tab, activity search or export.
- Head Guidance without direct staff: same self view; no global staff visibility.
- Counselor: only direct GSS, no pre-assignment event, staff security or hidden record content.
- Supervised search: explicit apply; staff/type/dates combine; URL reload/back restores criteria;
  pagination preserves them; criteria changes reset page; empty filtered state clears correctly.
- IT Admin: technical type/operator criteria work; no CSV or Privacy events.
- DPO: all six criteria combine; real downloaded UTF-8 CSV has all 25 matching rows across pages;
  raw audit fields and confidential synthetic content are absent; export fact appears subsequently.
- DPO export: pending prevents duplicate clicks; typed over-limit error preserves filters.
- Supervised/DPO at 390px: no horizontal overflow; filter dialog Escape and Apply return focus.
- Counselor/DPO: reversed date bounds stay in the dialog without URL navigation; corrected bounds
  apply and return focus. Same-criteria 503 refresh retains confirmed rows with a warning; a
  subsequent 403 hides protected cached rows. DPO export stays disabled during refresh failure.

The maximum/export audit failures were exercised through actual backend tests rather than attempting
a live large release. Responsive captures and the downloaded file were visually/structurally checked.

## Query audit and rollout

EXPLAIN ANALYZE BUFFERS on 15101 synthetic AuditEvents confirmed actor/action/date supervision and
Privacy action/date queries use the existing action/time index and organization/account indexes.
Sparse safe-text search remains a bounded application scan. No index or schema migration was added.
Measurements are representative local evidence, not a production latency guarantee.

Deployment must synchronize identity policy: 69 canonical capabilities, 78 role grants, 19
designation grants. There is no extra MFA gate for CSV. Retention's existing recent-MFA decisions
and append-only audit protections are unchanged. No real retention/disposition action was executed.

Intentional limits: current direct relationships only, no former-assignment reconstruction, current
display names, 100000 candidates per retrieval and 10000 rows per CSV. Raw AuditEvent, IP, User-Agent,
request ID and raw metadata remain unexposed. My/Security/Supervised/Platform have no export.
Opening a PR is not merge, repository-CI success or live deployment verification.
