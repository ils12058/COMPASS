# ADR-099: Operational responsibility and domain-owned Head oversight

## Status

Accepted, 2026-10-09. Refines the responsibility and supervision wording in ADR-017,
ADR-027, ADR-028, ADR-050, ADR-054 and ADR-055. Also clarifies the Student Support
boundary in ADR-048 and the shared operational Student picker in ADR-075/ADR-076.
Historical wording is retained with explicit refinement links; other decisions remain authoritative.

## Context

The shared organizational access resolver gave Head Guidance institution-wide scope and
recursively returned that same scope to supervised GSS. The default-responsibility projection
also treated every active College as Head workload, although Student routing already preferred
an active responsible Counselor before unique-Head fallback. ADR-028 allowed institution-wide
GSS inheritance while ADR-050 rejected it and described explicit responsibilities only.

## Decision

Guidance Services Staff inherit the operational responsibility of their supervising Counselor,
not the supervisor's designation authority.

`resolve_operational_responsibility_scope(actor)` returns only finite handled College IDs:

- Ordinary active COUNSELOR: explicit CounselorResponsibility Colleges.
- Active Head Guidance COUNSELOR: explicit Colleges plus Colleges with no valid active
  COUNSELOR responsibility when this actor is the unique active Head.
- Active GSS: current active COUNSELOR supervisor's handled Colleges, through StaffSupervision.
- Inactive actors, invalid/missing supervision and unsupported roles: empty scope.

Every included College and Campus must be active. Multiple active Heads receive no implicit
fallback Colleges; explicit assignments remain usable. An inactive or non-Counselor assignee
is unavailable for routing and therefore does not block a valid unique-Head fallback.
Fallback remains a query over current state, without persisted assignment rows or Student iteration.
The handled query and Student routing share the valid-Head candidate query.

`effective_responsibility_colleges` is a College projection of that same workload. The ambiguous
`resolve_organizational_access_scope` and its institution-wide scope type are removed. The workload
primitive cannot represent designation-wide authority. `is_head_guidance` checks only the actual
actor's active Counselor identity/designation and never follows supervision.

Domains explicitly decide oversight after their existing capability/role guards:

| Domain | Head oversight | Ordinary Counselor | GSS under Head |
| --- | --- | --- | --- |
| Non-Counseling Appointments | Institution-wide | Handled Colleges; existing provider relationship | Head handled Colleges |
| Counseling Appointments | Current provider only | Current provider only | No inherited provider access |
| Referrals | Institution-wide | Handled Colleges | Head handled Colleges |
| Call Slips | Institution-wide | Handled Colleges | Head handled Colleges; current supervisor is issuer |
| Inventory review/reopen | Institution-wide | Handled Colleges | No supported Counselor qualification |
| Student Support Context | Institution-wide | Handled Colleges | No supported Counselor qualification |
| Aggregate Reports | Global | Handled Colleges | Unsupported report role |
| Counseling / E-Counseling / Shared Summary / Routine | Existing relationship policy | Existing relationship policy | No inherited relationship |
| Good Moral | Existing office-wide policy | Existing policy | Existing view/preparation policy |
| Exit Interview Student picker | Explicit institution-wide selection | Existing capability plus handled scope | Head handled Colleges |

The shared Student picker accepts College IDs (or an explicit domain-selected institution-wide
`None`) rather than deciding actor authority. Referrals, Call Slips and Exit Interview selection
supply that scope. Exit Interview opportunity operations remain governed by ADR-075/076; this
correction does not add College scope to their existing scope-free operations or to Good Moral.

No capabilities, designations, provider/case relationships, MFA state, or resource exceptions are
inherited through supervision. Existing capability revokes, role eligibility, concealed not-found,
Counseling confidentiality, authority-change session invalidation, and lock scopes are preserved.

The Organization person projection now uses `ASSIGNED_AND_FALLBACK_COLLEGES` for a Head instead
of `INSTITUTION_WIDE`; it describes a workload resolution mode, not a list or access grant.
Ordinary Counselors retain `ASSIGNED_COLLEGES`. The OpenAPI enum and client labels follow this
correction. No route, operation ID, database migration, new role, workflow or capability is added.

Future Guidance Messages may consume handled scope for office staff visibility, but Head oversight
must be an explicit Messages-domain decision and contextual Counseling visibility must use its
relationship policy. This ADR implements neither Messages nor Realtime.
