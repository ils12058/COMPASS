# Validation and evidence limits

Audit performed **2026-10-24 (Asia/Manila)** against **`80b719eb7fbeb86646228b4c013314e8e909876a`**.

## Repository isolation and source inspection

Executed `git fetch origin integration/ux15-modernization` in the original repository and `git rev-parse origin/integration/ux15-modernization`; fetched HEAD matched the supplied SHA. Created a managed isolated worktree at that exact commit and switched it to `audit/gm-or-0-receipt-integrity`. The original checkout was on `staging` with preexisting untracked files; those files and branch were not edited.

Read the Good Moral model/service/API/work module, canonical migration and registry, requested three test modules, account capability/role/designation policy, Audit model/actions, institutional-time helpers, notification producer/policy/email presentation, controlled-form and document renderer services/templates, frontend receipt/correction/preparation/issuance/request/detail/list/print controls, frontend rules, relevant unit/browser test sources and CI/deployment conventions. Used `rg`, numbered source reads and Git inspection; [current-state-audit.md](current-state-audit.md) supplies pinned code references.

No original proposal's staging snapshot, historical CI run, or memory of an earlier deployment is counted as newly verified behavior. The current test/source baseline is the exact integration commit above.

## Newly executed checks

Working directory for Python checks: isolated worktree `be/`. Used existing local dependency runtime `/Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python` (**Python 3.13.12, Django 6.1.1, pytest 9.1.1, psycopg 3.3.5**). No dependency upgrade was performed.

The runner supplied a clean environment, imported the inspected worktree via `PYTHONPATH`, used `DJANGO_SETTINGS_MODULE=tests.settings`, and explicitly supplied synthetic local PostgreSQL/Redis endpoints. It did not load deployment `.env` files or connect to the preexisting local/default PostgreSQL service. Test settings generate ephemeral encryption keys and synthetic external-service values. Local PostgreSQL **17.11** was initialized into a new `/tmp/gm-or-0-audit/synthetic-…/pgdata` directory, bound only to loopback on a dynamically selected nondefault port, with a dedicated `gm_or_0_synthetic` database. A separate ephemeral loopback Redis served test cache/rate/idempotency dependencies; no worker/SMTP/object-store service was launched.

| Executed command (runtime prefix abbreviated as `python`) | Result |
| --- | --- |
| `python -m pytest tests/test_good_moral.py tests/test_good_moral_assisted.py tests/test_good_moral_preparation.py tests/test_canonical_baseline.py -q` | **162 passed in 80.98s**; no failures/skips reported |
| `python manage.py makemigrations --check --dry-run --settings=tests.settings` | **Passed**: `No changes detected`; no migration file generated |
| `python manage.py export_openapi --check --settings=tests.settings` | **Passed**: committed contract current; no contract rewrite |
| Documentation inventory SQL rehearsal on synthetic PostgreSQL | **Passed** after independently checking expected category counts; eight rows, both variants/all four states, no row identities in result |

Pytest created/discarded its own synthetic test database and applied the repository's **existing** migrations as normal test setup. This is not a feature migration or an operation on staging/live data. Canonical tests checked registered baseline hashes/additions, graph/model drift, PostgreSQL constraint/index presence and fail-closed pre-canonical-history behavior. Running them was justified by this audit's migration handoff. OpenAPI check was read-only verification of the baseline wire contract used in the API audit.

The focused suites exercise self/assisted creation, actor restrictions, F4/F6 prerequisites, corrections, preparation versions, issuance/feedback/notifications, owned historical access and actual Chromium PDF generation. Assisted creation concurrency tests run on PostgreSQL; these do **not** prove future receipt-assignment concurrency. There is no receipt ledger/inspection feature to test yet.

### Inventory SQL synthetic evidence

Executed the exact fenced SQL from [legacy-data-and-migration.md](legacy-data-and-migration.md#count-only-sql-for-the-inspected-schema) against synthetic tables matching its referenced columns, including one synthetic prior receipt-update Audit event. No application schema or feature was changed for this rehearsal. Counts below are **fixture expectations only**, not deployed-data estimates:

| Fixture metric | Synthetic count |
| --- | ---: |
| Total observations | 8 |
| Missing number / date / amount | 1 / 3 / 2 |
| Complete tuple (presence only, not validity) | 4 |
| Zero / non-80 / negative amount | 1 / 3 / 1 |
| Future receipt date / unsupported number | 1 / 1 |
| Duplicate normalized-key claims | 2 |
| Known recorded receipt correction | 1 |
| Duplicate group | 1, size bucket `2`, multiple Students/mixed variants/issued involvement/formatting variation |

The runner asserted these counts and the bounded conflict classification. A first fixture assertion incorrectly expected three complete tuples; review established four because a tuple with an unsupported number still has all three fields present. The expected count was corrected; the query was unchanged. This confirms why completeness and validity must remain separate classifications.

Initial local PostgreSQL startup failed because the clean environment omitted a valid locale; setting `LC_ALL=C`/`LANG=C` corrected it. A later restart attempt omitted explicit port/socket options and failed to bind the already occupied default port; it never connected to or modified that service. The successful rehearsal used the dedicated cluster's explicit nondefault port/socket. All owned PostgreSQL/Redis processes were stopped after validation. Synthetic logs/runner files stayed outside the repository.

## Design reference checks

Consulted PostgreSQL 17 primary documentation for [constraints/partial unique indexes](https://www.postgresql.org/docs/17/ddl-constraints.html), [row locking](https://www.postgresql.org/docs/17/explicit-locking.html), and [transaction isolation](https://www.postgresql.org/docs/17/transaction-iso.html). These support the proposed database/transaction design, not institutional fee or OR numbering policy. No independent fee effective date was looked up or asserted.

## Not executed / still required

- No deployed/live/staging data classification; all actual counts/duplicates/formats/fee distributions remain unknown. No real institutional payment data or physical receipt inspected.
- No new receipt models/migrations/triggers/backfill command/API/UI/capability implemented. Their correctness and races remain future GM-OR-1/2/4 acceptance tests.
- Frontend unit/browser sources were reviewed, but frontend install/build/browser suites were **not run** for this documentation-only change. Accessibility/responsiveness observations are source review, not fresh device/screen-reader evidence.
- Existing backend PDF tests generated PDFs, but no new historical receipt migration/render comparison, headful native print dialog, paper output, physical signature, Registrar dry seal, UAT or real email-client exercise was performed.
- No SSH, DigitalOcean connection, deployment, live migration/reset, real-data export, ledger population, automatic merge or fee-policy activation.

Final staged checks passed: `git diff --cached --check`; exactly the eight requested Markdown files under `docs/gm-or-0/`; no runtime, test, UI, contract or migration file changes. A local link checker verified 62 pinned code links (paths/line bounds) and internal document links/anchors. Remote integration HEAD was rechecked and still matched the inspected SHA. Branch/PR target and clean committed worktree are checked again at handoff. PR/CI status is reported as observed; a documentation PR's CI result is not a future rollout validation.
