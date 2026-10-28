# Legacy inventory and safe migration

**PROPOSED DESIGN / future authorized procedure.** No deployed database was contacted. All real F4/F6 counts, receipt formats, duplicates and conflict volumes are **unknown**. The [current-state audit](current-state-audit.md) establishes schema and behavior, not the contents of a deployed database.

## Evidence boundaries

| Evidence | Available in GM-OR-0 | Cannot establish |
| --- | --- | --- |
| Repository source/tests | Exact inspected commit and newly executed existing tests | Actual legacy population or physical receipt authenticity |
| Synthetic PostgreSQL | Baseline tests on PostgreSQL 17.11; inventory query fixture rehearsal described in validation | Production counts, fee authority, future trigger correctness |
| Deployed-data classification | **Not obtained**; procedure below prepared for a separate authorization | No count may be filled from assumptions or old CI/staging reports |
| Physical/Cashier evidence | Team-reported workflow only | Historical inspection timestamps, true owner of disputed receipts, fee effective dates |

## Separate read-only inventory procedure

This is an execution plan for a later authorized operator, **not permission to connect now**.

1. Approve environment, exact schema/application SHA, named operator, read-only database role, purpose and protected report destination. Use the institution's approved connection route; never paste credentials into a report. Confirm the destination without logging connection strings or row values. A read-only replica/snapshot is preferable where authorized and consistent enough for classification.
2. Verify local query against a sanitized schema copy first. Use a bounded repeatable-read/read-only transaction, timeouts, no row locks, no writes, no synchronizers, no resets and no migrations. For a large table, obtain an approved resource/time budget; fail on timeout rather than holding a long snapshot indefinitely.
3. Run count-only classification with all statuses included. Produce counts by F4/F6 and REQUESTED/READY/ISSUED/CANCELLED; missing number/date/amount, complete tuples, zero, non-80, negative, future date, normalized duplicates, formatting variation and recorded prior receipt corrections. Categories overlap and must not be summed as mutually exclusive populations.
4. Keep raw ORs, request IDs, Student IDs/names/emails, amount lists and audit reasons out of stdout, logs, screenshots and PRs. Report only bounded conflict classes (same/different variant, same/multiple Student, status involvement, group-size bucket). Exact aggregate counts can still be sensitive in small cohorts: retain internally and apply institutional small-cell suppression before wider sharing. Do not publish deterministic hashes of guessable OR numbers as anonymization.
5. Only if separately necessary and authorized, a privileged reviewer may inspect a bounded conflict case inside a protected operational session. The count report itself never exports identities. Record inventory tool/query version, schema SHA, execution time, institutional date/timezone, query status and counts; roll back/close even on failure.

### Count-only SQL for the inspected schema

The `GM_OR_V1` candidate key below is **proposed**, not active normalization. `translate` avoids locale-dependent case mapping; non-ASCII/control input is classified for review, never normalized away. Only ordinary outer spaces are trimmed. Compare this candidate to existing raw values before approving the policy. SQL targets the current table names from the inspected models; recheck them before future execution.

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';

WITH base AS (
  SELECT id, student_id, variant, status,
         official_receipt_number AS raw_number,
         btrim(official_receipt_number, ' ') AS display_number,
         official_receipt_date AS receipt_date,
         official_receipt_amount AS amount,
         issued_at,
         (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Manila')::date AS institution_day
  FROM good_moral_goodmoralrequest
), classified AS (
  SELECT *,
    CASE WHEN (raw_number COLLATE "C") ~ '^[ -~]*$'
               AND length(display_number) BETWEEN 1 AND 96
         THEN translate(display_number,
                'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    END AS candidate_key,
    EXISTS (
      SELECT 1 FROM audit_auditevent e
      WHERE e.target_type = 'goodmoral.request'
        AND e.target_id = base.id::text
        AND e.action = 'good_moral.request_updated'
        AND e.outcome = 'SUCCESS'
        AND (base.issued_at IS NULL OR e.occurred_at <= base.issued_at)
        AND (e.metadata->'changed_fields') ?| ARRAY[
          'official_receipt_number', 'official_receipt_date', 'official_receipt_amount'
        ]
    ) AS recorded_receipt_correction
  FROM base
), duplicate_groups AS (
  SELECT candidate_key, count(*) AS claims,
         count(DISTINCT raw_number) AS formatting_count,
         count(DISTINCT student_id) > 1 AS multiple_students,
         count(DISTINCT variant) > 1 AS mixed_variants,
         bool_or(status = 'ISSUED') AS includes_issued,
         bool_or(status = 'CANCELLED') AS includes_cancelled
  FROM classified WHERE candidate_key IS NOT NULL
  GROUP BY candidate_key HAVING count(*) > 1
), totals AS (
  SELECT variant, status, count(*) AS records,
    count(*) FILTER (WHERE display_number = '') AS missing_number,
    count(*) FILTER (WHERE receipt_date IS NULL) AS missing_date,
    count(*) FILTER (WHERE amount IS NULL) AS missing_amount,
    count(*) FILTER (WHERE display_number <> '' AND receipt_date IS NOT NULL
                         AND amount IS NOT NULL) AS complete_tuple,
    count(*) FILTER (WHERE amount = 0) AS zero_amount,
    count(*) FILTER (WHERE amount <> 80.00) AS non_80_amount,
    count(*) FILTER (WHERE amount < 0) AS negative_amount,
    count(*) FILTER (WHERE receipt_date > institution_day) AS future_date,
    count(*) FILTER (WHERE display_number <> '' AND candidate_key IS NULL)
      AS unsupported_number,
    count(*) FILTER (WHERE candidate_key IN
                      (SELECT candidate_key FROM duplicate_groups)) AS duplicate_claims,
    count(*) FILTER (WHERE recorded_receipt_correction) AS known_corrected_receipts
  FROM classified GROUP BY variant, status
), conflict_buckets AS (
  SELECT CASE WHEN claims = 2 THEN '2' WHEN claims <= 5 THEN '3-5'
              ELSE '6+' END AS group_size,
         multiple_students, mixed_variants, includes_issued, includes_cancelled,
         formatting_count > 1 AS formatting_conflict, count(*) AS groups
  FROM duplicate_groups
  GROUP BY 1,2,3,4,5,6
)
SELECT jsonb_build_object(
  'by_variant_status', (SELECT jsonb_agg(to_jsonb(t) ORDER BY variant, status) FROM totals t),
  'conflict_classes', (SELECT jsonb_agg(to_jsonb(c)) FROM conflict_buckets c)
) AS count_only_report;

ROLLBACK;
```

The procedure's current-date reference is the **inventory date**, never an effective date for the PHP 80 fee. The `non_80_amount` column is a review classification, not a finding of invalid historical payment. Numeric database columns cannot recover whether an original input had excess decimal places before rounding.

For near-match analysis, use a second count-only pass over candidate groups where **diagnostic-only** punctuation removal/internal-space collapse/leading-zero simplification would coincide. Count groups and classes; do not use those lossy diagnostics as identity keys or export examples. Also classify case/outer-space collisions by comparing exact-trim keys to the candidate policy. Candidate `formatting_count` already detects raw variation within a normalized duplicate group. Unsupported Unicode/controls require protected review; they are not covered by the ASCII candidate uniqueness proof.

`known_corrected_receipts` means an extant structured Audit event indicates at least one receipt field changed before issue (or while still unissued). It does not recover old values or prove every correction was logged. Audit absence means **not observed**, not “never corrected.” Independently count historical issued rows and their template/form provenance completeness in a protected count-only pass before renderer rehearsal.

## Legacy treatment matrix

| Existing case | Migration representation | Later eligibility |
| --- | --- | --- |
| Unique complete OR, any variant | Preserve raw request snapshot; reserve candidate identity and create LEGACY_OBSERVED revision with import metadata; known sole historical claim may bind identity | Pending must undergo real inspection and fee/date validation; issued stays issued/downloadable without retroactive gate |
| Number without date or amount | Reserve number now; nullable historical claim fact remains null | Pending blocked until corrected and inspected; never fill invented dates or PHP 80 |
| Date/amount without number | Preserve request observation, no fabricated identity | Pending needs a real number; historical issued remains renderable |
| Issued without receipt | Keep issued state and saved certificate fields exactly | Show legacy unknown inspection status; no false claim that old OR history is complete |
| Duplicate candidate key | One permanent LEGACY_AMBIGUOUS reservation, `bound_request=NULL`; import **all** claims as non-current observations | Block new use and pending preparation/issuance involving this key until approved reconciliation; never choose first/oldest/issued as winner |
| Cancelled with number | Reserve and import claim just like any other status | Never release because cancelled; no reopening/correction via ordinary receipt API |
| Zero/non-80/negative/future facts | Preserve observation and historical print facts, with anomaly classification | New pending gates block invalid facts/mismatch; history does not become “unpaid” or void by migration |
| Previously corrected receipt | Import current stored number if known, preserve Audit linkage/unknown-history flag | Old overwritten numbers are unreconstructable from field-name-only audit; no retrospective full non-reuse guarantee |
| Unsupported Unicode/control/format | Preserve exact protected observation with no eligible current identity; reviewed aliases reserved before cutover | Unresolved potential aliases block activation of affected scope; no silent character substitution |
| Existing issued form/template metadata | Leave immutable; historical PDF path uses saved supported identity and facts | Verify renderability; no remapping to newest template or active form |

An import timestamp records **when migration observed a row**, not when a receipt was assigned, inspected or paid. Existing request creation/update/issuance times are not substitutes for verification. No privileged actor is retroactively attributed to legacy inspection. If the source did not store an old OR, this audit cannot discover it without separately authorized physical evidence; document that residual risk explicitly to decision makers.

## Expand / migrate / contract

### 1. Expand (GM-OR-1)

Add `good_moral/0002_…` tables/indexes/constraints on top of the immutable canonical baseline; register additive files in `compass/common/canonical_migrations.json`. Include source/provenance/state shapes, current-claim partial indexes, ownership/immutability guards, and import uniqueness such as `(import_batch, request, observation_kind)` for resumability. Do **not** add unique constraints to dirty request receipt fields. No reset, baseline rewrite, migration fake, or historical data deletion.

Install schema while old columns are retained, but keep identity-enforced writers disabled until population is fenced. Backfill tooling is explicit, bounded, resumable and dry-run/count capable. Prefer a separate controlled migration command rather than a long automatic RunPython over unknown data volume. If an additive data migration is selected later, it must provide the same writer fence and rehearsal evidence; schema deployment alone does not run it against unreviewed payment data.

### 2. Inventory and staged reservation

Obtain the separately authorized count report, normalization confirmation, legacy conflict policy, and pending-record cutover decision. Rehearse all classes on a synthetic PostgreSQL database. Stage every observed number across all statuses **before** admitting new assignments. Reserve unique valid keys and ambiguous keys; preserve invalid observations and evaluate aliases. Imported issued/cancelled claims need not become current/eligible. Unique pending claims may become current but remain unverified.

Do not create a period where new assignments can steal a key not yet backfilled. Recommended smallest rollout is a **short controlled write pause** for all Good Moral writers, drain in-flight requests/workers, take final consistent inventory, reserve/import, validate completeness/counts/checksums privately, then activate only the new writer. Reads and historical downloads can remain available. If a pause is unacceptable, a change-capture/dual-writer fence must first be designed and tested; a naive batch backfill racing old writes is not acceptable.

Within the fence, validate every observed nonblank number has either canonical reservation/claim or explicit protected quarantine; every duplicate has all observations and no exclusive current owner; no issued field/state changed; no verification was fabricated. Reports expose counts only. Record import/source hashes privately without publishing hashes of individual OR values. Failed batches roll back atomically; repeated imports are idempotent. Reconcile final source/observation counts before lifting the fence.

### 3. Writer cutover and verification gates (GM-OR-1/2)

Route existing correction writes through the receipt identity service, including number clearing/replacement and same-number fact revision. Disable/drain old API instances, jobs, admin edits and imports that can bypass reservations; database guards prevent projection writes outside the managed path. Do not leave an old binary writable merely because schema is additive.

Add GM-OR-2 verification tables and pending-request receipt gates after approved authority/fee rules. Existing READY records have no inspection evidence: **block final issue until actual inspection and deliberate re-preparation**. Recommended transition returns these unissued READY requests to REQUESTED with a system cutover event and preserved old preparation evidence in Audit/import evidence; obtain team acceptance first. Do not bulk mark them verified or leave them issuable by grandfathering. ISSUED rows/downloads are untouched.

### 4. Contract (later, only after GM-OR-4 evidence)

Remove independent pending receipt writers and old compatibility paths. Preserve frozen issued request snapshots or migrate them losslessly to an explicitly frozen issued-facts structure before any column removal. Existing response fields can remain projections; no client needs a breaking rename for its own sake. Register any further additive migrations; retain support for historical form/template versions.

## Rollback and recovery

Before future write cutover, a read-only new schema can be abandoned without dropping historical fields. After reservations/claims exist, **keep them**: reversing/dropping the ledger would destroy non-reuse evidence. Before initial activation, schema reversal is permissible only on an empty synthetic installation or after proof the new tables contain no required history.

After activation, fall back to an identity-aware compatible build or put Good Moral mutations into a controlled pause while preserving historical reads/PDFs. Do not roll back to baseline writable correction code. Disabling fee/verification enforcement needs an explicit approved operational decision and must not disable identity reservations. Backfill rollback restores service access policy, not invented source facts; imported historical snapshots remain preserved. A restore of a backup must account for all receipt claims committed after that backup before reopening writes, otherwise it can reintroduce reuse.

GM-OR-4 must rehearse interrupted import/resume, ambiguity preservation, invalid formats, schema upgrade on existing canonical history, writer exclusion, rollback with nonempty history, count reconciliation and historical HTML/PDF equivalence. This audit applies none of these future migrations.
