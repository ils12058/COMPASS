# Program academic-policy design

## Current contract

**VERIFIED CODE FACT:** Program stores UUID, College FK, code, name, active flag and timestamps.
Academic metadata is an exact-code registry projection, independent of Program row status/name.
Classifications are `BACHELORS`, `MASTERS`, `DOCTORAL`; statuses are `CONFIGURED` and `PENDING_POLICY`.
The baseline has 30 Bachelor's Programs with Years 1–4, five Master's and three Doctoral Programs
with pending levels. These are the code baseline's choices, not universal UCN progression policy.
Sources: [be/compass/organization/models.py:89](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L89);
[be/compass/organization/canonical.py:11](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L11);
[be/compass/organization/canonical.py:55](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L55);
[be/compass/organization/canonical.py:64](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L64);
[be/compass/organization/canonical.py:318](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L318).

API unknown identity = null classification, `PENDING_POLICY`, null levels. A changed display name
still matches; a changed code/ancestor code or parent may not. Never infer a new classification from
`BS`, `MA`, a College name, degree wording or a student's lifecycle.

## Representation decision

**PROPOSED DESIGN:** store one current policy directly on Program.

| Representation | Integrity/compatibility | Decision |
|---|---|---|
| Three Program columns | Same row lock and update as Program; no missing one-to-one row; simple existing response projection | Select |
| One-to-one ProgramPolicy | Useful for distinct lifecycle/permissions, but adds join, row-creation races and missing-policy states without demonstrated independent ownership | Reject initially |
| Related YearLevel rows/policy versions | Strong row uniqueness and history, but more joins/locking and effective-policy selection | Defer until a concrete temporal requirement |
| JSON blob + Python fallback | Flexible but duplicates policy and weakens typed constraints | Reject |

Proposed fields:

| Field | Definition | Validity |
|---|---|---|
| `academic_classification` | nullable CharField, existing enum values | null means unresolved, never a fourth invented classification |
| `year_level_policy_status` | CharField, existing enum values, default PENDING_POLICY | non-null; no name-derived defaults |
| `applicable_year_levels` | nullable PostgreSQL ArrayField(SmallIntegerField), no empty default | CONFIGURED = nonempty sorted unique integer list in 1–10, known classification; PENDING_POLICY = SQL NULL |

1–10 is the current stored compatibility domain, not permission for a specific Program to use all
levels. `[]` is invalid, distinct from pending `NULL`. Reject booleans, floats, null elements,
duplicates, unsorted values and out-of-range integers. Service validation and `Model.clean()` should
share the typed validator; model `save()` alone does not run full validation.

PostgreSQL checks must constrain enum membership, known classification for CONFIGURED, status/null
consistency, one-dimensional array, no null elements, nonempty cardinality for configured values,
and membership in the explicit set 1–10. Array containment alone does not reject duplicates/order:
add an immutable-array check expression comparing the array to the ordered allowed subset (bounded
ten elements) or an equally explicit database check; test its NULL/three-valued semantics and raw SQL
bypass. Do not claim Python validators are database constraints. Keep any custom SQL/check helper
local and immutable, and document reverse dependencies if a function is chosen. ORG-1 should select
and rehearse the simplest working check expression; a related table is the fallback if reliable
array checks cannot be maintained. No arbitrary lists or automatic contiguous-range inference.

Use the same persisted-policy accessor in Organization API, Inventory and F4. Move enum vocabulary
out of the seed registry if useful. No live fallback to canonical constants after migration: null
stored metadata must stay visibly unresolved, even when a name looks like a degree.

## Backfill rules

**PROPOSED DESIGN:** Organization `0002` copies a frozen `(Campus code, College code, Program code)`
map of the inspected baseline into matching existing rows using historical migration models.
Freeze the values in that additive migration; do not import mutable live canonical.py or call sync.
Only the three new columns are written. Preserve UUID, parent, code, name, active state, timestamps
and every downstream FK. Backfill inactive matching rows as well as active ones.

| Existing row | Result |
|---|---|
| Exact identity, original name | Copy frozen classification/status/levels |
| Exact identity, approved renamed name | Same policy copy; keep current name |
| Exact identity, inactive | Same policy copy; remain inactive |
| Additional Program, changed code/parent, or unknown ancestry | null / PENDING_POLICY / null; report unresolved identity; no guessing |
| Missing baseline Program | No insertion on upgrade; fresh initialization handles seed separately |
| Apparent spelling variant | No name-based match; explicit reviewed identity resolution later |
| Broken FK/duplicate identity/invalid stored code | Stop preflight with bounded report; do not auto-fix institution data |

Before/after comparison must prove unchanged identity/name/status/parents/FKs and unchanged output
for matched policies. Additional rows keep current unresolved output. A fresh DB has no Program rows
at migration time: the explicit initial seed must populate policy on creation after migrations.
See [migration](migration-and-rollback.md) for frozen baseline and initialization receipt details.

## Individual Inventory behavior and compatibility

**VERIFIED CODE FACT:** `_require_active_program` checks Program, College and Campus. New selection
locks Program but not its parent rows. `_validate_program_year_level` allows `None` during draft;
non-null values must be actual ints in 1–10. Configured metadata restricts membership; pending or
absent metadata adds no membership restriction. Draft writes validate policy when Program/year
changes. An unchanged inactive Program remains draft-editable. Submission rechecks active chain and
policy, requires structured Program/year and saves current Program name as course text. Submitted
records remain locked except their established controlled reopening flow.
Sources: [be/compass/inventory/services.py:542](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/services.py#L542);
[be/compass/inventory/services.py:560](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/services.py#L560);
[be/compass/inventory/services.py:1212](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/services.py#L1212);
[be/compass/inventory/services.py:1419](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/services.py#L1419);
[fe/src/features/inventory/editor/education-section.tsx:31](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/inventory/editor/education-section.tsx#L31).

**TESTED BEHAVIOR:** configured Bachelor invalid levels are rejected; pending postgraduate numeric
compatibility remains; inactive draft/reference and submitted name preservation are covered by the
executed Inventory tests. Unknown policy's permissive membership behavior is a source finding;
ORG-1 must add a dedicated unknown-row test rather than assuming postgraduate coverage proves it.

**PROPOSED DESIGN:** ORG-1 retains these semantics for compatibility, using persisted metadata.

| Policy/input | Proposed ORG-1 behavior |
|---|---|
| CONFIGURED + supported level | Accept subject to normal submission requirements |
| CONFIGURED + unsupported level | 422; do not silently substitute a level |
| Known classification + PENDING_POLICY | Retain 1–10 recorded-value compatibility; show policy pending, never call the range an approved progression |
| Unknown classification + pending | Retain existing compatibility on upgrade; explicit unresolved status, excluded from F4 eligibility |
| No Program / null year | Draft allowed; submission continues to require structured values |
| Previously submitted Inventory | Read/print saved facts; no migration rewrite or retroactive invalidation |

A stricter block on unresolved new submissions is a separate **INSTITUTIONAL DECISION REQUIRED**,
with impact review of existing postgraduate/unknown Programs, remediation and deliberate rollout.
Do not introduce it incidentally in the authority migration. For ORG-2 creation/activation, recommend
known classification and either approved configured levels or explicit authorization to keep levels
pending. Additional existing active unknown rows are preserved as migration exceptions needing
resolution; never auto-classify or auto-deactivate them.

## Good Moral F4

**VERIFIED CODE FACT:** F4 derives academic context from the current Academic Year's submitted
Inventory, plus the current Program metadata. No Program/unknown identity gives
`UNCLASSIFIED_PROGRAM`; Master's/Doctoral gives `POSTGRADUATE_PROGRAM`; Bachelor without a supported
level gives `UNSUPPORTED_YEAR_LEVEL`. A level must be in BOTH Program policy and the fixed
`F4_YEAR_LEVEL_LABELS` (1st–4th Year). Creation also requires CURRENT lifecycle and affiliation;
College text is from current Guidance affiliation while course/major/year are Inventory facts.
Those College/Program sources can disagree; ORG does not unify them or implement SAR.
Sources: [be/compass/good_moral/services.py:418](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L418);
[be/compass/good_moral/services.py:452](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L452);
[be/compass/good_moral/services.py:124](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L124);
[be/compass/good_moral/services.py:818](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L818);
[be/compass/good_moral/services.py:819](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L819).

**PROPOSED DESIGN:** newly approved persisted Bachelor policy works without a Python whitelist.
Keep explicit F4 supported-template levels 1–4 even if a Program later configures Year 5. No
postgraduate F4, level-5 issuance, automatic academic progression or new certificate template is
approved. Any expansion requires institutional form/template and eligibility approval together.
Persisted `CONFIGURED` does not itself authorize a form change.

**VERIFIED CODE FACT:** request creation saves local snapshots. Changing year during preparation is
checked against linked Inventory/current policy, while issuance checks completeness, receipt/preparation
integrity, lifecycle and supported form/template; it does **not** generally recalculate catalog
academic eligibility on every issue. Issued rendering uses saved text/template provenance, not a
new Program name. Existing idempotent creation replay returns the saved request before fresh context.
Sources: [be/compass/good_moral/services.py:735](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L735);
[be/compass/good_moral/services.py:1230](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L1230);
[be/compass/good_moral/services.py:1371](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L1371);
[be/compass/good_moral/services.py:1488](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L1488);
[be/compass/good_moral/services.py:1695](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L1695);
[be/tests/test_good_moral.py:1546](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_good_moral.py#L1546).

## Good Moral F6

**VERIFIED CODE FACT:** F6 accepts bounded reported degree/major/graduation-date facts and saves
`degree_snapshot`, `major_snapshot`, date and applicant text. It does not require current Inventory
or a Program FK and does not infer graduate eligibility from current catalog classification. A
recorded Student lifecycle is needed for creation, but CURRENT/GRADUATING/ALUMNI alone does not
verify the historical qualification. Current local postgraduate study does not erase a reported
prior undergraduate qualification. The API's Bachelor degree-name suggestions are advisory,
currently code-owned; submitted text is not forced into that list.
Sources: [be/compass/good_moral/services.py:849](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L849);
[be/compass/good_moral/services.py:913](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L913);
[be/compass/good_moral/api.py:685](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/api.py#L685);
[be/tests/test_good_moral.py:554](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_good_moral.py#L554).

**PROPOSED DESIGN:** replace suggestion enumeration with persisted active-chain Bachelor names,
without making suggestions an eligibility whitelist. Preserve request validation, graduate facts,
receipt verification and issuance behavior; do not reclassify graduates or reissue certificates.

## Policy changes after records exist

**PROPOSED DESIGN:** current policy plus bounded Audit history is sufficient for initial ORG; no
consumer currently evaluates an effective-dated policy by academic period. A full policy-version
subsystem would not make unsnapshotted historical facts accurate retroactively.

| Change | Current policy/new operations | Saved facts/pending work |
|---|---|---|
| Classification change | Consequential explicit review; quantify affected drafts and pending F4 | No Inventory rewrite; new F4 uses current policy; existing requests retain saved snapshots under existing lifecycle |
| Add levels | Future Inventory can use configured additions within 1–10 | No advancement; F4 remains 1–4 |
| Remove levels | New writes/submission must revalidate current policy | Existing submitted facts stay valid history; drafts receive actionable conflict on submission |
| CONFIGURED → PENDING | Explicit institutional approval and impact; preserve numeric compatibility pending chosen stricter policy | Must not silently make F4 eligible; pending policy cannot supply F4 levels |
| Activate incomplete Program | Require known classification and explicit pending-policy basis or completed policy | Preserve migrated exceptions; new activation cannot silently invent completeness |
| Retire Program | Prevent new operational selection/submission | Preserve submitted facts, issued text and existing authorized history |

For policy changes with unissued F4 requests, provide an impact warning/count and require an
acknowledgment of saved-request behavior. Preserve existing pending request snapshot/completeness
rules in ORG-1; ORG-2/4 may introduce an explicit conflict/re-preparation rule only if institutionally
approved. Do not quietly add eligibility revalidation to issuance. Capture before/after policy and
resource version in the change Audit; if a future approved gate needs exact policy-at-preparation
evidence, add a narrow request-local policy snapshot/version, not comprehensive effective dating.
Already-issued documents remain immutable and printable under saved provenance.
