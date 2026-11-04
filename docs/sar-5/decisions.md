# Decisions consumed by SAR-5

**Source register:** `docs/sar-0/decisions.md`, D-SAR-01 through D-SAR-20. All entries remain
recorded there as **Open**, with institutional owners.
**Status of this file:** this slice consumes **no institutional decision**. It performs the
terminology retirement that SAR-2A deliberately deferred and records it here instead of rewriting
the historical decision files.

## 1. No decision consumed

| Change | Decision status |
|---|---|
| `NO_AFFILIATION` → `NO_PLACEMENT` | Internal reason code only; no policy meaning changed; no caller or contract depends on the string |
| `Applied — Student's current Guidance affiliation` → `Applied — Student's current academic placement` | Report wording only; the coverage source was already the canonical academic placement |
| `CURRENT_COVERAGE_NOTE` wording | Report wording only; the note already described the canonical placement source |

No mandatory/optional field rule, verification policy, effective-date rule, authorization model,
report reconciliation definition or institutional transition was decided.

## 2. The report wording change does not settle D-SAR-20

D-SAR-20 asks for reconciliation definitions across reports, profiling and operational Student
lists. Changing a display label and a methodology sentence is terminology alignment with the
data source that already exists; it does not define denominators, precedence between Inventory
Program College and current placement, inclusion rules or cross-surface reconciliation. D-SAR-20
remains open.

D-SAR-19 (Inventory Program College vs placement College precedence) is likewise untouched: the
Campus/College coverage filters still use the current academic placement exactly as before.

## 3. Decisions that remain open

- **D-SAR-05** — dedicated Student academic capabilities and the final read/write authorization
  split. This slice adds no capability and changes no authorization.
- **D-SAR-12..20** — multiple degrees, retention, corrections, Student visibility, F4/F6,
  Inventory-vs-placement precedence, report reconciliation. All remain open and untouched.

## 4. Historical wording

`docs/sar-2a/decisions.md` records the two residues as they were at SAR-2A. This slice does not
rewrite that file or add supersession notes to ADRs. `NO_AFFILIATION` and the old PDF label remain
in historical documents as recorded history; they were retired only from live backend code and
report output.
