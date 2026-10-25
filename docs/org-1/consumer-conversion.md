# Live consumer conversion

| Consumer | Conversion / preserved contract |
|---|---|
| Organization API `_program` | get_program_policy; same ProgramSummary keys/enums/nullability; no mutation endpoints |
| Inventory `_validate_program_year_level` | Persisted accessor; configured membership and pending/unknown 1–10 compatibility |
| Inventory `_require_active_program` | Shared `program_has_active_ancestry`; historical unchanged inactive draft handling retained |
| Good Moral `_f4_academic_context` | Persisted classification/levels; unknown remains UNCLASSIFIED_PROGRAM, Masters/Doctoral remain POSTGRADUATE_PROGRAM; independent F4 1–4 restriction |
| Good Moral `.only()` projections | Explicitly fetch all three Program policy columns without hydrating confidential Inventory content |
| Good Moral degree options | Distinct sorted active-chain database Bachelor names; unchanged response and advisory semantics |
| Dataset orchestration | Receipt/schema check instead of direct destructive sync |
| Dataset verification | Receipt and actual persona prerequisites, not global canonical active-membership assertion |
| Dataset reports | Persisted parent-qualified College names instead of Python name dictionary |

[program_policy.py](../../be/compass/organization/program_policy.py) is the single policy validator
and accessor. [selection.py](../../be/compass/organization/selection.py) supplies current-use active
ancestry and active Program queryset. Enum vocabulary moves here from the seed module without wire
value changes. Seed may import the vocabulary, not the other way around.

Remaining canonical references are classified as follows:

- `organization/canonical.py`: frozen installation definitions, seed identity indexes, seed count
  validation and legacy seed/fixture metadata lookup. No database read/eligibility fallback.
- `organization/bootstrap.py`: reads frozen definitions only for explicit initial seed.
- Organization 0002: its own frozen map; no import of current canonical.py or policy code.
- Tests: explicit seed fixture and original baseline assertions. Good Moral fixture builders now
  persist the expected policy rather than relying on implicit name/code classification.
- Documentation/ORG-0/historical outputs: dated descriptions of old behavior; current README/ADR and
  deployment runbook explain the replacement. Old historical text is not executable policy.

Repository searches found no remaining live Program policy reader using canonical_program_metadata
or CANONICAL_CAMPUSES. Additional Programs work without seed registration; unknown Programs remain
unresolved even if their name resembles a known degree. Changing persisted policy, names or status
immediately affects relevant current projections, without overwriting saved historical facts.

OpenAPI comparison is unchanged; generated frontend code is ignored and no contract/frontend source
change is required. Orval regeneration is therefore not necessary for this slice. No client types
are hand-edited or duplicated.
