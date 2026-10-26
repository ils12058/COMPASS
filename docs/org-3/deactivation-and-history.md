# Deactivation, activation and change history

Every deactivation intent immediately loads its generated entity impact operation. Review reloads
both the record and impact, checks matching resource versions and refuses review while fetching,
failed, or blocked. Impact is advisory; the status operation sends only desired state/basis/version,
and the server recounts dependencies transactionally. A new dependency after review still yields
an effective refusal and fresh impact, without another mutation.

`catalog-impact.tsx` translates the actual typed blocker/warning codes. It displays observed time,
version, can_deactivate, separate blocker/warning lists, actual counts and preserved categories.
Expanded dependent counts use the fixed generated response fields; zero is a real returned value,
never an estimate. No dependent names, student identifiers, answers or confidential content is read.

Active children, active Student affiliations, Counselor responsibilities, open Office work and
pending operational Follow-Ups retain ORG-2's actual blockers. Draft Inventories, pending Good Moral
and inactive-account affiliations retain warning semantics. Program has no fabricated affiliation
or responsibility relationship. Preserved categories are the returned submitted Inventory facts,
issued certificate snapshots, Tracer references, resolved threads and inactive affiliations.

Blocked deactivation has a disabled Review action and a refresh control. Permitted deactivation
opens ConsequentialActionDialog with the target/name/code/parent, reviewed version/time, warnings,
preserved references and consequences. No descendants or assignments change automatically. Scope
changes can affect resolved-work visibility even though historical facts remain saved. Actual
status mutation failure returns to the preserved editor for review.

Only relationship managers receive remediation links to Responsibilities/Student affiliations.
Catalog-only authority adds no relationship or confidential-record access. Activation explains
active ancestry, complete Program policy and no automatic descendant/assignment restoration; the
canonical status operation keeps incomplete-policy and inactive-parent conflicts effective.

`catalog-history.tsx` uses the target-specific generated history operations, items/page/page_size/
has_next, with ten items per requested page. It retains the selected target while paging. No total
is fabricated. Each record displays the provided action/time, actor UUID, version transition,
bounded basis and catalog-safe before/after values. Actor names are not inferred or looked up in
Accounts; no global Audit API is queried. Older unversioned initialization events are not invented.

History is a separate accessible dialog with its own loading/error/empty states and Retry. A failed
history refresh does not display protected stale results as current. Closing restores the actual
history button. Backend authorization is still required on every impact/history request.
