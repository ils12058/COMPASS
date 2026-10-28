# Current-state audit

All facts in this document are **VERIFIED CODE FACT** at the [reviewed SHA](README.md), unless marked
otherwise. Test coverage is separately identified in [validation](validation.md).

## Models and ownership

| Model | Actual representation and constraints | Consequence |
|---|---|---|
| Campus | UUID PK; code 32 globally unique; name 160; active boolean; timestamps | Stable identity exists; no hierarchy-status constraint |
| College | UUID PK; PROTECT Campus; `(campus, code)` unique; name/status/timestamps | Duplicate code under different Campuses is legal |
| Program | UUID PK; PROTECT College; `(college, code)` unique; name/status/timestamps | No classification, policy status or levels column |
| StudentAffiliation | Student OneToOne PK, PROTECT Student and College, nullable SET_NULL assigned_by | One current Guidance College; no Program or academic-period history |
| CounselorResponsibility | College OneToOne PK; PROTECT College and Counselor; assignment provenance | One assigned Counselor per College, many Colleges per Counselor |
| StaffSupervision | Staff OneToOne PK; PROTECT Staff and Supervisor; assignment provenance | No catalog FK; scope derives through supervisor |
| AcademicYear | UUID; unique label; conditional uniqueness of current=true | Separate domain configuration; not catalog CRUD |

Sources: [be/compass/organization/models.py:11](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L11);
[be/compass/organization/models.py:15](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L15);
[be/compass/organization/models.py:41](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L41);
[be/compass/organization/models.py:117](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L117).

`normalize_code` is exactly `value.strip().upper()`. It does not collapse interior whitespace,
slugify, strip punctuation/accents or apply an external identifier mapping. `save()` normalizes code
and strips name; bulk updates/raw SQL bypass those hooks. Database uniqueness is on stored values,
not an additional normalized-code expression. There is no automatic `full_clean()` or cross-table
active-parent enforcement in these models. Future services must validate before saving; constraints
remain the race-safe uniqueness boundary. No deletion workflow or Django Admin catalog editor was
found in this domain.

Current registry validates exactly 6/10/38 at import and pins Bachelor's to `(1,2,3,4)`; Master's and
Doctoral levels are `None`. The numbers validate this installation dataset, not the University's
future offerings. Majors remain separate descriptive information. BSED under COED and ENTIENZA
are separate Program identities. ENTIENZA's College row is an explicit academic/routing projection,
not proof of its official organizational type. These distinctions are documented in ADR-064.
Sources: [be/compass/organization/canonical.py:55](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L55);
[be/compass/organization/canonical.py:225](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/canonical.py#L225);
[be/docs/decisions/ADR-064-canonical-organization-catalog.md:105](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/docs/decisions/ADR-064-canonical-organization-catalog.md#L105).

## Services and synchronization

`organization/services.py` exposes list/get catalog reads and transactional operational relationship
writes, not catalog creation/rename/status services. Lists return tuples, ordered by codes, with
optional search/status/parent filters; search trims and bounds terms at 160 characters. Catalog
`is_active=True` filters the row's status only, not its parents. Detail reads retain inactive rows.
This is safe for reference browsing but insufficient as the sole new-selection eligibility check.

Relationship setters validate active users/roles and lock College/Campus for affiliation and
responsibility assignment. Relationship removal remains possible for inactive users. Role changes
are refused until conflicting affiliation/responsibility/supervision relationships are explicitly
removed or reassigned. No-op assignments do not emit misleading mutation events.
Sources: [be/compass/organization/services.py:163](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L163);
[be/compass/organization/services.py:203](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L203);
[be/compass/organization/services.py:254](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L254);
[be/compass/organization/services.py:135](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L135);
[be/compass/organization/services.py:268](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L268).

Canonical bootstrap is a separate system writer; see the complete [invocation inventory](canonical-authority-and-bootstrap.md).
It identifies by codes/parents, repairs name/active values, retains UUIDs and historical FKs, retires
unknown Programs, and can roll back the whole transaction when an unknown College has relationships.
Even inactive students' affiliation rows count in that current blocker; the query does not filter
student activity or lifecycle. Ordinary starts do not run this writer.

## Existing HTTP and generated contract

All following routes are under `/api/v1/organization` and session authentication:

| Surface | Operations | Authorization/behavior |
|---|---|---|
| Campus | `organizationListCampuses`, `organizationGetCampus` (GET) | `organization.structure.view`; list status/search |
| College | `organizationListColleges`, `organizationGetCollege` (GET) | Same; optional `campus_id` |
| Program | `organizationListPrograms`, `organizationGetProgram` (GET) | Same; optional `college_id` |
| Counselor responsibilities | list; PUT/DELETE `/colleges/{college_id}/counselor` | `organization.manage`; writes recent MFA |
| Staff supervision | list; PUT/DELETE `/staff/{staff_id}/supervisor` | Same |
| Student affiliation | paginated/searchable/filterable list; PUT/DELETE `/students/{student_id}/affiliation` | Same |
| People | eligible active-role discovery | `organization.manage`, bounded pagination |

Source: [be/compass/organization/api.py:263](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L263);
[be/compass/organization/api.py:390](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L390);
[be/compass/organization/api.py:444](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L444);
[be/compass/organization/api.py:516](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L516);
[be/compass/organization/api.py:550](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L550).

The old twelve structural write operation IDs are removed; tests require absent routes, not 403
placeholders. Errors use 404 `organization_not_found`, 409 `organization_conflict`, 422
`invalid_organization_request`; service errors are mapped by the API. ProgramSummary exposes UUID,
code, name, nested College/Campus, active flag, nullable classification, non-null status and nullable
integer levels. Metadata comes from the Python identity lookup; absent lookup means classification
null, status `PENDING_POLICY`, levels null.
Sources: [be/compass/organization/api.py:76](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L76);
[be/compass/organization/api.py:207](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L207);
[be/tests/test_organization.py:502](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_organization.py#L502).

`contracts/openapi.json` is the backend-owned wire contract. The frontend imports generated
Organization hooks/models from `fe/src/lib/api/generated/`, which is generated locally and ignored,
not a second handwritten contract. ORG-0 changes neither source nor contract; ORG-1 should retain the
metadata response shape. ORG-2 regenerates OpenAPI and Orval for actual new endpoints and capability
values. Sources: [fe/AGENTS.md:129](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/AGENTS.md#L129);
[fe/orval.config.ts:1](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/orval.config.ts#L1).

## Authorization and workspace

`organization.structure.view` is a safe reference-read capability granted across the ordinary roles.
`organization.manage` is operational configuration, granted to IT Admin and the Head designation.
Account overrides are resolved with revokes and prerequisite suppression; a designation is not a
primary role, and GSS supervision never inherits its supervisor's capabilities or Head designation.
Sources: [be/compass/accounts/policy.py:578](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/policy.py#L578);
[be/compass/accounts/policy.py:699](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/policy.py#L699);
[be/compass/accounts/policy.py:784](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/policy.py#L784);
[be/compass/organization/access_scope.py:70](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/access_scope.py#L70).

The frontend's **outer OrganizationGate requires `organization.manage`**, even though its inner
Structure gate checks `organization.structure.view`. Therefore a Student/Counselor reference-read
capability does not by itself open the standalone workspace. Tabs are Structure, Responsibilities
(including staff supervision), and Student affiliations. Structure loads three lists without filters,
renders Campus panels with College rows and indented Programs, status labels and policy summaries,
and has shared loading/error/retry handling. It has no catalog mutation controls, search or filters.
Its first-to-last Year Level summary assumes a contiguous set; future noncontiguous levels need
explicit labels. Details and proposed access changes are in [UX](ux-and-workspace-design.md).
Sources: [fe/src/features/organization/components/organization-gate.tsx:14](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/components/organization-gate.tsx#L14);
[fe/src/features/organization/components/organization-navigation.tsx:26](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/components/organization-navigation.tsx#L26);
[fe/src/features/organization/structure/organization-structure-page.tsx:24](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/fe/src/features/organization/structure/organization-structure-page.tsx#L24).

## Migration graph and architectural precedent

Organization has only `0001_canonical_baseline.py` (schema only). `0002` is the next available
Organization migration identifier at the inspected revision; recheck on ORG-1 branch creation.
Canonical baselines are immutable and hash-registered; later additive migrations are explicitly
registered in `common/canonical_migrations.json`. Tests verify graph leaves, model drift and actual
PostgreSQL constraints. Pre-canonical database histories are rejected; ORG-1 is an ordinary additive
upgrade for databases already on this lineage, never another reset/rebaseline.
Sources: [be/compass/organization/migrations/0001_canonical_baseline.py:9](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/migrations/0001_canonical_baseline.py#L9);
[be/compass/common/canonical_migrations.json:21](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/common/canonical_migrations.json#L21);
[be/compass/common/canonical_baseline.py:29](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/common/canonical_baseline.py#L29);
[be/tests/test_canonical_baseline.py:41](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/tests/test_canonical_baseline.py#L41).

ADR-017 defines operational relationships; ADR-064 intentionally removed catalog CRUD and asserts
code ownership; ADR-099 separates handled workload and general Head oversight. ORG-1 needs a new
accepted replacement/refinement of ADR-064 before runtime ownership changes. This audit proposes
that replacement, and does not silently rewrite historical ADR status.
