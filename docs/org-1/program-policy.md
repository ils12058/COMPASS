# Persisted Program academic policy

[Program](../../be/compass/organization/models.py) adds:

| Field | Storage / meaning |
|---|---|
| academic_classification | nullable CharField(16): BACHELORS, MASTERS, DOCTORAL; NULL unresolved |
| year_level_policy_status | CharField(16): CONFIGURED or PENDING_POLICY; default pending |
| applicable_year_levels | nullable PostgreSQL smallint array; pending requires NULL, never empty array |

CONFIGURED requires known classification and a nonempty, sorted, unique, one-dimensional list of
actual integer levels 1–10. Gaps are allowed, e.g. [1,3,5]; no contiguous inference occurs. Any known
classification can have an approved configured set or pending policy. Unknown classification can
only be pending. Nothing infers classification from code/name or invents postgraduate levels.

[program_policy.py](../../be/compass/organization/program_policy.py) owns enum vocabulary,
`validate_program_policy` and immutable `ProgramPolicy` returned by `get_program_policy(program)`.
Model `clean_fields` checks before Django integer-array coercion, so bool/float/string inputs cannot
be silently normalized by full_clean. `clean` shares the validator, and initial seed validates it.
Future ORG-2 services must invoke it before writes. As in Django generally, save/bulk/raw SQL do not
implicitly run full_clean; the database checks remain the durable persisted-state guard.

Three Program CHECKs cover classification, status, and coherent null/configured shape. The additive
migration installs `organization_valid_year_levels_v1(smallint[])`, a narrow immutable, parallel-safe
SQL function. It checks dimensions, one-based lower bound, cardinality and equality with an ordered,
distinct range-filtered unnest. Null elements, duplicates, unsorted/out-of-range values, empty and
multidimensional arrays fail. COALESCE(false) and explicit IS NOT NULL conditions prevent PostgreSQL
CHECK's unknown-NULL acceptance from admitting inconsistent states. The function is versioned and
migration-owned; do not replace its definition in place to change policy semantics.

PostgreSQL typed columns may coerce a SQL literal/cast before checking stored state; Python input-type
validation addresses booleans/floats before coercion, while CHECKs enforce the actual stored array.
Do not claim the database can recover the source type of an already-cast integer.

Inventory still accepts recorded 1–10 values for known pending and unknown pending policy. This is
compatibility, not universal institutional progression. Configured membership is enforced. F4 uses
known BACHELORS and intersects configured levels with fixed F4 1–4 labels. Even persisted Year 5 does
not expand F4. F6 suggestions are advisory and do not establish historical qualification.

No current-policy edit service, history-version engine or institution-policy approval workflow is
added. Existing records are not retroactively revalidated or rewritten. Stricter pending submission
rules, new classification rules or supported certificate levels require separate approval.
