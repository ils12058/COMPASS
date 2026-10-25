# Current Program policy and academic workflows

Complete policy mutations use the ORG-1 [shared validator](../../be/compass/organization/program_policy.py)
and its existing SQL constraints. Classification is nullable or BACHELORS/MASTERS/DOCTORAL;
PENDING_POLICY requires null levels. CONFIGURED requires known classification and sorted unique
genuine integer levels 1–10, nonempty. No name/prefix inference, postgraduate defaults, partial
policy update, automatic progression or effective-dated policy engine is introduced.

A new active Program or reactivation requires known CONFIGURED policy and active Campus/College.
An inactive draft can hold coherent unknown/pending policy. Existing migrated active unresolved
Programs are preserved, but changing an active Program to incomplete policy is blocked until
retired. There is no caller-provided approval Boolean. A bounded basis records accountability; it
neither verifies institutional approval nor establishes which staff may approve academic policy.
Actual delegation/policy authorization remains outside synthetic implementation.

Every actual policy change while linked pending F4 exists fails closed with
`catalog_pending_f4_policy_decision_required`, regardless of whether a client calls it harmless.
A no-op remains a no-op. Requested and ready-for-issuance F4 records both count. Do not silently
cancel, reclassify, reprepare, issue or rewrite existing requests. Resolving pending-F4 treatment
requires the institutional certificate owner; no bypass/acknowledgment field claims that approval.

| Consumer | Current behavior and preserved facts |
|---|---|
| Draft Inventory | Current Program/year edits use current policy; unsupported stored draft year conflicts at submission; unrelated unchanged draft edits retain ORG-1 behavior |
| Inventory submission | Shared gate prevents policy/status change midway through validation/snapshot; configured membership enforced |
| Submitted Inventory | Year/course text and submitted facts remain unchanged after rename, retirement or policy change |
| Pending/unknown Inventory | Existing 1–10 recorded compatibility retained; not permission for new incomplete Program activation |
| New F4 | Uses persisted Bachelor policy and submitted Inventory academic context under shared gate; supports only 1st–4th Year |
| Pending F4 correction | Year correction retains current policy/Inventory checks; catalog policy cannot change while pending F4 exists |
| Issued F4/F6 | Saved certificate facts/template/issuer provenance retained; no catalog eligibility recheck added to issuance |
| F6 suggestions | Active database Bachelor names remain advisory, never a historical degree whitelist |
| Tracer/reports | Historical FKs and saved answers remain; intended current name joins can show renamed labels |

Program retirement itself warns about pending Good Moral and does not invalidate their saved facts.
Existing F4 uses submitted Inventory policy rather than a new Program selection; this slice does not
invent an additional active-Program issuance or academic-context rule. Current active Guidance
College affiliation remains required for F4 creation. New Inventory selection/submission rejects
inactive ancestry. F4 Year 5 remains unsupported even when a Program configures Year 5.

Impact exposes drafts, submissions, pending F4, other pending and issued Good Moral and Tracer counts.
Those counts are not full eligibility determinations: current lifecycle, academic year, affiliation,
Inventory, opportunity and form/receipt rules still belong to their domains. Synthetic tests can
prove coherent configured edits, draft conflicts, historical preservation and pending-request
refusal. They cannot approve pending activation, new classifications/levels or pending-F4 migration.
Unresolved institutional decisions D7–D11 remain explicit operational activation blockers.
