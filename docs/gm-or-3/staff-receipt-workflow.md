# Staff receipt workflow

Use the existing Good Moral queue and operational request detail. No additional navigation, receipt dashboard, payment workspace or verification wizard is introduced. `good-moral-counselor-detail.tsx` hosts the new `GoodMoralReceiptSection` next to existing request actions and preparation/issuance sections.

## Saved receipt and availability

Saved number/date/actual amount come from the operational detail. Approved expected amount appears only from `receipt_inspection.expected_amount` with backend PHP currency. Currency formatting is presentation, never a client fee comparison. A mismatch keeps the actual printed amount and directs GCO review; policy unavailability does not suggest repeatedly editing payment facts.

All eight backend states have text: Missing receipt, Receipt incomplete, Receipt needs verification, Receipt verified, Inspection not recorded, Receipt needs GCO review, Receipt disputed and Fee policy unavailable. These labels do not create new lifecycle states. DORMANT separately explains that physical inspection is not enabled while existing processing remains available. FENCED explains the pause and suppresses usable correction/inspection/preparation/issuance controls.

Verification provenance uses the actual backend **inspector account reference**, since the contract provides an ID rather than a name. Institutional time uses the shared formatter. No Accounts-directory lookup, inferred name or fake “authorized inspector” attribution is added. History is a collapsed disclosure of at most the backend's 20 own-request metadata rows: sequence, change classification, attachment/historical status, recording time and recorder reference. It is not past receipt contents or an inspection-history API.

## Entry then explicit inspection

Correct certificate details remains the single receipt editor. In ACTIVE its grouping explains required completeness before inspection/preparation, while drafts may still be saved. DORMANT keeps optional entry semantics. Input preserves number/date/actual amount and GM-OR-1 correction review/replay tokens. Saving never invokes verification.

Verify receipt appears only for backend `can_verify`, ACTIVE mode, confirmed detail and no open correction/recovery conflict. It is not derived from a role/capability array. The confirmation names the applicant and request, saved OR number/date/amount and available approved fee, then requires an **initially unchecked** personal physical-inspection attestation. It submits the generated `goodMoralVerifyReceipt` operation with exact resource version, assignment UUID, operation UUID and `PHYSICAL_OR_INSPECTION`. Actor/time/fee authority stay server-owned. No receipt image or Cashier-clearing claim is made.

Pending copy is “Recording inspection…”. A current matching committed result completes the same dialog as “Receipt inspection recorded”, followed by Done. An already verified response refreshes and displays the existing inspector/time. Historical/invalidated outcome evidence cannot become a current success. Receipt verification never prints a certificate.

## Corrections and transitions

A receipt revision after inspection displays that the updated receipt needs another physical inspection; its former evidence remains backend history. An unrelated certificate correction retains exact unchanged inspection and explains re-preparation. Existing READY→REQUESTED behavior remains. Routine save feedback uses the shared ActionStatus; persistent current blockers stay beside receipt/preparation.

Preparation uses backend `can_prepare` and reviewed resource version. The receipt section gives the specific next action; preparation points to that review without duplicating fee narratives. Final issuance remains Counselor-only and uses existing preparation/resource/revision/verification tokens. Its confirmation freezes the reviewed certificate and inspection summary. A changed receipt closes/refuses stale review, refreshes and requires a deliberate new Counselor review. An unsuccessful refresh blocks further issue attempts.

Existing issued PDF preview/download/print, supported form revision, issuer snapshot and release authorization remain intact. No new MFA prompt, automatic printing or Registrar/dry-seal status is added. Historical issued inspection can remain unknown without revoking document access.
