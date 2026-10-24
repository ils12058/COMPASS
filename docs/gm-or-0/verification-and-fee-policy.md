# Physical receipt verification and expected fee

## Evidence and meaning

**TEAM-REPORTED OPERATIONAL PRACTICE:** PHP **80.00 per certificate**, same for F4 Current Student and F6 Graduate; each certificate request uses a distinct OR. Student requests first, pays UCN Cashier, receives physical OR, presents it to GCO, then authorized staff inspect/record before preparation, Counselor issuance/printing and external Registrar dry seal.

No signed fee schedule, effective date, waiver procedure, alternative-payment procedure, or reconciliation authority was supplied. These are **INSTITUTIONAL CONFIRMATION REQUIRED**, not gaps an engineer may fill with invented policy.

**VERIFIED CODE FACT:** receipt save is ordinary pre-issue correction; there is no physical inspection model/action or fee comparison. Existing preparation/issuance require certificate facts but permit blank receipt facts. See [current-state evidence](current-state-audit.md#receipt-and-lifecycle-evidence).

**PROPOSED DESIGN:** `PHYSICAL_OR_INSPECTION` attests that “I personally inspected the physical Official Receipt and matched its number, date and amount to this Good Moral request and applicant.” It proves the authorized actor recorded that inspection. It does **not** mean Cashier-ledger confirmation, cleared funds, counterfeit detection, or independent payment-system reconciliation. No “Cashier payment verified” label or online Cashier status is justified.

## Authority choice

| Option | Advantage | Cost / risk |
| --- | --- | --- |
| Reuse `good_moral.prepare` | Smallest policy footprint; current Counselor/GSS preparers already record receipts | Silently makes every preparer an inspection attestor; cannot revoke inspection without disabling clerical work/preparation |
| Reuse `good_moral.manage` | Narrower current Counselor audience | Excludes Guidance Services Staff despite their operational role; confuses certificate correction with inspection and may encourage broadening manage grants |
| New `good_moral.verify_receipt` | Expresses a distinct personal attestation; independently revocable and auditable | Requires policy synchronization, account capability review and explicit grant decision |

Recommend the **focused new capability**, with dependencies on `good_moral.view` and `good_moral.prepare`, enforced together with the existing active `COUNSELOR` / `GUIDANCE_SERVICES_STAFF` role fence. Candidate recipients are only institutionally authorized GCO inspectors within those roles. This is **not an automatic baseline grant** to every existing preparer. GM-OR-2 must obtain an approved grant matrix, implement the canonical capability definition/dependencies and supported assignment mechanism, and test explicit denial/revocation/expiry. If role-wide default grants are approved, enumerate them in that later PR and synchronize using existing identity-policy conventions.

Head Guidance remains a Counselor with its actual capabilities; the designation alone adds no inspection/reconciliation right. IT Administrator can administer approved access through existing governance but does not thereby become an inspector or issuer. Student cannot write or verify receipt facts. Preparation authority remains unchanged; final issuance remains active Counselor plus `good_moral.issue`. No MFA/step-up expansion is proposed for this routine action.

Pending a confirmed inspector matrix, build and test the action with explicit synthetic capabilities but keep operational activation blocked. Do not grant authority by treating receipt save, assisted initiation, preparation or issuance as an implied inspection.

## Verification data and action

Add one attestation record for one **immutable claim revision**:

- Assignment revision FK (ownership and displayed facts resolved by that revision).
- Verifying actor PROTECT FK and aware server timestamp; method enum initially only `PHYSICAL_OR_INSPECTION`.
- Applied expected-fee policy identifier, PHP expected amount and applicability decision evidence; amount paid stays on the claim.
- Operation digest/fingerprint for retry identity, and invalidated-at/by/reason (including system lifecycle reason where applicable).

Derive current state from the eligible current claim plus its non-invalidated attestation: `MISSING`, `INCOMPLETE`, `NEEDS_VERIFICATION`, `VERIFIED`, `LEGACY_UNKNOWN`, `LEGACY_CONFLICT` or `DISPUTED` as appropriate. These are receipt presentation states, **not additional Good Moral lifecycle states**. Do not persist another independently writable `is_paid`/`is_verified` flag on the request. Historical records can have past attestations while no current attestation qualifies them for issuance.

`Verify receipt` is a separate intentional action after saved facts are reviewed. Require expected request version and exact assignment revision; show applicant/request reference, receipt number/date/amount and approved expected fee before confirmation. Reject incomplete/invalid/future-dated/ambiguous/disputed claims and denied actors. Never auto-check the attestation, infer it from a checkbox stored by Student, or upload receipt scans by default. Minimum evidence is the accountable personal inspection; scan storage would require a separate need/privacy decision.

Record `good_moral.receipt_verified` in the same transaction with actor/request/assignment/verification identifiers, method and policy reference. Put receipt fact history in the restricted domain rows; do not duplicate raw ORs or payment information into general Audit metadata, logs, notifications or emails. Follow existing Audit metadata size/shape/sensitive-key validation and define narrow receipt-action metadata at the call site; the current validator is not a receipt-content scanner. An audit write failure rolls back verification.

## Invalidation and corrections

| Change/action | Inspection evidence | Preparation / next action |
| --- | --- | --- |
| Different OR number, receipt date or amount | Invalidate current attestation with actor/time/reason; retain old revision and attestation | Return READY to REQUESTED; save new claim; inspect again before preparing |
| Exact normalized no-op, including decimal equality | No new claim or attestation | No lifecycle change or duplicate Audit event |
| Unrelated certificate correction | Keep inspection of unchanged exact receipt revision | Existing rule still returns READY to REQUESTED; prepare again |
| Saved display spelling changes | Initial conservative design creates revision/reinspection; later harmless-presentation policy may avoid this only if original evidence stays immutable | No silent verified-fact rewrite |
| Clear wrong receipt | Close claim; invalidate any active attestation; retain identity reservation | REQUESTED with missing receipt, cannot prepare |
| Cancel | Preserve past personal inspection; invalidate its current eligibility using a lifecycle reason | Terminal CANCELLED, no issue or OR release |
| Issue | Keep attestation and bind it to final issuance evidence | Terminal ISSUED, unchanged historical rendering |
| Reconciliation/dispute | Suspend eligibility and preserve all previous evidence | Require separately approved resolution and fresh inspection/preparation |

Verification and correction must compete under the same request/identity locks and resource/claim tokens. A person reviewing revision 3 cannot verify revision 4 after another operator's edit. Two verification requests must not create two current attestations; a stable operation replay returns its committed outcome without changing the verifying actor/time. If a different actor tries to verify an already verified unchanged claim, return its current state without replacing the first actor or creating a redundant attestation. A retry cannot reactivate evidence invalidated by later correction/cancellation.

## Preparation and issuance gates

For all **new transitions** after approved cutover:

| State / operation | Requirement |
| --- | --- |
| REQUESTED / initial self or assisted creation | Receipt optional; no prepayment input requirement. Partial entry is not a verified assignment. |
| Verify | Nonblank canonical number; complete date/amount; finite valid amount; date ≤ institution today; current unique BOUND identity belonging to this request; authorized physical inspection; applicable approved fee decision passes. |
| Mark READY | Repeat completeness, validity, uniqueness/binding, no dispute, active exact-claim inspection and applicable expected-fee decision; existing certificate completeness/date checks and authority still apply. |
| Issue | Repeat every receipt gate under lock, verify reviewed versions, plus existing READY/Counselor/F4 lifecycle/form/template/issuer requirements. Snapshot/reference the exact claim and verification in issuance provenance. |
| CANCELLED | Cannot prepare/verify/issue. Preserve all reservations and history. |
| Already ISSUED retry or historical PDF/download | Preserve idempotent return and historical rendering; no retroactive receipt/fee gate, no new side effects. |

Use backend-generated blocker codes/reasons in operational actions rather than making the UI independently compute policy. Examples: `good_moral_receipt_incomplete`, `good_moral_receipt_unverified`, `good_moral_receipt_conflict`, `good_moral_receipt_fee_mismatch`, `good_moral_receipt_policy_unresolved`, `good_moral_receipt_changed`. These are proposed additions to the existing 409 envelope; lexical validation remains 422 and authority remains 403. Duplicate-key errors say “Official Receipt number already recorded” without identifying another Student, request, status, verifier or receipt date. An authorized request view may show that request's own history.

Keep existing request/preparation tokens for compatibility and add exact receipt revision/verification references to review. Require expected resource version on correction and new verification; require current resource version in addition to preparation version on final issue. Do not rely on timestamps alone for claim identity. A receipt/verification/policy-relevant change must invalidate preparation or otherwise make final review stale. Already-ISSUED replay is handled first, preserving current semantics.

Existing READY rows require deliberate review after cutover; do not fabricate inspection or exempt them from future issuance checks. The [migration plan](legacy-data-and-migration.md#3-writer-cutover-and-verification-gates-gm-or-12) recommends return to preparation, with preserved provenance and team acceptance.

## Smallest maintainable fee policy

**Recommendation:** begin with a versioned code-owned expected-fee definition for F4/F6, PHP 80.00, authority marked **team-reported pending institutional confirmation**. It is not an institutionally approved historical schedule. Require operational approval before activation; the audit itself neither approves nor enforces it.

The definition should identify currency `PHP`, exact Decimal expected amount, supported variants, policy ID/version, authority reference and **approved applicability rule**. Persist the policy ID and expected amount/result with verification/issuance evidence so future code changes do not relabel an old decision. Use the existing institutional date helpers for date selection and aware times for actions. Never derive inspection/issue time from receipt date.

| Fee approach | Assessment |
| --- | --- |
| One unversioned `80` scattered in forms/services | Reject: inconsistent changes, no explanation of old decisions |
| Versioned code-owned policy with approval reference | Recommended initially: one maintainer-owned definition, reviewed releases, no unnecessary CRUD; meets current single reported amount |
| Small effective-dated configuration | Justified once approved historical/future ranges or frequent delegated updates exist; requires non-overlap/gap handling, immutable revisions, approval audit and safe activation |
| Cashier fee-maintenance subsystem | Out of scope; receipt matching does not need payment processing or a fee administration portal |

### Dates and future approved changes

**INSTITUTIONAL CONFIRMATION REQUIRED:** choose the charging reference date. Recommendation is **receipt/payment date** because it reflects when money was received, but the institution may use request date or another documented basis. Request creation, inspection and issuance dates must not silently stand in for the fee's effective date.

No start date is known for PHP 80.00. Do not seed `effective_from=2026-10-20`, this audit date, request creation, or “beginning of time.” Software gate activation time is a deployment control, not proof of a fee's historical effective date. Approval must define which pending receipts the initial expected policy covers; receipts outside known coverage return `policy unresolved` and need approved review, rather than being declared valid merely because they equal 80.

At a future approved change, append a new policy ID with the actual approved date/rule/authority reference; retain the prior policy definition and recorded decisions. A small ordered code-owned schedule can support infrequent changes. Promote to an effective-dated table only if operational maintenance demands it. If table-backed, use immutable published rows with no overlapping applicability ranges for the same variant/currency, explicit unknown ranges, retirement audit and tests for boundary dates; do not backdate from engineering guesswork.

Preparation/issuance recompute applicability and compare against the saved approved policy decision. If a new approval changes the decision for an unissued request, require deliberate re-review/re-preparation; do not silently accept a stale quote or mutate old attestations. A legacy receipt with unknown applicability remains unresolved until a policy-approved transitional treatment exists.

### Historical amounts and exceptions

PHP 0.00, PHP 250.00, a missing amount, or another value on an issued record is a historical fact. The repository currently accepts nonnegative non-80 values; that is not evidence of an approved different fee or waiver. Do not rewrite it to 80, revoke issued status, block historical PDF, or mark it verified to satisfy a constraint.

For new/pending work, valid numeric precision alone is insufficient: require complete actual amount, approved applicable expected fee and a passing comparison before receipt verification/readiness. Preserve the entered actual amount on mismatch; do not default or overwrite it with the expected value. Show both values and a review message.

No evidence establishes that waivers, discounts, aggregated payments, excess payments, replacement receipts or refunds are supported **or prohibited**. Do not invent a waiver toggle or use zero as an implicit exception. Until an approved procedure exists, mismatches/unresolved applicability block the new gate and are escalated for institutional decision. Any future approved exception needs a separate attributable authorization, evidence/reason, scope and immutable decision record; ordinary receipt correction and IT capability overrides are not fee-exception authority.
