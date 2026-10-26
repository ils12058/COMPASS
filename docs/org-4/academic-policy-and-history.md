# Academic policy, Inventory and historical outputs

Program policy is stored on Program, validated by `organization/program_policy.py`, and constrained
by PostgreSQL migration 0002. CONFIGURED requires known BACHELORS/MASTERS/DOCTORAL plus a nonempty,
sorted, unique one-dimensional integer set within 1–10. Gaps are supported. PENDING_POLICY requires
null levels; unknown classification remains pending. SQL tests cover nulls, bounds, order,
duplicates and array shape. Python rejects bool/float/string coercion before storage. A SQL cast
can erase original input type; the CHECK protects stored integers, not their original representation.

Active creation/reactivation requires complete policy and active ancestry. Inactive pending drafts
are allowed. Existing migrated active unknowns are preserved. There is no inferred classification
from names/codes, approval checkbox, fallback to Python canonical metadata, forced migration or
automatic certificate re-preparation. Searches of production callers found only seed/definition
uses of the frozen registry; additional database-owned Bachelor's Programs work without code entries.

Every consequential policy change while pending F4 exists refuses with
`catalog_pending_f4_policy_decision_required`. Requested and prepared F4 both count. A no-op is still
a no-op. Independent-connection tests cover F4 creation in both orders and correction versus policy;
the new concurrent complete-policy case refuses a stale second intent. This preserves the merged
ORG-2 contract rather than reviving ORG-0's earlier acknowledgment proposal.

## Inventory

Current selection/submission requires active Program/College/Campus. Configured membership is
enforced; known pending and unknown pending policy retain recorded Years 1–10 compatibility. This
is not approval of academic progression. Existing unchanged inactive draft behavior remains;
reselection/submission refuses inactive ancestry. Policy-versus-submit and retirement-versus-select
races pass; ORG-4 adds retirement-versus-submit on independent connections.

Submitted Program FK, course text, recorded year, submitted timestamp and encrypted answers remain
unchanged. The real browser fixture compares **every persisted Inventory field**, including
ciphertext, after Catalog operations and after renaming, changing policy and retiring its Program.
Existing Inventory context/document tests preserve reopening restrictions and current-label versus
saved-course semantics. Placement remains the separate StudentAffiliation College, not Inventory
Program inference or a new SAR model.

## Good Moral and GM-OR

The selected F4/F6/core/preparation/assisted and receipt/verification suites pass. F4 requires CURRENT
Student status, submitted Inventory context, persisted Bachelor eligibility and supported fixed
first-through-fourth-year labels. Master's/Doctoral/unknown Programs are excluded. Configuring Year
5 does not expand F4 eligibility/templates. F6 suggestions are active database Bachelor names;
graduate-entered historical degree text remains free text and is not turned into a whitelist.

ORG-4 adds two actual authorized F4/F6 PDF retrievals before/after protected Program changes. Each
test preserves the complete issued request row, render context, issuer/template/issuance/receipt
facts and issuance Audit, and compares page count plus whitespace-normalized extracted PDF facts.
PDF binary equality is not asserted. The F4 case changes its actual Inventory-linked Program;
F6 has saved degree text and no Catalog FK, and remains independent of current Program definitions.
Existing six historical migration/import PDF cases also ran. No historical certificate was reissued.

Permanent receipt reservation, correction/invalidation, physical-inspection attribution, fee-policy
restrictions and Counselor-only issuance are covered by existing selected GM-OR regressions.
Synthetic active-policy fixtures stay isolated inside tests. The real integration database and
institutional/deployed GM-OR ledger were not activated. Physical paper inspection is not simulated
as institutional evidence. The print and receipt UI suites add 24 and 37 mocked scenarios per browser
engine; native OS print dialogs/physical paper were not observed.

## Other historical consumers

Graduate Tracer and relevant reports retain UUID references and saved responses while current
Catalog joins can show an official rename. Exit Interview documents and Routine/Inventory decoupling
regressions passed. Guidance/appointments retain provider-owned records, routing references and
scope restrictions. No effective-dated institutional naming or missing historical names were invented.

These are selected regression/source-review and synthetic preservation findings. They do not prove
every report format, stakeholder expectation, production rendering environment or all historical
datasets. Cross-domain assessment remains PARTIAL until institutional presentation acceptance,
authorized UAT and operational compatibility evidence are supplied.
