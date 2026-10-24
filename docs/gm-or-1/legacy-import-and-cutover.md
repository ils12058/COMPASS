# Legacy import, writer fence and rollback

`import_good_moral_receipts` is a **synthetic-only rehearsal command**. It rejects non-local app environments, non-loopback database hosts, names without a `test_` prefix or `_synthetic` suffix, a mismatched explicit database confirmation, and a server-reported database name different from the configured one. No live credentials are required or authorized. There is no production activation flag or deployment step in this PR.

Examples, only inside an already configured disposable PostgreSQL environment:

```sh
python manage.py import_good_moral_receipts --dry-run \
  --confirm-disposable-database gm_or_1_synthetic
python manage.py import_good_moral_receipts --import \
  --batch 11111111-1111-4111-8111-111111111111 \
  --evidence-reference synthetic-rehearsal \
  --confirm-disposable-database gm_or_1_synthetic --chunk-size 100 --max-batches 1
# Resume the same batch; --activate is only for a completed synthetic rehearsal.
python manage.py import_good_moral_receipts --import --activate \
  --batch 11111111-1111-4111-8111-111111111111 \
  --confirm-disposable-database gm_or_1_synthetic
```

Default mode is read-only count classification. Output contains variant/status and anomaly counts, never raw ORs, Student/request IDs, individual amounts or SQL exception DETAIL. Counts are overlapping classifications, not proof of invalid historical payment. The full-source digest is held privately on the batch. Inventory is bounded (100,000 records by default, explicit maximum 1,000,000); only key frequencies/sole claimant references are held in memory. Large-volume production performance/resource approval is **not** claimed: reservation guards inspect source keys and require a separately measured rollout budget.

The command uses three database modes:

1. **DORMANT:** existing receipt writer and validation remain intact; ledger inserts are disallowed. No claim of complete historical non-reuse.
2. **FENCED:** acquiring the control-row exclusive lock drains writers holding its shared lock. Commit the fence before chunking. Database triggers refuse all Good Moral source INSERT/UPDATE/DELETE while observations import; this is a real writer fence, not a flag plus an unprotected dual-write interval. Other domains/read access are unaffected.
3. **ACTIVE:** database checks full source/observation coverage, exact projections and absence of unsupported identifier quarantine before changing the mode. Old projection-only writes cannot commit; new API/service receipt writes require review tokens and durable operation identity. No backwards state transition is provided.

A batch records immutable source count/digest/evidence reference. Each request gets one LEGACY_OBSERVED revision, including missing receipt facts without a fabricated identity. Chunk transactions are atomic with Audit; completed chunks survive interruption and the same explicit batch resumes by excluding already observed requests. Repeat import cannot create duplicate claims/events. Different batch adoption and changed frozen source are refused. After active writes change the original census, an old import replay may be refused; it never reimports new facts over the active ledger.

| Legacy observation | Representation |
| --- | --- |
| Unique canonical number | Permanent BOUND reservation to its sole **observed** request, not proof of inspection |
| Duplicate canonical number | One LEGACY_AMBIGUOUS reservation, null owner, every claim retained non-current; new ordinary use blocked |
| Unsupported format | Exact null-identity quarantined observation; activation blocked, no invented aliases |
| Blank number | Observation only, no fabricated reservation |
| Missing date/amount, zero, non-80, future date | Original values retained; no synthetic payment/verification timestamp or PHP 80 overwrite |
| Negative/nonfinite stored amount | Non-current historical observation; ordinary successor must correct it before becoming a normal claim |
| Issued/cancelled record | Source fields/state untouched; import does not reopen it or reissue a certificate |

Old overwritten numbers are not reconstructable from changed-field-only Audit events. The ledger guarantees non-reuse for safely observed/reserved identities going forward; neither import nor test fixtures prove a complete real historical register.

## Writer inventory and operational prerequisites

Receipt writes were searched across backend source, test and maintenance code. Production correction is `good_moral.services.update_request` via the operational PATCH endpoint. Creation paths set no receipts. `good_moral.models` remains available to ORM/raw SQL writers; database projection guards cover them after activation. No Good Moral admin registration or production payment-import writer was found.

Synthetic seeds in `staging_seed/scenarios/action_ready.py` and `rich.py` call correction services with synthetic ORs/amounts. Timestamp maintenance in `staging_seed/support.py` can update requests; verifier/publication/activity/work modules read them. Existing tests use direct receipt updates and `GoodMoralRequest.objects.create` as fixtures. Those paths remain compatible in DORMANT; old seed/maintenance writers are **not silently upgraded** to bypass active tokens/guards. A later cutover must explicitly adapt or stop them, along with old binaries and any external scripts not present in this repository.

Real cutover still requires numbering/normalization approval, separately authorized count inventory, complete reservation and projection reconciliation, quarantine review, writer drain, compatible clients and an approved controlled pause. Unsupported formats cannot be edited away while the fence is active; resolve aliases/policy in protected staging tooling before designing a production transition. Ambiguous keys may remain reserved without an owner; their receipt completeness/issuance policy belongs to GM-OR-2, not this slice.

Rollback before any ledger evidence exists can reverse/reapply the additive migration on a disposable database. Reversal refuses nonempty identities, assignments, operations or batches. After evidence exists, preserve it and use an identity-aware compatible build or controlled mutation pause; do not drop the ledger or return to the old writable build. A production recovery/unfence procedure is deliberately not exposed by this synthetic command. Restored backups must reconcile claims committed after the backup before reopening writes.
