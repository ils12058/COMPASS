# Additive migration and validation

Migration: **`be/compass/good_moral/migrations/0002_receipt_identity_and_history.py`**. Dependencies are Good Moral `0001_canonical_baseline` and the swappable account model. The immutable canonical baseline is unchanged; the additive path is registered in `compass/common/canonical_migrations.json`.

It creates the two core and three support tables, named uniqueness/partial indexes and row-shape constraints, frozen SQL guards, and a DORMANT singleton control row. It performs **no receipt backfill** and makes no historical ownership or physical-inspection assertion. SQL is migration-owned, not imported from changeable runtime code.

Database guards cover:

- Canonical nonempty ASCII/version/key shape and global key uniqueness.
- Permanent identity binding/key/metadata and immutable mutation/import evidence; new operation results must match the current request/revision at insertion.
- Exact same-request predecessor and consecutive sequence; immutable facts; one-way attributable closure with a required successor.
- Current identity ownership, partial uniqueness, null-identity prohibition and superseded-key non-reactivation.
- Explicit historical amount allowance, with valid ordinary/current numeric facts.
- Deferred equality of the latest revision and compatibility projection, protecting ORM/raw SQL writers.
- An ordinary identity must have its immutable claim at commit; failed operations cannot leave an orphan reservation.
- A monotonic writer state with complete source/observation coverage and unsupported-format refusal at activation.

Receipt table guards are exercised directly, including illegal rekey/delete/update/reactivation, wrong binding/predecessor/sequence, projection-only writes, orphan reservation, closure without successor and control downgrade. Tests use PostgreSQL; SQLite is not substituted.

New migration tests reverse to the canonical Good Moral baseline, create populated synthetic historical source rows, upgrade, compare complete row values, reverse/reapply with empty ledger history, and preserve source data. A second rehearsal imports evidence and proves destructive reversal is refused atomically. Existing canonical tests validate registered migration files/hashes, graph/no drift and declared PostgreSQL indexes/constraints. Fresh test database creation also exercises the full install graph.

For issued F4/F6 with missing or non-80 receipt facts, tests compare all persisted request fields, saved render context and exact rendered HTML before/after import. Existing domain tests retain actual Chromium PDF generation, supported historical forms, frozen issuer provenance, owned downloads and privacy release Audit checks. Binary PDF equality is not claimed; native printing/paper/signature/dry seal remain outside headless evidence.

All executions were on disposable loopback PostgreSQL using test-generated encryption keys and synthetic fixtures. The production command/resource budget, protected inventory, writer window and operational recovery plan remain a separately authorized release prerequisite. No live migration/reset/backfill was executed. See [validation.md](validation.md) for exact commands and results.
