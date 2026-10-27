# Unresolved institutional and operational decisions

No entry records institutional approval. Owners below are **proposed accountable functions**, not
appointments made by this PR. Source implementation can be reviewed independently; live editing,
migration and release remain blocked until applicable evidence is signed off. A panel recommendation
or passing synthetic suite is not formal authority. All statuses: **OPEN / NOT APPROVED** unless
explicitly described as a completed technical implementation (which still supplies no approval).

| ID / decision | Proposed owner | Required evidence | Operational consequence / release gate |
|---|---|---|---|
| D1 Database-owned Catalog authority | Institutional academic/Registrar authority + repository owner | Recorded ownership decision replacing code-owned synchronization | Blocks operational cutover |
| D2 Cutover/rollback responsibility | Release operator + system owner | Exact artifact/process inventory, stopped old writers, restart control | Blocks deployment and activation |
| D3 Catalog delegates and grant approver | Catalog owner + GCO/security administrator | Named eligible delegates, grant/revoke authority and scope | No real grants; blocks activation |
| D4 Acceptable change basis | Catalog owner | Accepted evidence/reference procedure and accountability | Bounded text is not approval; blocks official edits |
| D5 Official names/code allocation | Registrar/academic owner | Official definitions, uniqueness/allocation procedure | Blocks institutional creation/rename |
| D6 Academic-unit terminology | Academic owner + GCO | Approved College/Academic Unit and Entienza presentation | Blocks presentation acceptance for affected units |
| D7 Program classifications/levels | Academic authority | Offering-specific approved classification and level set | No inferred policy; blocks policy activation |
| D8 Pending/unknown compatibility | Academic authority + GCO | Decision on retained 1–10 compatibility and remediation | Current compatibility retained; blocks any tightening/activation acceptance |
| D9 Active incomplete Programs | Academic authority | Review migrated unresolved offerings; approved remediation | New incomplete activation remains refused; blocks affected use acceptance |
| D10 Expanded F4 years/templates | GCO certificate owner | Eligibility/form/template authorization for any expansion | Existing Years 1–4 retained; blocks expansion, not unrelated source review |
| D11 Pending F4 policy changes | GCO certificate owner + academic owner | Approved treatment of requested/prepared F4 before policy change | Current `catalog_pending_f4_policy_decision_required` remains; blocks consequential edits with pending F4 |
| D12 Retirement/account remediation | Catalog owner + Accounts/GCO owners | Live Student/responsibility cleanup plan and safe reactivation procedure | No automatic reassignment; blocks institutional retirement |
| D13 Open-work and resolved-history access | Office/Follow-Up/provider owners | Resolution/reassignment plan and retained-access acceptance | Open work blocks; stored resolved history does not imply access; blocks retirement acceptance |
| D14 Historical-name presentation | Reporting/academic owner | Acceptance of current labels versus saved snapshots; any future as-of requirement | No effective-dated names; blocks reporting/UAT acceptance |
| D15 Retired Tracer choices | Tracer/academic owner | Historical qualification choice and submission policy | Existing semantics retained; blocks changing historical eligibility |
| D16 Workspace/delegation model | GCO + Catalog owner | Accept independent Catalog-only/relationship/read-only entry | Technical split implemented/tested; blocks institutional grant acceptance |
| D17 MFA continuation acceptance | Security + frontend owner | Review refresh/re-review/no-replay behavior and human usability | Technical behavior tested; manual/UAT gate remains |
| D18 Concurrency and writer participation | Backend/database owner | Review race evidence plus actual external-writer inventory | Cooperative gate implemented; uncontrolled old writers block activation |
| D19 Initialization/adoption and migration review | Database/release owner | Exact migration review, approved seed/adopt action/reference | Receipt implemented; withheld migration approval blocks staging |
| D20 Backup, recovery, UAT and activation | System owner + backup operator + institutional UAT lead | Consistent DB/Audit/key backup, compatible image, signed UAT, separate release/grant approval | Synthetic restore passed; all operational gates remain blocking |
| D21 Restructuring/import scope | Academic owner + architecture owner | Separately approved transfer/merge/code-reuse/import/effective-date design | Out of ordinary CRUD; blocks those operations, not this source PR |

Specific missing operational evidence also includes deployment locale/PostgreSQL compatibility,
immutable web/worker/CLI recovery artifacts, service/storage/key availability, logs/monitoring and
human accessibility/physical-device/native-print checks. None was inferred from local UTF8/C tests.
