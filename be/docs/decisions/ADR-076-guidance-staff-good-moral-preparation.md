# ADR-076: Guidance staff Good Moral preparation

## Status

Accepted. Refines ADR-033's operational authority and pre-issuance workflow.
Its Student eligibility, immutable source provenance, certificate snapshots,
controlled-form resolution, and issued-PDF rules remain authoritative.

## Context

Guidance Services Staff already coordinate Appointments, Referrals, and Call Slips.
They are an administrative GCO role, not a Counselor or provider. Good Moral's
Counselor-only queue/correction guards prevented safe clerical delegation, even if
an access administrator granted a capability. Preparation and professional issuance
therefore need separate authority and an explicit handoff.

Call Slips resolve StaffSupervision to retain a supervising Counselor's issuer
accountability. Good Moral does not copy that rule: the actual GSS or Counselor is
the preparer, and the actual Counselor performing final issuance remains issued_by.

## Decision

### Narrow authority

GSS receives academic_years.view, institutional_forms.view, good_moral.view, and
good_moral.prepare. Counselors receive prepare alongside existing view, manage, and
issue. The new prepare capability depends on view. Existing manage remains a
Counselor-only authority for identity/graduation-fact correction and cancellation.

View and preparation require an active COUNSELOR or GUIDANCE_SERVICES_STAFF account
and the effective capability. Issuance additionally requires the COUNSELOR primary
role and effective good_moral.issue. A GSS issue override cannot qualify the actor.
IT Admin receives no Good Moral operational baseline or professional qualification.

No GSS grant is added for Inventory answers/reopen, counseling, Routine Interview,
shared summaries, Student Support, E-Counseling, Exit Interview answers/reopen,
Graduate Tracer, Feedback/CSM, broad Reports, or reference configuration management.
Account/capability governance remains in the existing IT Admin management services
and API, including role qualification, step-up, audit, and expiry semantics. This
slice adds no Counselor, Head, or GSS override controls.

### First-class preparation

The workflow is REQUESTED -> READY_FOR_ISSUANCE -> ISSUED. Both GSS and Counselors
may mark a REQUESTED record ready after server validation of the existing printable
certificate completeness rules. Receipts remain optional. Readiness does not bind
the QMS FormRevision or refresh canonical source records; final issuance still
resolves and freezes the active supported revision and presentation template.

Preparation stores prepared_by and prepared_at. Existing REQUESTED, ISSUED, and
CANCELLED rows are not rewritten or assigned invented preparers. Database constraints
require preparation provenance for READY and continue to enforce issuance,
cancellation, and variant provenance shapes. Historical issued rows with no digital
preparation remain valid.

Clerical correction can change year level, semester, certificate-local course,
major, and optional receipt number/date/amount, where applicable to the saved variant.
Applicant name, College, degree, and graduation date remain Counselor-only corrections
requiring prepare plus the retained manage authority. Student ownership, variant,
Inventory, Academic Year, account/profile, and institutional records remain immutable
through every Good Moral correction route.

A material correction to READY returns it to REQUESTED and clears the current
preparation marker. An identical correction is a no-op. Audit retains every prepare
and return transition, so re-preparation does not imply the latest marker is a full
history. REQUESTED and READY can be cancelled through the existing Student-owner or
Counselor cancellation authority. GSS is not granted cancellation. Issued and
cancelled records remain terminal; issued certificate facts remain immutable.

Preparation, correction, cancellation, and issuance lock the request row. Browser
preparation supplies the exact server-owned request version reviewed; issuance
supplies the preparation version reviewed. Version strings preserve database
timestamp precision independently of human-readable JSON dates. Stale reviews return
good_moral_preparation_changed; a record that is not ready returns good_moral_not_ready.
No action is replayed automatically after a refresh. Issuance remains idempotent once
ISSUED, rechecks F4 CURRENT lifecycle and certificate completeness, and records the
actual issuing Counselor. It adds no authenticator step-up to routine issuance.

### APIs, interface, and PDF access

The existing operational queue/detail/correction endpoints admit qualified GSS.
POST /good-moral/requests/{id}/prepare is the explicit readiness action. Issue now
requires an expected_preparation_version; prepare requires an expected_resource_version.
Operational detail returns server-owned correction, preparation, issuance,
cancellation, and download action state and the permitted correction-field list.

The queue retains search, variant, status, pagination, and represented FormRevision
filters, adds Academic Year filtering/projection, and distinguishes Needs preparation
from Ready for issuance. Detail shows certificate-local facts, receipts, current
preparation provenance, and only authorized actions. GSS never sees an Issue action;
Counselors can prepare personally or review a GSS preparation. Effective view-only
access remains useful after a prepare revoke.

Only issued certificates have a final PDF. Qualified GSS with view may retrieve/print
that administrative artifact through the existing audited, fail-closed release path.
It retains the actual Counselor's saved issuer name and never changes issuance
provenance. No new draft preview or counseling/Inventory document access is added.

Overview uses its existing compact workload/At a glance patterns. Its Guidance
projection adds an exact ready count, and GSS receives the exact preparation queue
count behind view. These link to the appropriate Good Moral status filters. GSS's
Routine Interview count stays null and no confidential work query is enabled.
Student pending-request counts include REQUESTED and READY. No reporting authority
or dashboard framework is introduced.

### Exit Interview integration dependency

The separate Exit Interview opportunity slice is not on staging at this slice's
base, 2ed4a9aad6cf23a311b53ab031e556157c0ba9dd. It is being developed in a separate
worktree. This slice deliberately adds no competing opportunity model, endpoint,
or placeholder capability. GSS continues to be denied response detail and reopen.

After that domain lands, integration must reuse its bounded opportunity-management
authority and expose only Student/year/source/opportunity status, workflow status,
and opening/submission times. It must not grant response view/reopen or PDF access.
The two independent Good Moral migration leaves will also need an integration merge
migration when both branches are brought together. Neither slice is automatically
merged or deployed by this work.

### Audit and compatibility

good_moral.prepared and good_moral.returned_to_preparation record actual actors,
variant, and transition. Existing request_created, request_updated, issued, cancelled,
and document release actions remain. Notes, certificate text, receipt values, PDF
bytes, and sensitive source content are not duplicated into transition metadata.
Preparation adds no new email/notification. Existing issuance behavior remains.
Demo issuance explicitly performs preparation using its actual Counselor and saved
business timeline rather than bypassing the new readiness boundary.

## Validation

Focused tests cover GSS reference and clerical grants, denied confidential domains,
view/prepare/issue role qualification, overrides/revokes/expiry/dependencies, safe
fields, immutable provenance, completeness, stale reviews, correction invalidation,
actual preparation/issuance actors, terminal history, cancellation, and audited issued
PDF access. Existing Good Moral tests now explicitly prepare before issuance.
OpenAPI/client generation and frontend access, queue, detail, correction, readiness,
lint, strict types, and production build are checked without weakening repository rules.
