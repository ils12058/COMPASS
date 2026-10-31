# FAC-0 verified architecture and ownership

Inspected integration `478166b7` on 2026-10-31 after fetching origin. The checkout
matched origin. Work branch: `codex/fac-1-faculty-identity`; PR target:
`integration/ux15-modernization`. No deployment or merge is authorized.

## Verified baseline

No Faculty primary role, affiliation, Faculty API or Faculty submission service
exists. “FACULTY” in Exit Interview feedback is a survey category, not identity.
Accounts have one protected Role FK. `accounts/policy.py` owns canonical codes,
grants, dependencies and role/designation compatibility; `bootstrap.py` syncs them
idempotently. Unknown database grants are retained by sync, and generic overrides
can add capabilities. Consequently an empty baseline alone is insufficient to
guarantee a Faculty boundary: FAC-1 needs an explicit capability ceiling too.

Head Guidance is a COUNSELOR designation; DPO requires INSTITUTIONAL_OFFICER.
Account Management checks capabilities, recent MFA for authority changes, a shared
manager mutex, locked current actors/targets, last-manager preservation, CSRF,
and authentication invalidation. Existing role changes reject stranded Student,
Counselor, Supervision, Availability and Appointment relationships. These are the
verified access-control principles relevant to Proposal #13: distinct primary
identity, compatible designation, explicit action authority, separate resource
scope, default denial and audited institutional provisioning. The complete text
of Proposal #13 is not in this checkout; no additional policy is inferred.

ORG-1–4 established database-owned UUID references, active parent validation,
resource versions, impact blockers and a cooperative catalog gate taken before
user locks. StudentAffiliation remains the current Student routing relationship.
Catalog initialization is explicit, not a recurring seed reconciliation. FAC-1
must add Faculty references to impact/reactivation protection without changing
StudentAffiliation or catalog initialization.

Referral already owns encrypted reasons/referrer names, annual reference counters,
actor-scoped creation digests and fingerprints, protected revision references,
and GCO operational actions. `recorded_by` is GCO recorder provenance, not an
authenticated Faculty submitter. Revision `UCN-OP-GCO-01F3`, revision 1, is already
canonical (ADR-113). Creation requires a Counselor/GSS actor and Student placement
within the actor's GCO scope. Reusing that permission for Faculty would be wrong.
Follow-Ups and CONT coverage/handoffs have separate scope and fail-closed policy;
Faculty receives none. NOTIF maintains server policy, generic security events
and disclosure minimization; Faculty creation must not create Referral notices.

UX15 Home composes Student, Counselor, GSS and a generic fallback. Workspaces and
their guards read capabilities and domain actor checks. Faculty needs an explicit
holding Home so the generic operational presentation never implies availability.
Opaque sessions, MFA, CSRF, account-cache ownership and sign-in remain unchanged.

## Dependencies and file ownership before implementation

| Owner | Planned changes and boundary |
| --- | --- |
| `be/compass/accounts/{policy,services}.py` | Faculty code, empty baseline, ceiling and override eligibility; existing roles' grants unchanged |
| `be/compass/organization/models.py`, additive migration | Faculty-only current home College reference/version and institutional provenance; no Student model migration |
| `organization/{api,catalog_services,services}.py` | Faculty impact blockers, strict impact DTOs and retained-reference reactivation validation under existing gate |
| `be/compass/account_management/{faculty,services,api,csv_import}.py` | Controlled assignment, creation/import, exact identity conflicts, versioned changes; no academic writer |
| `be/compass/audit/actions.py` | Affiliation change event with UUIDs/version, no Student or Referral content |
| `be/compass/authentication/api.py` | Read-only self affiliation projection using existing authenticated summary |
| `contracts/openapi.json` | Generated canonical API changes, then Orval regeneration (generated frontend ignored) |
| `fe/src/features/accounts/` | Faculty provisioning, affiliation review/change, CSV schema presentation |
| `fe/src/features/portal/` | Explicit Faculty holding Home; existing guards retain capability-based denial |
| `fe/src/features/organization/structure/catalog/catalog-impact.tsx` | Explain Faculty retirement blockers using the canonical impact contract |
| `be/tests/`, `fe/tests/` | Identity, authorization, catalog, import, migration and routing regressions |
| `docs/fac-1/` | FAC-2 contract, policy register and observed validation/limitations |

No changes planned to Referral, protected clinical domains, Student placement
writers, notifications, staging/main or deployment workflows.

Validation exposed two baseline formatting failures in `test_fixed_date_slots.py`
and `test_service_catalog.py`; changes there normalize formatting only. Existing
Student Home node tests also could not resolve its build-time `next/font/google`
import. A bounded test-only Caveat fixture lets those actual Home regression tests
run; production font rendering continues to be checked in the built browser app.
