# Deactivation, routing and ongoing work

Synthetic tests pass the implemented blocker and warning contract. No actual Student population,
Counselor workload or institutional retirement decision was inspected.

`catalog_services._impact` computes each category with actual FK/subquery predicates, independently
of joined display names: Campus child Colleges; descendant Programs; all/active Student-role and
inactive-account affiliations; responsibility rows; draft/submitted Inventories; Tracer College OR
Program references; open Office and resolved threads; pending Good Moral/F4 and issued certificates;
pending OPERATIONAL Follow-Ups through current College affiliation. OR predicates avoid counting a
Good Moral/Tracer record twice when both relationships match. Tests verify aggregate shape/counts
and absence of confidential bodies/answers. They do not claim counts for text-only F6 history that
has neither Inventory nor current-affiliation linkage.

| Target | Hard blockers | Warnings / retained facts |
|---|---|---|
| Campus | Active child Colleges; active Student-role affiliations, any responsibilities, open Office work, pending operational Follow-Ups below it | Inactive-account affiliations, drafts and pending Good Moral warn; inactive children/history retained |
| College | Active Programs; active Student-role affiliations; any responsibility; open Office threads; pending operational Follow-Ups | Inactive-account affiliations, drafts and pending Good Moral warn; historical records preserved |
| Program | No affiliation/Responsibility FK is invented | Drafts/pending Good Moral warn; submitted Inventory, issued certificates and Tracer remain |

Actual Student lifecycle values are **CURRENT, GRADUATED, FORMER**. The active-role blocker covers all
three, not just CURRENT. Stale/inactive Counselor responsibility rows still block. No workflow
silently removes relationships, substitutes Head fallback or reassigns Counselors to make retirement
succeed. Program warnings were not converted into new institutional blockers.

Preview is advisory. The independent-connection affiliation/responsibility tests observe a permitted
preview, insert a dependency while holding the shared gate, then observe deactivation wait and
recount under the exclusive gate. It refuses despite an unchanged Catalog version. A target version
is not a reservation for dependencies.

Routing regressions cover explicit Counselor resolution, absent/inactive/wrong-role responsibility,
unique Head fallback, ambiguous/inactive Heads, inactive Campus/College, StaffSupervision and GSS
dynamic scope, role transition and account reactivation. Account enable checks retained invalid
relationships and returns `organization_relationship_conflict`; no invalid placement is silently
restored. `test_account_reactivation_vs_college_retirement` exercises the actual supported account
service concurrently. Existing Account Management tests cover neighboring account transitions.

New ORG-4 work races open actual encrypted Office threads/create actual operational Follow-Ups and
observe gate waits before the Catalog recount. Tests assert specific open-work blocker counts and
retained work. Other new tests resolve/complete synthetic work, retain its ciphertext and inactive
affiliation, remediate the responsibility fixture, and demonstrate permitted College retirement.
Existing Follow-Up tests cover reassignment, completion, cancellation, current supervision loss,
confidential-source rules and lifecycle replay. Reassignment alone is not completion and does not
remove a pending-work blocker.

Resolved threads remain stored, but current scope-based staff access may shrink after retirement.
Retention is not an extra historical-access grant. Office handler assignment is workflow attribution,
not confidentiality ownership. Counselor-owned records keep their provider policies. Catalog-only
impact contains aggregate categories and no unauthorized remediation links.

No test invents institutional remediation authority or proves an old external writer participates
in the gate. Choosing how to resolve live workloads and historical visibility belongs to the GCO,
account, message and Follow-Up owners before activation.
