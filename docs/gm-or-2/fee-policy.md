# Expected-fee policy

**Team-reported practice:** PHP **80.00** for CURRENT_STUDENT/F4 and GRADUATE/F6, one distinct OR per certificate. Constants retain this report as Decimal/currency/variants. It is not a signed schedule and has no invented effective date.

`receipt_fee_policy.resolve_approved_fee(item, assignment)` returns **None by default**. There is no environment flag, client approval input or fee CRUD. ACTIVE fails closed without an approved decision. DORMANT does not introduce partial PHP 80 enforcement. Tests replace this provider with explicitly fictional approved definitions scoped to synthetic fixtures.

`FeeDecision` is immutable: policy ID/version, PHP currency, positive finite two-decimal expected amount, authority evidence, variant, receipt reference date, bounded approved date range, explicit `RECEIPT_DATE_IN_APPROVED_RANGE` rule and APPROVED status. The provider must return a complete matching decision. Receipt date is the implemented contract's reference; institutional adoption of this rule and actual coverage remains a release decision. Unknown coverage is unresolved, never “PHP 80 has always applied.” Deployment/audit/request creation dates do not establish fee history.

Compare exact Decimal actual versus expected. Missing/negative/nonfinite/excess-precision values are invalid or incomplete; zero, PHP 75 and PHP 100 fail under a synthetic PHP 80 decision. Do not rewrite actual amounts, infer waived fees, permit overpayment, refund or reconcile Cashier records. Historical non-80 and missing receipts remain untouched.

Inspection persists the entire structured decision plus explicit policy ID/version/currency/expected amount. Preparation and issuance resolve again and require exact snapshot equality. An amount, version, applicability boundary, authority or reference change cannot silently reuse prior inspection/preparation. A deliberate new inspection creates fresh evidence; old definitions and attestations must be retained. Issued history uses its recorded decision even when a future provider is different/unavailable.

An eventual operational provider must be a separately reviewed code-owned approved schedule with real evidence and applicability, retaining historical definitions and transitional treatment. Concurrent in-process policy loss/change is rechecked before commit. A multi-process code rollout is not a transactional pricing registry: drain old writers under the established release fence before changing the approved schedule. No database fee table is justified by the current single reported fee.
