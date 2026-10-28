# Assignment revisions and database invariants

Core models are in `be/compass/good_moral/models.py`. Identity stores a normalized key, version, nullable protected request binding, state, recorder/time/origin and import provenance. It has no Student FK or mutable receipt date/amount. BOUND requires an established request; LEGACY_AMBIGUOUS has no chosen owner; DISPUTED is represented by the schema but has no ordinary creation/resolution workflow.

Each assignment stores request/identity, original display/date/amount, source, sequence, previous revision, recorder/time, classification, optional bounded reason and import provenance. Its receipt facts never change in place. The only permitted update closes a current claim once, with actor/time/`REVISION` reason and a successor in the same transaction. SQL guards reject deletion, fact rewrites, reactivation, wrong ownership, skipped/wrong-request predecessors and inconsistent sequences.

Current-claim partial unique indexes enforce at most one current claim per request and per identity. A null-identity observation can never be current. Current means the presently attached number-bearing revision, **not** an inspection/payment attestation; a later issuance/cancellation retains its historical attachment. Terminal requests cannot acquire ordinary new/revised receipt facts. RECONCILED is a reserved enum value, deliberately rejected by the current source constraints/guards; no ownership transfer authority exists.

Ordinary amount facts retain the existing nonnegative, finite, two-decimal validation. The database allows anomalous amounts only on non-current LEGACY_OBSERVED rows so it can preserve historical truth. Zero and non-80 amounts are not fee-policy violations in this slice. There is no physical verification model or timestamp.

| Correction | Result after active cutover |
| --- | --- |
| Initial number | New permanent identity and immutable current revision |
| Date/amount/display correction, same current key | Close previous current claim; append successor under the same identity |
| Different number | Reserve new identity; close previous claim; retain old reservation forever |
| Clear number | Append null-identity REMOVED revision, retaining any permitted date/amount draft; no empty identity and no released old key |
| Exact no-op | Durable mutation receipt, no new claim or duplicate Audit event |
| Uniquely bound pending legacy anomaly | Explicit successor of that exact observation; no adoption of another identity; corrected ordinary numeric facts must be valid |
| Unrelated certificate correction | Existing correction behavior; no receipt revision unless receipt facts actually change |
| READY correction | Existing return to REQUESTED and preparation provenance reset |
| ISSUED/CANCELLED correction | Rejected; committed operation replay only returns evidence/current resource, never reapplies old facts |

Design refinement from GM-OR-0: null identity is allowed for an ordinary REMOVED/absence revision as well as legacy quarantine. This is necessary to preserve clearing and date/amount drafts, provide an exact review token after removal, and enforce projection equality without inventing an empty identity. It can never be current. The bounded reason field stays optional, as specified for GM-OR-1; no new required reason form is imposed, and closure uses the controlled REVISION classification.

A null-identity REMOVED revision also records date/amount drafts when no number exists. `receipt_identity.revision_id` is the latest **fact revision**, including absence/quarantine, while `is_current` applies only to an attached number. This makes expected-version checks unambiguous after clearing.

Existing request receipt fields remain the compatibility projection. Under ACTIVE, deferred constraint triggers require exact equality with the latest immutable revision (or empty/null facts on a brand-new receipt-free request). Direct old-writer changes cannot commit an unreserved receipt. Historical issued receipt fields/form/template/applicant/issuer facts are never rewritten by import; the existing renderer continues to use them. No receipt gate was added to historical download or printing.

History in operational detail is capped at 20 own-request summaries; it exposes revision/source/recorder/time/closure, not a global OR directory. Student self detail does not gain staff history. Raw prior facts remain restricted domain evidence, rather than general Audit metadata or outbound notifications.
