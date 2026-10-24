# GM-OR-1 through GM-OR-4 handoff

**PROPOSED DESIGN.** These are separate future PRs against the agreed integration lineage. GM-OR-0 changes documentation only. Neither this plan nor audit approval authorizes live migration, deployment, exceptional transfer or automatic merge.

## Dependency order

`GM-OR-0 audit → normalization/identity decisions → GM-OR-1 identity/history → inspector/fee/cutover decisions → GM-OR-2 verification/gates → GM-OR-3 operational UX → GM-OR-4 integrated validation → separately approved release`.

GM-OR-1 may ship additive dormant schema before gate activation. No slice may open unreserved legacy identifiers to new claims while backfill is incomplete. Keep an identity-aware maintenance/read-only fallback available after writer cutover. Capability synchronization and contract generation must happen in the owning slice, in order; do not hand-edit generated clients or merge simultaneous divergent contracts.

## GM-OR-1 — Receipt identity and history

**Result:** a receipt identifier survives clearing, replacement, cancellation and later requests, while ambiguous legacy claims remain nonexclusive and blocked.

| Item | Concrete handoff |
| --- | --- |
| Models | Add `GoodMoralReceiptIdentity` and immutable `GoodMoralReceiptAssignment` revisions, import/quarantine provenance, permanent binding, current-claim indexes and relationship/immutability guards from [identity design](receipt-identity-design.md#proposed-core-schema). No Student FK duplication and no physical-verification claims. |
| Migration | Tentative `good_moral/0002_receipt_identity_and_history.py`, additive registry entry; dependencies on canonical Good Moral/accounts schema. Exact next number rechecked at implementation. Add protected tables, named unique indexes/CHECKs/constraint triggers; no request-field uniqueness, baseline edits or reset. Explicit resumable backfill command, not automatic unreviewed live data rewrite. |
| Backend files | `good_moral/{models,services,api}.py`; a focused receipt normalization/identity service module; management command for protected dry-run/import; migrations; `common/canonical_migrations.json`; `audit/{actions,metadata}.py` as required; current-state tests plus new identity/legacy/concurrency tests. Enumerate admin/import/script writers before cutover. |
| API | Keep receipt creation absent from student/assisted payloads. Route existing operational correction receipt changes through identity service. Add expected resource version to correction (required at cutover), current revision/limited operational history/legacy state to detail/actions, stable safe receipt-conflict code and mutation operation identity. Existing number/date/amount response fields become managed projections. No standalone global receipt lookup endpoint. |
| Capabilities | **None added or broadened**. Current clerical prepare authority still controls entry; history visibility stays in existing operational role/capability scope. |
| Audit | Proposed `good_moral.receipt_assigned`, `good_moral.receipt_revised`, `good_moral.receipt_removed`, `good_moral.receipt_legacy_imported`; preserve existing request update/return-to-preparation events. Reference domain IDs/changed field names/source batch, not raw OR/Student/payment facts in metadata. No duplicate events on operation replay. |
| Critical dependency | Confirm full printed identity scope, case/character rules and legacy quarantine protocol. Obtain separately authorized real-data inventory before population/activation. Reconciliation remains unavailable. |
| Rollback | Dormant empty schema reversible in rehearsal. Once reservations exist, preserve tables/history; only compatible writer rollback or controlled mutation pause. Never old writable code or ledger drop. |

Acceptance/test gates:

1. Same canonical identifier conflicts across F4/F6, Students, all statuses and superseded claims; empty receipt creates no identity. Cancellation/clearing/number replacement never releases it. Same-current-number fact revision remains possible and attributable.
2. Table-driven normalization tests include case/space rules, zeroes, punctuation/prefix distinctions, max length, blank/nontext/Unicode/control rejection and legacy quarantine. No lossy diagnostic key becomes the identity key.
3. Migration fixtures include unique complete/incomplete, issued without OR, duplicate across Students/statuses, cancelled, unsupported format and unknown former assignments. No arbitrary winner or changed issued field/state; imports are idempotent, bounded and resumable.
4. Real PostgreSQL multi-connection barrier test proves one winner on simultaneous same-key assignment, safe 409 loser and no partial records. Test same-request competing corrections and stale tokens, key-specific IntegrityError mapping, rollback on Audit failure and database guard bypass attempts.
5. Canonical hashes/registry/graph/drift and OpenAPI check pass; client regenerated for development and not manually edited/committed against policy. Existing Good Moral suites still pass under the explicitly staged compatibility policy.
6. Before activation, every source number is reserved or in blocking quarantine, old writers drained and fenced, count reconciliation complete and exceptions documented. A feature flag alone is not a writer fence.

## GM-OR-2 — Physical inspection and preparation/issuance gates

**Result:** only a complete, valid, uniquely bound, physically inspected receipt with an applicable approved fee decision can qualify for a new READY/ISSUED transition.

| Item | Concrete handoff |
| --- | --- |
| Models/migration | Tentative additive `good_moral/0003_receipt_verification.py`: verification/invalidator/operation/policy fields and partial uniqueness for one active attestation per revision. Add nullable `issued_receipt_assignment`/`issued_receipt_verification` PROTECT references to future issue provenance; null remains valid for legacy ISSUED. Relationship guards ensure referenced claim belongs to request and verification to claim. Existing issued receipt fields remain frozen renderer facts. Register migration; no historical verification backfill. |
| Fee model | Initially no fee table. One versioned code-owned approved expected policy (PHP, Decimal, F4/F6, authority/applicability reference), with applied policy ID/expected amount/result recorded on attestation/issuance evidence. Add a dated schedule/table only with approved ranges and real maintenance need. |
| Backend files | Receipt service, `good_moral/{models,services,api,work}.py`, new fee policy module, `accounts/policy.py` and supported policy sync/migration convention, Audit validation/actions, canonical registry, contract export/tests. `work.py` retains preparation/issuance role separation; optional blocker projection, no payment queue. |
| API | Proposed `POST /api/v1/good-moral/requests/{request_id}/receipt/verify` with expected request version, exact claim revision, explicit physical-inspection method and operation UUID. Actor/time are server-owned. Add verification state/provenance, applicable expected-fee result, `can_verify_receipt`, and structured blockers to operational detail. Student detail gets its own safe receipt status, not unrestricted staff history. Strengthen issue review with expected resource version alongside existing preparation version; maintain already-ISSUED replay behavior. |
| Capability | Define focused `good_moral.verify_receipt` with prepare/view dependencies and existing Counselor/GSS role fence. **Approved grant matrix required**, no silent role-wide grant or new IT/Student authority. Issue remains Counselor-only. |
| Audit | `good_moral.receipt_verified`, `good_moral.receipt_verification_invalidated`; preserve issue/prepare/cancel/update events. Tie final issue evidence to exact claim/verification/policy, and retain original actual issuer. No new receipt email/notification needed. |
| Critical dependencies | GM-OR-1 complete and populated; confirmed inspector authority, fee applicability/reference date, old READY transition and mismatch procedure. No fee exception/transfer UI without separate approval. |
| Rollback | Preserve attestation/history/identity. Compatible build or mutation pause; a return to weaker gates is an explicit operational decision, not automatic schema reversal. Never block historical PDF/download by applying new gates retroactively. |

Acceptance/test gates:

1. For both variants test every missing field, zero/nonmatching/negative/nonfinite/overprecision amount, future date, unresolved fee range, unverified/superseded/disputed/ambiguous claim, wrong binding and stale verification. Historical dates remain allowed where applicable policy is confirmed; no invented lower date bound.
2. Verify uses personally inspected exact saved facts; entry alone cannot verify. Receipt number/date/amount correction invalidates current inspection; unrelated certificate changes retain it while requiring preparation again. Clear/cancel never release identity.
3. API and direct service tests deny Student, IT Admin, inactive/revoked/expired/dependency-denied actors, and deny GSS final issuance even with an issue override. Head designation does not create extra rights. Test capability policy synchronization without broadening unrelated grants.
4. PostgreSQL races: correction-versus-verification/preparation/issue, cancellation-versus-verification, two verification operations, stale Counselor final review, and lost response/identical retry. Assert side effects and actor attribution exactly once; uniqueness and ownership guards also work outside normal service calls.
5. Legacy ISSUED snapshots, blanks/different amounts, Student-owned history and PDF release Audit remain accessible; no fake verification timestamps. Old READY cannot bypass the gate. Issued replay does not create more feedback opportunities or notifications.
6. F4 Inventory/Exit Interview/lifecycle and F6 degree-claim/regression coverage pass. Schema/client contract tests include new payloads/errors/action flags and no receipt creation fields. No notification disclosure-policy or print subsystem changes.

## GM-OR-3 — Existing operational and Student UX

**Result:** staff can record then explicitly inspect receipts within current Good Moral pages; Students understand Cashier/GCO steps after requesting.

| Item | Concrete handoff |
| --- | --- |
| Frontend files | `good-moral-correction-form.tsx`, `good-moral-preparation-section.tsx`, `good-moral-issue-section.tsx`, `good-moral-counselor-detail.tsx`, `good-moral-student-detail.tsx`, request/assisted/detail/shared/access/list modules and existing portal work invalidation. Existing `good-moral-{issued-pdf,pdf,print-preview}` behavior retained. |
| Models/migrations | None expected. Consume backend-owned fields/actions from GM-OR-1/2; no invented client receipt state or mock policy. Backend contract generation precedes frontend work. |
| UX | Enhance existing receipt section/editor: number/date/actual PHP amount, applicable expected fee/result, inspection state/actor/time, explicit non-prechecked confirmation, restricted bounded history, duplicate conflict and missing-receipt blockers. Add post-request Cashier→GCO steps with reference; retain initial receipt-free request. |
| Copy | Apply [copy inventory](current-state-audit.md#ux-and-copy-inventory) only once corresponding backend gate exists. Use “Receipt verified” and “physical receipt inspected”; never “Cashier payment verified.” Explain required-before-ready/issuance without demanding prepayment at initial creation. Keep external signature/Registrar dry seal guidance. |
| API/capabilities/audit | No separate grants or new endpoint design in UI. Consume `can_verify_receipt`, canonical roles/action flags and safe errors. No client-supplied verifier/time, receipt facts in analytics, or outward receipt notifications. |
| Critical dependencies | Backend gates/contract and approved fee/authority ready. Existing `fe/AGENTS.md` PageHeader/Panel/ContextHelp, form, confirmation, stale-state and responsive conventions apply. |
| Rollback | Previous UI can be read-only/limited only if backend continues enforcing invariants. Do not remove backend gates to restore an older button flow; warn/block unsupported mutation clients. |

Acceptance/test gates:

- Extend `good-moral-{preparation,print,assisted,request-standardization}.test.mjs`; browser suites for self/assisted request, staff receipt editing/inspection, stale/conflicting operators, preparation blocker and Counselor issue/print. Preserve actual draft while exposing fresh saved version after stale edit; never auto-resubmit.
- Test keyboard-only and screen reader labels/status announcements/focus; pending/refresh-failure states; small screen/zoom/long OR wrapping; shared help and confirmation anatomy. No verification status shown only through color, no falsely successful inspection after timeout.
- F4/F6 request success requires no receipt; fee copy comes from applicable approved policy; Student cannot edit receipt, inspect others' histories or acquire GCO rights. Request references identify the intended certificate.
- Issued PDF preview/download/print retries remain independent from issuance. Existing native print prompt is preserved; headless browser tests do not claim physical print or dry-seal proof. No redundant receipt workspace or new Cashier/Registrar state.

## GM-OR-4 — Integrated validation and release evidence

**Result:** documented evidence that the combined design protects current operations, legacy data and PostgreSQL concurrency; no new feature scope.

| Item | Concrete handoff |
| --- | --- |
| Files/domains | Good Moral backend/model/API tests, dedicated receipt/migration/concurrency tests, canonical registry assertions, contract tests, existing frontend/browser print/request/assisted tests, migration rehearsal fixtures and release runbook/evidence docs. |
| Models/migrations/API/capabilities | None newly planned. Fixes discovered during validation must have explicit owning-slice review; rehearse already approved additive migrations and policy synchronization. No exception workflow slipped into validation. |
| Audit | Assert each mutation's attributable domain event, no raw receipt metadata/log leakage, rollback behavior and no duplicate notification/feedback/verification side effects on retries. |
| Dependencies | GM-OR-1/2/3 integrated in order; institutional decisions signed off; authorized count inventory and controlled data-access procedure ready; supported historical renderer versions available. |
| Rollback | Rehearse interrupted imports, compatible-build fallback/mutation pause, preservation of nonempty ledger, restored-backup gap reconciliation, retained reads/PDFs. Separate future deployment approval required. |

Required evidence bundle:

1. **Domain regression:** three existing Good Moral suites plus new receipt tests; F4 classification/current-year Inventory/Exit Interview and CURRENT recheck; F6 claimed qualification/postgraduate reenrollment; self/assisted ownership, persistent replay, account/capability denials and terminal immutability.
2. **Migration:** fresh PostgreSQL install and existing canonical-baseline upgrade with all legacy classes, duplicates/no winner, unknown prior receipt history, invalid formats, incomplete/zero/different fee/future dates, cancelled/issued states, no fabricated verification, exact private before/after fact comparison and import rerun/resume.
3. **Concurrency:** independent real PostgreSQL connections/barriers, not SQLite or mocked `.exists()`. Force all race pairs listed in [identity protocol](receipt-identity-design.md#transaction-and-conflict-protocol), including cross-variant/cross-Student and direct constraint violations. Assert one winner/no orphans, stable 409, lock ordering/timeout recovery and retry identity.
4. **Documents/print:** compare historical saved render contexts and HTML/normalized PDF text/page count for F4 old/current template versions and F6, blank receipts/different amounts/long values; pinned form/issuer metadata unchanged after profile/current-form changes. Verify actual Chromium generation and release Audit. Avoid binary PDF equality where renderer metadata makes it unstable. Headful/manual supported-browser native-print and physical signature/seal checks remain separate.
5. **Browser/accessibility:** Chromium and WebKit scenarios at mobile/desktop/zoom; staff/Counselor/Student, complete/missing/duplicate receipt, explicit verification/invalidation/stale state, legacy conflict copy, issue confirmation and existing print/download behavior. Manual keyboard/screen-reader/device checks recorded honestly.
6. **Repository/release:** immutable baseline hashes, additive migration registry/graph/drift, OpenAPI export/check and generated-client/type/build checks appropriate to changed files, CI status on exact candidate SHA, no hidden runtime diff. Record pending policy/access/UAT decisions, roll-forward/rollback controls, actor training and separately authorized cutover evidence.

## Release acceptance boundary

GM-OR-1 implementation readiness is **conditional**, not a statement that deployed data are clean. Engineering can implement/test the additive design with synthetic data; live population and new gates wait for institution-approved numbering, inspector, fee and legacy policies. There is no automatic transfer/release of a mistakenly reserved OR. Any future exception workflow requires a separate reviewed slice after authority confirmation.
