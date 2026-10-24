# Integration manifest

## Exact lineage and versions

| Slice | Merged integration SHA | Owning evidence |
| --- | --- | --- |
| GM-OR-0 / #321 | `7f0c75e970f26cc832158f4609295f0dd40938c5` | [Architecture, legacy audit and decisions](../gm-or-0/README.md) |
| GM-OR-1 / #322 | `ef2ba91777ce75391876c36211b2cde83f02188f` | [Reservations, immutable assignments and importer](../gm-or-1/README.md) |
| GM-OR-2 / #323 | `09c7fd82fb1d77cdc1f47d9435d122a2a853ca56` | [Inspection and issuance gates](../gm-or-2/README.md) |
| GM-OR-3 / #324 | `8872db0a7325239ccab6d6f0ca3f68ffd312de8c` | [Operational workflow and Student UX](../gm-or-3/README.md) |

Backend/frontend package versions: 0.1.0 / 0.1.0. Tested Python 3.13.12, Django 6.1.1, pytest 9.1.1, PostgreSQL 17.11; frontend Next 16.3.4, React 19.2.8, Orval 8.29.0, Node/pnpm versions recorded in evidence results. Python and Node Playwright have separate pinned runtimes (1.63.0 / 1.62.1).

Canonical OpenAPI: 3.1.0, API 1.0.0, 417 operations. SHA-256 of `contracts/openapi.json`: `cc16b36ff34ca899d139b503fbfcb33832a4a0ec4f733765f337082079c398b8`. Registry hash: `4722bf480086abbff6bb0c0fb5960e904f6d7efb292d3ef6316581bab1ebf775`. Export check passes; ignored Orval clients regenerated, not committed.

## Good Moral graph

`0001_canonical_baseline → 0002_receipt_identity_and_history → 0003_receipt_verification`, with swappable accounts dependencies. Frozen migration hashes:

| Migration | SHA-256 |
| --- | --- |
| 0001 | `19d2027a7f9dfd57925d6853588f508c65211765a0548c7ae4f396aa892b32a6` |
| 0002 | `131761d2ecdd6119eedadecc16f12cf8b987b75283cdd89192e9c5e957b0e7b7` |
| 0003 | `146bd3dea60786fdb94b67fd37a98dca455249d71ba86f20759e7aed166439ea` |

No historical migrations or registry entries changed. Fresh disposable migrate, drift, registry/hash and migration-executor tests were run again.

## Implementation and test inventory

| Component | Source under repository root | GM-OR-4 evidence |
| --- | --- | --- |
| Canonical identity, corrections/replay | `be/compass/good_moral/receipt_identity.py`, `services.py`, `models.py` | Receipt suite, direct SQL guard and multi-connection tests |
| Import/control fence | `legacy_receipts.py`, `management/commands/import_good_moral_receipts.py`, 0002 | Resume, duplicates, quarantine, cutover refusal and migration suites |
| Fee and inspection | `receipt_fee_policy.py`, `receipt_verification.py`, 0003 | 99 verification cases and 23 coordination cases rerun |
| API authority/contract | `api.py`, `accounts/policy.py`, `authentication/api.py`, `sessions.py` | Canonical contract plus new persisted-session/CSRF matrix |
| Issuance effects | `services.py`, `audit/`, `notifications/`, `feedback/` | Replay and three new injected outcome failures with full database snapshots |
| Existing certificate/print | `documents/`, `fe/src/features/good-moral/` | Six new populated-upgrade PDF comparisons; existing PDF/print suites |
| Receipt UI/account ownership | `receipt-review.ts`, `use-receipt-inspection.ts`, receipt/correction/detail components; portal QueryClient ownership | Node, Chromium/WebKit mocked contracts, actual Chromium/Next integration |
| Selection | `.github/scripts/backend_ci.py` Good Moral group | Three new modules registered; planner tests rerun; workflow triggers unchanged |

F4 still depends on CURRENT Student, classified current-year Inventory, affiliation, semester and applicable Exit Interview. F6 remains a captured degree/date claim. Active final issue retains current Student/form/template/Counselor checks. Audit owns attributable events; issuance notifications and feedback opportunity stay transactionally associated. No payment system, Registrar subsystem, receipt upload or extra print flow is introduced.

The singleton ledger model and migration create DORMANT. `resolve_approved_fee` returns `None`. Policy defines inspection dependencies on view/prepare but adds no baseline role/designation grant. Seeders retain dormant receipt writers; they are not active-compatible cutover tools.
