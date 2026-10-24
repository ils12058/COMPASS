# Open institutional and release decisions

All entries are **INSTITUTIONAL DECISION REQUIRED** or explicitly technical release gates. No panel
recommendation, old ADR source citation or test result is approval. No operational count or deployed
grant was obtained. Recommended defaults are design proposals, not institutional facts.

| ID / decision | Recommendation and evidence | Gate / decision owner |
|---|---|---|
| D1 — Live catalog authority | Accept DB authority with frozen initial seed; replace/refine ADR-064 deliberately | ORG-1 architecture review by repository/domain owners; institutional catalog authority acknowledged |
| D2 — Cutover/rollback ownership | Fully stop old binaries/CLI writers, enforce minimum compatible release; no rolling overlap. A marker alone cannot stop old writers | ORG-1 release/operator approval; external timers/old credentials/deployed image inventory still UNVERIFIED |
| D3 — Institutional catalog editor | Dedicated catalog.manage, no automatic grants; decide IT-only vs explicit eligible staff delegation and who approves it | ORG-2 permission model; separate operational grant activation approval |
| D4 — Approval evidence | Bounded reason/basis reference where appropriate; do not mandate invented memo numbering or dual approval | ORG-2 mutation workflow; institution/GCO/catalog owner |
| D5 — Official codes and names | Current COMPASS codes are not established Registrar/SIS identifiers; stable code and UUID after create, ordinary official name edits only | ORG-2 input guidance; institutional owner confirms naming/code allocation process |
| D6 — Academic-unit terminology | Keep College relational model and Entienza projection; decide display “College / Academic Unit” with actual institutional terminology | ORG-3 copy; no generalized hierarchy without a requirement |
| D7 — Program classification/levels | Approve each new offering's classification and configured level set; no universal Bachelor/postgraduate inference | ORG-2 create/policy activation; institutional academic authority |
| D8 — Pending/unknown Inventory policy | ORG-1 preserves current 1–10 recorded compatibility for pending/unknown. Decide whether later new submissions must block unresolved policy and how existing users are remediated | Any behavior tightening after foundation; institutional academic/GCO approval |
| D9 — Active but incomplete Programs | Preserve migrated active unknown rows; recommend known classification plus configured levels or explicit pending-policy approval for new activation | ORG-2 activation contract, no silent retirement of old rows |
| D10 — F4 supported years/forms | Retain 1st–4th Year and Bachelor eligibility. Expanded Program levels do not expand F4 template capability | Any future F4 expansion requires form/template plus institutional eligibility approval; outside ordinary ORG |
| D11 — Pending F4 after policy change | Keep existing saved-request behavior in ORG-1; ORG-2 impact warning/acknowledgment. Decide if specific changes require hold/re-preparation; issued documents never rewritten | Before enabling consequential policy edits; GCO certificate owner |
| D12 — Retirement/remediation | Active Students (all lifecycle states), responsibility rows and active children block as specified; inactive-account affiliations warn with explicit reactivation repair | ORG-2 blocker tests; institution/GCO and account owners agree precise rule |
| D13 — Open workflow ownership | Identify pending Guidance threads/queues that would lose access; prove retained relationship access or require explicit owner remediation | ORG-2/4 status-change contract; each domain owner, no blanket historical blocker |
| D14 — Historical names in Tracer/reports | Current labels over stable UUIDs initially; decide whether formal as-of names require small submission snapshots | ORG-4 history/output acceptance; institutional reporting owner; do not invent past names |
| D15 — Retired historical Tracer choices | Preserve submitted records and valid historical qualifications; decide explicit historical inactive-choice UX versus current offering choices | ORG-4 Tracer compatibility; academic/reporting owner; no incidental eligibility change |
| D16 — Catalog-only workspace entry | Permit expressly authorized staff Catalog access without relationship authority; existing managers see read-only Catalog; Students keep selector-only access | ORG-3 navigation/role review |
| D17 — MFA continuation for Catalog | Refresh impact/version and require deliberate catalog confirmation after security transition; reconcile current one-shot helper with FE guideline | ORG-3 action contract; frontend/security owners; no change to existing relationship behavior |
| D18 — Concurrency implementation | One cooperative shared/exclusive transaction gate plus resource versions/unique keys; old-process retirement separate | ORG-2 technical review and actual PostgreSQL race evidence |
| D19 — Initialization receipt/checks | Narrow receipt/adoption design; exact array check implementation; freeze map and register additive migration | ORG-1 technical review; no need for CODE/DB authority state machine |
| D20 — Recovery/UAT/activation | Compatible rollback image and consistent backup; manual accessibility and institutional UAT distinct from synthetic checks | ORG-4 release readiness; separate explicit deployment/grant authorization |
| D21 — Restructuring/imports | Transfers, mergers, code aliases/reuse, effective-dated hierarchy and institution-wide imports require separate controlled scope | Future proposal, never ordinary ORG-2 CRUD |

## What can proceed without resolving every institutional choice

ORG-1 implementation can proceed from this design after the architecture/cutover/compatibility
choices D1/D2/D8/D19 are accepted. It adds no catalog editor or grants and preserves current
academic behavior. ORG-2 permission scaffolding and tests can be implemented default-deny, but user
activation must wait for editor/policy/retirement choices. ORG-3 cannot invent missing backend
contracts. ORG-4 can build synthetic fixtures without querying real institutional populations.

No unresolved naming or policy question authorizes guessing a Program's classification from its
name, fabricating postgraduate levels, changing Student lifecycle or removing StudentAffiliation.
The task's explicit exclusions remain in effect in every handoff.
