# Integrated source manifest

All paths are repository-relative. The merged source at the exact README candidate SHA is the
runtime authority; historical design documents are contextual. In particular ORG-0's proposed
GRADUATING/ALUMNI wording is superseded by actual CURRENT/GRADUATED/FORMER storage, and its proposed
pending-F4 acknowledgment is superseded by ORG-2's fail-closed policy-change refusal.

| Slice | PR | Integration commit |
|---|---|---|
| ORG-0 authority/dependency audit | [#326](https://github.com/ils12058/COMPASS/pull/326) | `e7db50e0b23dd21a7ff7ec44c9d08708eb24ee12` |
| ORG-1 database authority/policy | [#327](https://github.com/ils12058/COMPASS/pull/327) | `077d98a29855f9822599c938d81cb6b5d7102684` |
| ORG-2 protected services/API/integrity | [#328](https://github.com/ils12058/COMPASS/pull/328) | `f9e6fb4a99ed3bdc72f7b594752a141d6ac48edd` |
| ORG-3 management UI | [#329](https://github.com/ils12058/COMPASS/pull/329) | `d91d64c2893ac834c6b70c1e00f4a823e11478f7` |

## Migrations, authority and services

| Owner | Exact implementation files / responsibility |
|---|---|
| Organization schema | `be/compass/organization/models.py`; `migrations/0001_canonical_baseline.py`, `0002_program_policy_and_catalog_initialization.py`, `0003_catalog_resource_versions.py` in that domain |
| Organization initialization | `be/compass/organization/bootstrap.py`; `management/commands/initialize_organization_catalog.py`, `management/commands/sync_organization_catalog.py`; `canonical.py` is frozen seed input only |
| Organization academic policy | `be/compass/organization/program_policy.py`, `selection.py`; database array function is owned by migration 0002 |
| Protected Catalog administration | `be/compass/organization/catalog_services.py`, `api.py`, `integrity.py`; no generic PATCH, move or delete |
| Relationship/routing ownership | `be/compass/organization/services.py`, `access_scope.py`; StudentAffiliation, CounselorResponsibility, StaffSupervision remain separate |
| Capability definitions/evaluation | `be/compass/accounts/policy.py`, `services.py`, `bootstrap.py`; `be/compass/account_management/services.py`, `csv_import.py` |
| Authentication/MFA | `be/compass/authentication/api.py`, `services.py`, `sessions.py`, `mfa.py`, `step_up.py`, `crypto.py`; persisted AuthSession and active TOTPFactor |
| Audit | `be/compass/audit/actions.py`, `context.py`, `services.py`, `models.py`; restricted projection is in Organization `catalog_services.py` |
| Migration/deployment safety | `be/compass/common/canonical_migrations.json`, `canonical_baseline.py`; `be/deploy/staging/database_preflight.py`, `deploy.sh`; `.github/scripts/run_staging_deploy.py` |

`organization.catalog.manage` depends on `organization.structure.view`. Eligible active staff roles
are IT_ADMIN, COUNSELOR and GUIDANCE_SERVICES_STAFF, but none receives Catalog manage by role or
designation baseline. `organization.manage` continues to own relationship administration.

Catalog gate: `477580715032`, exclusive for Catalog mutations and shared for participating dependent
writes. Initialization uses its distinct `477580715031`. Positive versions start at 1. Changes and
Audit commit atomically. Events are `organization.{campus|college|program}.{created|updated|enabled|disabled}`
and `organization.program.policy_changed`. History projects only marked, committed, exact-target
Catalog evidence; initialization does not fabricate versioned individual changes.

## All sixteen authenticated operations

Routes are under `/api/v1/organization`. Each row was observed succeeding against real Django;
mutation database observations and exact actor/version transitions were checked by the external
test oracle. History pagination additionally used actual authenticated same-origin requests.

| # | Method/path | Canonical operation ID | Service |
|---|---|---|---|
| 1 | POST /campuses | organizationCreateCampus | create_campus |
| 2 | PUT /campuses/{id}/name | organizationRenameCampus | rename_campus |
| 3 | PUT /campuses/{id}/active | organizationSetCampusActive | set_campus_active |
| 4 | GET /campuses/{id}/impact | organizationGetCampusImpact | get_catalog_impact |
| 5 | GET /campuses/{id}/history | organizationGetCampusHistory | get_catalog_history |
| 6 | POST /colleges | organizationCreateCollege | create_college |
| 7 | PUT /colleges/{id}/name | organizationRenameCollege | rename_college |
| 8 | PUT /colleges/{id}/active | organizationSetCollegeActive | set_college_active |
| 9 | GET /colleges/{id}/impact | organizationGetCollegeImpact | get_catalog_impact |
| 10 | GET /colleges/{id}/history | organizationGetCollegeHistory | get_catalog_history |
| 11 | POST /programs | organizationCreateProgram | create_program |
| 12 | PUT /programs/{id}/name | organizationRenameProgram | rename_program |
| 13 | PUT /programs/{id}/active | organizationSetProgramActive | set_program_active |
| 14 | GET /programs/{id}/impact | organizationGetProgramImpact | get_catalog_impact |
| 15 | GET /programs/{id}/history | organizationGetProgramHistory | get_catalog_history |
| 16 | PUT /programs/{id}/policy | organizationUpdateProgramPolicy | update_program_policy |

## UI, writers and consumers

UI owner: `fe/src/features/organization/structure/organization-structure-page.tsx` and
`structure/catalog/{catalog-actions,catalog-editor,catalog-history,catalog-impact,catalog-model,catalog-policy-fields,catalog-query,catalog-review,catalog-errors}`
with their actual `.tsx` or `.ts` extensions. Entry/navigation: Organization `components/organization-gate.tsx`,
`organization-navigation.tsx`, `fe/src/features/institution-configuration/institution-access.ts` (entry helpers);
MFA: `fe/src/features/account/security/security-shared.tsx`. Generated operations come from
`contracts/openapi.json` via `fe/orval.config.ts`, never handwritten transport or DTOs.

Participating production writers were source-reviewed in Organization services, Accounts overrides
and identity sync, Account Management/CSV entry, Inventory ensure/replace/submit, Good Moral F4 and
assisted/correction entry, appointment creation, Office open/status, Follow-Up lifecycle/reassignment,
and dataset-seed outer entry. The shared gate precedes their existing domain/user locks. This is a
finite inventory of supported current-runtime paths, not a fence against arbitrary ORM/SQL or old code.

Historical consumers: `be/compass/inventory/{services,api,documents}.py`,
`good_moral/{services,api}.py`, `graduate_tracer/{services,api}.py`, `reports/{services,graduate_tracer,graduate_tracer_xlsx}.py`,
`exit_interviews/`, `routine_interviews/`, `guidance_messages/`, `guidance_followups/`,
`appointments/`, `counseling/` and `operational_students.py` beneath `be/compass/`.
Student placement and provider-owned confidentiality stay in their owning domains.

New assurance sources: `be/tests/test_catalog_final_integration.py`,
`be/tests/catalog_authenticated_rehearsal.py`, `fe/tests/organization-catalog.authenticated.mjs`.
The pytest module is registered in `.github/scripts/backend_ci.py`. The real browser rehearsal is
explicitly opt-in and separate from the auto-discovered mocked `*.browser.mjs` suites.
