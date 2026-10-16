# CANON-1 condensed implementation roadmap

Verified base for CANON-1B: `0d7fbd0a5fd0ee6d38aba091a27ffa4ed3ac4691`, fetched 2026-10-16
(Asia/Manila). PR #247 merged CANON-1A. Its exact post-merge backend full-regression run
[38888769644](https://github.com/ils12058/COMPASS/actions/runs/38888769644) passed all six shards.
That result does not certify later revisions or browser coverage.

The owner consolidated the remaining milestone into four implementation slices. This replaces the
older proposed CANON-2/3/2R/4/5/6/7 PR split and the regression work already incorporated into #247.
Existing audit, inventories and historical regression reports remain evidence; they are not a
second implementation backlog to repeat verbatim.

| Slice | Target | Scope and acceptance |
| --- | --- | --- |
| CANON-1A — CI Foundation | staging; merged #247 | Complete backend discovery (167 files, six shards), all 31 browser suites on both engines, attributable suite failures, CI selector self-tests, initial fixture/application regression fixes. Exact merged backend run passed; browser failures handed to 1B. |
| CANON-1B — Full-Stack Cleanup & Browser Stabilization | staging; current | Remove caller-proven dead aliases/components/compatibility code; consolidate safe shared primitives and frontend consumers; stabilize required browser matrix without hiding assertions; document PG-1A reset-only boundary. One compatible PR, generated-client/contract consistency, focused domain tests and exact-revision CI. See implementation and browser reports. |
| CANON-1C — Canonical Schema & Seeder | separate clean-baseline integration branch | Combine final PG-1A source/ledger decommission, canonical model/migration baseline and deterministic synthetic seeder work. Review tombstone/broker/runtime/callback prerequisites, provider-role model removal, old capability-name guards, frozen migration schemas and additive seed namespace together. Compare schema/constraints/indexes/defaults; fresh PostgreSQL migration tests; encryption/key rotation/provenance/ownership; seed rerun/concurrency/environment safety. No Student population expansion authorized here. |
| CANON-1D — Final Regression & Staging Rebuild Preparation | clean-baseline integration branch | Complete backend and both browser engines at the reviewed final revision; role-scoped UAT, privacy/encryption/PDF/media regressions; non-destructive resource inventory and typed environment/revision gates; disposable local rebuild rehearsal, rollback fencing and operator handoff. No live reset execution. |

## Integration and reset gates

Create the reset integration branch only when incompatible work begins and record its reviewed
compatible base. Never merge incompatible schema/history/tombstone removals into ordinary staging.
Keep supported APIs, deployed-frontend compatibility, encryption and authorization through 1B.
Old retention page bookmarks cease redirecting in 1B and return 404; the canonical oversight route
and all supported APIs remain. No data/schema cutover is required for that route retirement.

The [PG-1A handoff](CANON-1B-PG-1A-Reset-Handoff.md) identifies actual ledger consumers and the
required worker/Beat stop, broker isolation, callback/provider/object-store decisions and rollback
image fencing. PostgreSQL reset does not delete provider artifacts, object storage, Redis messages
or backups. Their classification and any destructive action require separate authorization.

The reset itself remains a separately authorized operation after 1D preparation. No merge,
deployment, infrastructure modification, secret rotation, migration rewrite, live migration,
database reset, Redis purge or external artifact deletion is part of CANON-1B.
