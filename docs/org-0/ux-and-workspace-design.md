# Organization workspace and Catalog UX

## Existing surface (VERIFIED CODE FACT)

`organization-structure-page.tsx` loads Campus, College and Program lists through generated TanStack
hooks (retry disabled), uses an all-list loading/error branch with retry, then groups by UUID.
It renders read-only hierarchical text in a `max-w-4xl` region: Campus Panel, College rows, indented
Program rows with code, classification/year labels and status. It does not impose fixed 6/10/38
counts, but has no search/filter or catalog mutation actions. First/last-level summarization would
misstate noncontiguous future policy sets as a range.
Source: [fe/src/features/organization/structure/organization-structure-page.tsx:45](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/structure/organization-structure-page.tsx#L45).

Outer OrganizationGate requires `organization.manage`; inner Structure gate separately checks
`organization.structure.view`. Reference reads support other workflows without granting standalone
workspace access. Tabs are Structure, Responsibilities and Student affiliations. Responsibilities
contains Counselor assignment and Staff supervision; Student affiliations retains paginated search,
Campus/College filters, people lookup and assignment/removal. Both use shared consequential dialogs,
feedback/error and recent-MFA handling. No separate staff-supervision tab exists.
Sources: [fe/src/features/organization/components/organization-gate.tsx:14](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/components/organization-gate.tsx#L14);
[fe/src/features/organization/components/organization-navigation.tsx:26](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/components/organization-navigation.tsx#L26);
[fe/src/features/organization/responsibilities/responsibilities-page.tsx:45](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/responsibilities/responsibilities-page.tsx#L45);
[fe/src/features/organization/student-affiliations/student-affiliations-page.tsx:52](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/student-affiliations/student-affiliations-page.tsx#L52);
[fe/src/features/organization/responsibilities/responsibilities-help.tsx:1](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/responsibilities/responsibilities-help.tsx#L1);
[fe/src/features/organization/components/organization-action.tsx:30](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/components/organization-action.tsx#L30).

Current `useOrganizationAction` delegates to `useStepUpContinuation`: a confirmed operation can be
retained briefly in memory for one verify continuation, bound to actor/session; setup retains none.
The general FE guidance also describes deliberate resubmission. ORG-3 must explicitly reconcile
which established behavior fits consequential catalog edits with a stale preview/version; it must
not assume any unsafe request may be blindly replayed or change existing relationship behavior.
Sources: [fe/src/features/account/security/step-up-continuation.ts:38](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/account/security/step-up-continuation.ts#L38);
[fe/AGENTS.md:229](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/AGENTS.md#L229).

## Proposed workspace scope

**PROPOSED DESIGN:** enhance the existing Structure tab; no parallel Catalog application or three
new top-level destinations. Keep the current hierarchy and readable width, with search/status and
Campus/College narrowing as needed. Use lightweight forms/dialogs or a single nested editor route
only if the policy form is too long; any child editor shares Organization navigation and return
context. Do not recreate the archived topology editor.

Recommended gate split for ORG-3:

- Existing operational managers can enter Organization and see read-only structure where they also
  have structure.view. Their Responsibilities/Student affiliations controls remain operational.
- An explicitly authorized catalog manager with structure.view can enter Structure without gaining
  organization.manage or access to relationship records. Hide relationship tabs unless manage exists.
- Reference-only ordinary roles keep their current selector/API access; do not expose the workspace
  to every Student merely because structure.view is present. Any broader staff-only browse authority
  is a separate institutional choice.
- Backend endpoint authorization is the security boundary. Missing permissions render an honest
  unavailable surface; never present an enabled action that predictably lacks backend authority.

## Proposed interactions

| Task | Interaction / validation |
|---|---|
| Browse | Hierarchy, code, active/inactive status, policy status; search matches relevant ancestors/descendants and preserves context |
| Add Campus | PageAction; official name and stable code; explain later code changes need separate process |
| Add College | Add within selected Campus with explicit parent summary; active parent rechecked at submit |
| Add Program | Parent summary, stable code/name, classification, configured/pending policy; no automatic Bachelor or Years 1–4 defaults |
| Rename | Name editor with stable code/parent shown read-only; save expected resource version; explain linked current labels may change |
| Edit policy | Explicit classification and configured/pending choice; checkbox/list of permitted levels 1–10; noncontiguous set displayed accurately |
| Deactivate | Fresh impact review of actual blockers, warnings and preserved history; confirm target, consequences and expected version |
| Reactivate | Validate active parent chain and Program policy/basis; do not reactivate descendants automatically |
| History | Bounded target-specific safe catalog changes for authorized managers; no full Audit Trail or student contents |

Search/filter scale is driven by real list size, not a fabricated cap. The existing list API supports
status/search/parent filtering but no pagination. ORG-2 should add bounded pagination only if justified
by anticipated scale and compatibility; ORG-3 cannot invent it. Filtered lists must not pretend missing
parents/children were deleted. The current three-query view can briefly combine different refresh
moments; refetch affected ancestry after success, show refresh failure, and rely on mutation-side
versions/validation, not client hierarchy coherence.

## Feedback and recovery contract

| State | Proposed user behavior |
|---|---|
| Duplicate code | Field-level code error including correct parent context, retain other inputs |
| Parent inactive/unavailable | Plain explanation and return to parent selection; no silent activation/reparenting |
| Pending classification/levels | “Classification pending” / “Year Level policy pending”; recorded range is compatibility, not approved policy |
| Inactive historical record | Visible status; historical reference stays readable; excluded from ordinary new selection |
| Stale version / preview | “This record changed. Review the latest details before saving.” Reload comparison and require another deliberate confirmation |
| Blocked deactivation | Display blocker categories/counts and links only to already-authorized remediation workflows; do not offer one-click reassignment |
| MFA setup | Link to Account Security, preserve local draft if safe, then re-review/resubmit after return; no retained operation across setup |
| MFA verify | Recommend re-review of current impact/version before a new Catalog confirmation; if existing one-shot continuation is approved, backend must still reject stale versions/blockers |
| Mutation failure | Safe typed message, preserve draft, no success notification or automatic arbitrary replay |
| Refresh failed after success | State “Saved; latest details could not be loaded”, retry affected query; never imply save failed or silently resubmit |
| Permission revoked mid-edit | Backend 403, stop mutation, preserve appropriate local input for review without leaking restricted history |
| Unsaved edits | Local dirty-state cancel/leave confirmation only for this editor; keep browsing/back context |

Use nontechnical terms: official name, code, parent Campus/College, active/inactive, linked records,
change history. Do not show database fields, SQL errors, Python registry status or row-lock jargon.
Impact numbers must come from the authorized backend projection, not hardcoded estimates.

## Accessibility and responsive handoff

Use existing PageHeader/PageAction, Panel/PanelSection, form labels/descriptions/error summaries,
Notice/ActionStatus, ContextHelp, ConsequentialActionDialog, focus handling, and responsive table/list
patterns. Do not add a second component or state system. Keep hierarchy as nested lists/headings;
use a full ARIA tree only if implementing all its keyboard semantics. On mobile, stack parent facts
and edit controls, wrap long names/codes, keep target/actions visible and never replace identity with
unlabeled icon controls. No horizontal page spill or nested scroll traps.

Dialogs need clear title/description, label associations, initial focus, focus return, Escape/cancel,
keyboard reachability and announced error/status. Deactivation confirmation names the target and
states preserved records/remediation clearly. Help contains policy explanation; inline hints address
the immediate field. Noncontiguous levels must list actual values, not imply a continuous range.
Validate at narrow mobile width, keyboard-only, screen reader and 200% text/zoom, plus stale refresh
and permission/MFA transitions. No screen has been built or browser-reviewed in ORG-0.
Sources: [fe/AGENTS.md:485](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/AGENTS.md#L485); [fe/AGENTS.md:2198](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/AGENTS.md#L2198);
[fe/src/components/ui/consequential-action-dialog.tsx:1](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/components/ui/consequential-action-dialog.tsx#L1).

Student affiliations remains functional and unchanged in this proposal. No removal, migration,
student-placement redesign or compulsory SAR dependency is authorized.
