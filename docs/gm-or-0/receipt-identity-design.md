# Receipt identity, history and correction design

**PROPOSED DESIGN** throughout, grounded in the [verified current behavior](current-state-audit.md). Names below are handoff names, not existing models or implemented migrations.

## Alternatives

| Criterion | A — unique current request field | B — dedicated assignment ledger, unique key on each assignment | C — identity reservation + claim revisions |
| --- | --- | --- | --- |
| DB uniqueness / concurrent assignment | Yes for occupied current values; empty values need special handling | Yes while unique assignment rows are retained | Unique immutable identity key; current-claim indexes and request/identity locking |
| Permanent ordinary non-reuse | **No**: clear/replace releases value | Yes if assignments never deleted/rekeyed | Yes: reservation survives every claim/state change |
| Legacy duplicates | Cannot add constraint without resolving/deleting claims | A unique ledger row cannot truthfully attach multiple old owners; needs an exception structure | One blocked identity, multiple historical observations, no arbitrary owner |
| Date/amount correction | Overwrite unless another history mechanism is added | Requires revisions/history; cannot insert repeated same key under naive uniqueness | Append fact revision under same identity and invalidate exact old verification |
| Number correction | Old number ordinarily reusable | Keep superseded assignment forever | Keep old identity, end current claim, reserve new identity |
| Cancellation | No protection elsewhere | Retain ledger row | Retain identity and all history; status never frees key |
| Historical truth | Current snapshot only | Good for unique known ownership | Explicit observed versus exclusive versus disputed ownership |
| Normalization | Needs separate display/key fields | Same requirement | One canonical key, per-claim display evidence |
| Migration | Simplest only if all history clean and reusable values allowed | Smaller for an empty/known-clean dataset | Additive, supports unknown duplicate inventory; more explicit constraints |
| Transactions/usability | Small change with unmet requirements | Moderate, plus legacy side mechanism | Moderate; reuse current request screens, distinguish blocked legacy claims |

Choose **C**. B plus a legacy exception registry is effectively C with a different name. Two core tables are sufficient if identity carries the durable ordinary binding and claims carry immutable fact revisions. A separate verification table is added in GM-OR-2. Avoid a full payment ledger, Cashier integration, or a receipt administration workspace.

## Identity and normalization

Identity is global across this Good Moral domain: no partition by Student, variant, request status, academic year, or cancellation. The requirement is one physical OR identifier per distinct certificate request; multiple print/download operations of the same issued request do not consume additional ORs.

**INSTITUTIONAL CONFIRMATION REQUIRED:** confirm whether the identifier printed on an OR is globally unique, or whether series/book/office prefixes are essential to distinguish reused numeric sequences. Do not silently add year/Student scope to make duplicates disappear. If a series is necessary, capture the full printed identifier or approve a composite identity before GM-OR-1 activates; the date alone is not an invented uniqueness namespace.

Proposed `GM_OR_V1` for **new entry**, after case policy confirmation:

1. Input must be text; an absent receipt is represented by no current claim, not an empty identity row. Partial receipt entry without a number may remain a request-local draft, never a reservation or verification.
2. Reject characters outside printable ASCII U+0020–U+007E **before** trimming, including tabs, line breaks, DEL, bidi/zero-width characters and non-ASCII lookalikes. Reject embedded nonprintable bytes; never silently remove them. This conservative grammar must be checked against real blank receipt samples.
3. Trim outer ordinary spaces. Reject an empty result. Limit recorded display and canonical key to 96 characters; require an explicit schema/design change if an approved receipt format exceeds that.
4. Preserve the trimmed original spelling as `display_number`. Derive `normalized_key` by uppercasing ASCII a–z only. This is a proposal, not evidence that UCN treats case as identical.
5. Preserve prefixes, hyphens, slashes, dots, other printable punctuation, internal spaces (including their count) and leading zeroes. Do not Unicode-normalize, remove punctuation, collapse internal spaces, strip prefixes, parse numerically, or remove zeroes.

| Entered display | Proposed key | Consequence |
| --- | --- | --- |
| `  or-00042  ` | `OR-00042` | Outer spaces/case equivalent, conditional on approval |
| `OR00042` | `OR00042` | Distinct from `OR-00042` until evidence says otherwise |
| `OR-42` | `OR-42` | Distinct from `OR-00042` |
| `OR 00042` / `OR  00042` | Preserve one / two internal spaces | Different keys; flag as near matches for review, do not auto-merge |
| Full-width letters/digits, en dash, newline | Rejected for new entry | Legacy values remain preserved and quarantined |

Alternative: exact-case key is less assumptive but permits case-only near-duplicate reuse. Recommendation is the explicit ASCII case-insensitive policy above **with confirmation as a release gate**. An expanded Unicode grammar would require precise Unicode/collation behavior and collision rehearsal; no need to accept it speculatively.

Use deterministic bytewise comparison for the normalized key (for example PostgreSQL `C` collation), not deployment-dependent case-insensitive collation. Record `normalization_version`, but **do not** put version in the uniqueness namespace: a policy upgrade must not allow the same identity under V1 and V2. Any future normalization change requires an inventory and collision reservation plan.

Legacy values outside the new grammar remain exact observed evidence. Do not reformat issued fields. Stage them as opaque blocked observations plus reviewed candidate aliases; a raw opaque reservation by itself cannot prove a formatted alias is safe. Unresolved aliases that might collide with admitted new identifiers block activation (or a specifically reviewed affected namespace); they are not simply excluded from the inventory.

## Proposed core schema

| Object | Minimum fields / semantics |
| --- | --- |
| `GoodMoralReceiptIdentity` | UUID; globally unique nonempty normalized key; normalization version; `bound_request` nullable PROTECT FK; state `BOUND`, `LEGACY_AMBIGUOUS`, `DISPUTED`; reservation recorded-at; recorder nullable for imports; source `ORDINARY`/`LEGACY_IMPORT`; import batch/evidence reference. A BOUND row has a known request; ambiguous rows have none. DISPUTED may retain the prior known binding as historical ownership but allows no eligible current claim. No release/delete/rekey operation. |
| `GoodMoralReceiptAssignment` (claim revision) | UUID; identity FK PROTECT (nullable **only** for quarantined invalid legacy observations); request FK PROTECT; immutable display number/date/amount; origin `ORDINARY`, `LEGACY_OBSERVED`, future `RECONCILED`; recorded actor/time (import time distinct from historical event time); `is_current`; optional `supersedes` self-FK; change kind, reason/evidence reference; closed-at/by/reason when current ends. No copied Student FK: ownership derives from request. Only lifecycle closure metadata can change after insertion. |
| `GoodMoralReceiptVerification` (GM-OR-2) | Exact assignment revision FK; verifying actor/time; method `PHYSICAL_OR_INSPECTION`; applied fee policy decision reference/snapshot; invalidated-at/by/reason. Append a new verification after invalidation; never rewrite original attestation. See [verification policy](verification-and-fee-policy.md). |

`bound_request` is a durable ownership binding, **not** another copy of receipt number/date/amount. Assignment request references also preserve nonexclusive historical claims. For legacy duplicates, one reservation has `bound_request=NULL`, state LEGACY_AMBIGUOUS, and several non-current LEGACY_OBSERVED claims. A complete unique legacy claim may establish a historical binding but **does not** establish inspection. No historical record becomes verified by import.

Same-number date/amount correction creates a new immutable claim revision under the existing bound identity. Number replacement creates a **new** reservation and claim; the old reservation stays bound to its original request. A superseded number cannot be ordinarily reactivated, even on the same request. Same current number can be revised only through the current-claim revision path, not a generic “claim existing identity” path.

For a uniquely bound **pending legacy** observation that was staged non-current because of an anomaly, allow an explicit remediation revision of that exact imported observation under its existing request binding. Check request/observation version, no competing current claim, BOUND state and no ambiguity/dispute; append corrected facts and make the successor current only when valid. This is a same-owner legacy correction, not adoption of another reservation. It is unavailable for terminal records or ordinarily superseded assignments, and it never treats import as physical verification.

## Constraints and ownership enforcement

Required database invariants:

- Unique normalized identity key, nonempty bounded key and explicit identity-state shape. Identity key and ordinary binding immutable after reservation, apart from a separately authorized reconciliation path that is **not implemented** in GM-OR-1/2.
- Partial unique index on assignment `request_id WHERE is_current`; partial unique index on `identity_id WHERE is_current`. Legacy duplicates are non-current observations. Null-identity quarantine rows can never be current.
- Ordinary/current receipt amount uses `CHECK ((origin = 'LEGACY_OBSERVED' AND NOT is_current) OR amount IS NULL OR (amount >= 0 AND amount < 10000000000))`; decimal precision remains 12,2. This explicit non-current historical allowance preserves an anomalous legacy amount rather than forcing its deletion or rewrite. Anomalous-amount legacy observations cannot become current; corrected ordinary revisions must pass normal validation. Service rejects excess precision before persistence; the database numeric type may round direct SQL inputs, so do not claim type precision proves validation of the original lexical input.
- Actor/time pairs for ordinary recording and closure; origin discriminator allows unknown legacy actor. Verification actor/time always required. Invalidator/time/reason appear together; method/state constrained. No fabricated actor or historical timestamp.
- Revision links are to the immediately prior **same-request** current claim (number change may link a different identity); links cannot point to self, forward in sequence, or form cycles. Use monotonically increasing per-request revision sequence, unique `(request, sequence)`; a predecessor must have smaller sequence, and locked service ensures the immediate predecessor.
- Issued/cancelled claims cannot be rewritten through ordinary mutation. PROTECT references and application append-only guards prohibit ordinary deletion. A cancelled request may retain its last claim for display, but it is not issuance-eligible.

Ordinary Django row CHECKs cannot enforce joined ownership, same-request predecessor consistency, or cross-table state. Implement a small, explicitly tested PostgreSQL constraint trigger for these invariants (or equivalent composite FK where expressible): a current claim must reference a BOUND identity whose binding equals its request; its predecessor must be on that request; an active verification must refer to the eligible exact claim (invalidated historical attestations retain references to their old closed revisions). Reconciliation must not be able to establish two current owners. Keep role/capability decisions in the service, not SQL. Protect immutable key/fact updates/deletes with database guards plus model/service guards; document migration/backfill privileges. An application `.exists()` call is not the uniqueness authority.

PostgreSQL supports [unique constraints/partial unique indexes and foreign keys](https://www.postgresql.org/docs/17/ddl-constraints.html); cross-row rules require mechanisms beyond ordinary CHECKs. Exact trigger/index names and Django migration SQL are GM-OR-1 work, including forward/reverse rehearsal. No trigger or model is added in GM-OR-0.

## Single source of receipt facts

For new/pending records after cutover, immutable claim revisions are authoritative. Existing request fields may temporarily remain a service-maintained compatibility projection written in the **same transaction**, never separately editable through admin/import/old writers. Expose the current claim via the existing response fields until client migration. Retain original issued request receipt fields as frozen certificate facts; they are not a live receipt editor. Old issued render paths continue reading these snapshots, including blanks/different amounts.

Do not maintain independently writable amount/date/display values on identity, assignment, verification and request. Verification references a revision; it does not copy mutable receipt facts. An expected-fee snapshot is a policy decision, not a second “amount paid.” Later contract cleanup may remove pending projections, but must not drop facts that historical rendering still needs. Document all writers before cutover, including scripts/admin; old application binaries cannot keep writing after identity enforcement starts.

## Transaction and conflict protocol

For every receipt action, atomically authorize the actor, lock the request, check expected resource/revision token, and inspect its terminal status before acting. Do not lock a joined nullable query that unintentionally locks unrelated rows. Use a common lock order: affected request IDs sorted, then existing identity keys sorted, then claim/verification rows. Multi-request reconciliation later follows the same order. Preserve/rehearse existing request→Student issuance and assisted-creation lock interactions.

For **new number assignment**, insert the permanent identity under its unique key within a nested savepoint. Two independent requests cannot lock a nonexistent shared row; the unique index arbitrates the race. Catch only the named identity uniqueness violation outside the savepoint, return the safe conflict and roll back all claim/request/audit changes. Do not treat arbitrary integrity errors as OR conflicts. Do not adopt an existing reservation after a collision; a same-request replay must match the already committed operation/revision.

For **fact revision**, lock the existing identity, close the current claim, append the successor and invalidate its old verification, reset READY to REQUESTED, update the resource version/projection, and record domain Audit events in one transaction. Preparation/issue lock and recheck the same current revision and active verification. Locks are held to commit; [PostgreSQL row-lock behavior](https://www.postgresql.org/docs/17/explicit-locking.html) is the basis, not an assumed race-free UI.

| Competing action | Required outcome / future PostgreSQL test |
| --- | --- |
| Different requests claim same key, F4 versus F6, any Student/status | Exactly one ordinary reservation commits; other 409; no orphan claim/audit |
| Correct versus verify | Exact expected request + claim revision checked under lock; losing stale operation 409, cannot attest to unseen successor |
| Correct versus prepare | If correction first, stale preparation fails; if prepare first, correction resets READY and invalidates receipt verification only for substantive receipt change |
| Correct versus issue | Correction first prevents old issuance; issuance first makes subsequent correction fail as terminal |
| Cancel versus verify | Cancellation first denies verification; verification first may commit historical evidence, then cancellation removes issuance eligibility without releasing identity |
| Two verifies / retry | One active attestation for the same operation and claim; no duplicate audit, actor attribution preserved |
| Stale Counselor review | Require preparation token and current request/claim/verification versions at issuance; never rely on disabled button alone |
| Audit failure / transaction rollback | Reservation, revision, verification and request state roll back together; no success response |

Use a stable client operation UUID for new receipt mutation/verification and a durable unique operation digest with payload fingerprint (on the created revision/verification or a small shared mutation record if needed). Bind actor, request, method and intended revision. Identical replay returns committed result; key reuse with different payload returns `idempotency_key_conflict`. Check exact committed replay before rejecting its now-old expected token. Cancellation after a prior verification does not permit its replay to restore eligibility. No automatic client replay of consequential actions; after uncertain response, refresh and deliberately review. Issue retries keep the existing already-ISSUED behavior with no new side effects.

At READ COMMITTED, preflight reads can become stale; uniqueness exceptions and version rejection are normal conflicts, not evidence to retry a changed payload invisibly. Any bounded internal retry for deadlock/serialization failure must preserve operation identity and rerun the entire transaction; do not retry role denials or business conflicts. See [PostgreSQL transaction isolation](https://www.postgresql.org/docs/17/transaction-iso.html).

## Ordinary correction and exceptional reconciliation

| Operation | New behavior |
| --- | --- |
| Date or amount changes, same current number | New fact revision; mandatory reason; invalidate inspection; preserve paid value as reported; fee mismatch blocks verification/preparation |
| Display-only outer-space/case change | If normalization/display policy treats it as harmless, record display correction provenance without substantive fact revision; do not mutate immutable verified facts. Simplest initial implementation treats a changed saved display as a new revision requiring reinspection. Exact no-op creates nothing. |
| Number replacement | Reserve unused key, append revision and close old; old OR remains blocked forever in ordinary flow |
| Remove wrong entry before verification | Close current claim and clear pending projection; retain reservation and revision with reason, no empty identity |
| Remove/replace verified receipt | Same durable history plus verification invalidation; new physical inspection required before readiness |
| Correct READY | Return to REQUESTED for any certificate change, as today; unrelated certificate correction retains exact receipt verification |
| Correct ISSUED / CANCELLED | Reject ordinary request, as today; do not rewrite historical PDF facts |
| Cancel with OR | Keep reservation, revisions and inspection evidence; no future eligibility and no ordinary reuse |

**INSTITUTIONAL CONFIRMATION REQUIRED:** clerical errors that captured another request's true OR need a distinct reconciliation procedure: designated authority, supporting physical evidence, independent reviewer, reason, affected request review and an immutable resolution record. Recommend Head Guidance oversight plus second reviewer, subject to institutional approval; do not infer that designation currently grants it. No ordinary preparer/IT override may transfer ownership.

Future reconciliation locks all affected requests/identities, ends any eligible current claim before establishing at most one new current claimant, retains every disputed/incorrect claim and prior binding as resolution history, invalidates affected inspection/preparation and requires fresh inspection. It may record a corrected binding only under the approved procedure; **never delete/release the reservation**. An issued request's original certificate snapshot remains intact even if an external resolution records a clerical attribution issue. Until this workflow is approved and separately implemented, disputed/ambiguous keys remain blocked; ordinary correction is not a workaround.
