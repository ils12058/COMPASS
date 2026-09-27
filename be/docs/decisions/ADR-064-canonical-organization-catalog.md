# ADR-064: Code-owned UCN organization catalog with synchronized DB projection

- Status: Accepted
- Date: 2026-09-27
- Scope: Campus, College/top-level academic unit, and Program ownership

## Context

ADR-017 introduced the relational Organization model and operational routing relationships. At that
time Campus, College, and later Program were ordinary runtime-managed configuration. That contract
allowed Guidance/administrative users to create or rename institutional topology even though those
values describe University structure rather than Guidance Office policy.

This is the same ownership mismatch corrected for Institutional Forms by ADR-063, but Organization
has different historical and operational constraints. Campus, College, and Program are consumed by
Inventory, reports, access-scope/routing logic, and saved foreign keys. At the same time,
StudentAffiliation, CounselorResponsibility, and StaffSupervision are genuine GCO operational
relationships and must remain editable at runtime.

The current COMPASS schema is intentionally explicit:

```text
Campus
  -> College / top-level academic offering unit
       -> Program
```

It is not a generic University hierarchy or SIS schema.

## Source basis

The initial canonical projection was verified on 2026-09-27 against current official University of
Camarines Norte web material:

- UCN About page / campus descriptions:
  https://ucn.edu.ph/UCN/main-home-page-copy/about-ucn/
- UCN Admission / Courses Offered roster:
  https://ucn.edu.ph/UCN/main-home-page-copy/admission/
- UCN homepage Facts and Figures, which reports 38 total courses offered:
  https://ucn.edu.ph/UCN/
- UCN July 2025 announcement archive documenting the IFMS -> CFAST rename:
  https://ucn.edu.ph/UCN/2025/07/

The current Admission roster is preferred for active Program membership when older dedicated pages
retain stale offerings. For that reason BA History is not added. The base Program catalog contains
exactly 38 Programs, matching the current homepage total when published majors/specializations are
not incorrectly expanded into separate Program rows.

These sources are verification inputs for a source-controlled catalog. COMPASS does not scrape the
UCN website at runtime.

## Decision

### Campus, College, and Program are institutionally canonical

The running COMPASS version owns one immutable canonical registry for the current locally supported
projection:

- 6 Campuses;
- 10 College/top-level academic offering and routing units;
- 38 base Programs.

The registry uses stable COMPASS canonical codes. Those codes are not claimed to be SIAS, CAPS,
Registrar, or ITSO identifiers. Current identity is structural:

```text
Campus: code
College: canonical Campus code + College code
Program: canonical Campus/College identity + Program code
```

Display names are not identity and synchronization never merges rows by name alone.

### The current six Campus identities are

```text
MAIN        Main Campus
ABANO       Abaño Campus
MERCEDES    Mercedes Campus
LABO        Labo Campus
PANGANIBAN  Jose Panganiban Campus
ENTIENZA    Ret. Judge Antonio C. Entienza Campus
```

The published "Santa Elena Campus" location for Entienza is not a seventh Campus.

### The current ten top-level academic/routing units are

```text
MAIN / CAS        College of Arts and Sciences
MAIN / CBPA       College of Business and Public Administration
MAIN / COENG      College of Engineering
MAIN / GS         Graduate School
MAIN / CCMS       College of Computing and Multimedia Studies
ABANO / COED      College of Education
MERCEDES / CFAST  College of Fisheries, Aquatic Sciences, and Technology
LABO / CANR       College of Agriculture and Natural Resources
PANGANIBAN / COTT College of Trades and Technology
ENTIENZA / ENTIENZA Ret. Judge Antonio C. Entienza Campus
```

The CFAST identity supersedes former IFMS for the active canonical projection. Historical IFMS rows,
if present, are retained rather than rewritten or hard-deleted.

### Entienza is an explicit relational projection, not a fabricated College

UCN publishes Entienza as a campus-level academic offering unit. COMPASS currently requires
`Program -> College -> Campus`, and Student routing also references College. The least speculative
projection is therefore an ENTIENZA Campus with an ENTIENZA College-row projection carrying the
same published name. This does not assert that UCN institutionally calls Entienza a College and
does not invent a fake college name.

### Program is the base degree/program; Major remains separate

Individual Inventory already stores `program_id` and `major` separately. The 38-row canonical
Program catalog therefore represents base programs only. BSBA, BSEd, Agriculture, COTT, Graduate
School, and other majors/specializations remain descriptive major information and do not become
additional Program rows. No Major, Department, curriculum, section, subject, or enrollment model is
introduced.

Duplicate Program codes under different College parents remain valid. For example BSED exists under
COED and under the ENTIENZA projection.

### PostgreSQL remains the relational and historical projection

Campus, College, and Program models remain. Their UUIDs are stable relational identities used by
Guidance-domain consumers and historical records. Existing PROTECT relationships remain intact.

Deployments run:

```text
migrate
sync_identity_policy
sync_canonical_services
sync_institutional_forms
sync_organization_catalog
check
```

`sync_organization_catalog` is explicit, transactional, deterministic, and idempotent. It creates
missing canonical rows, repairs canonical names and active state, and preserves the UUID when an
exact canonical identity already exists. It does not run at import time, application startup,
request time, or from a portal button.

No schema/data migration is added solely to seed the catalog.

### Historical and noncanonical rows are retained safely

Synchronization never hard-deletes unknown Organization rows and never rewrites saved foreign keys
merely to make historical data look canonical.

A noncanonical Program is retained but made inactive so it cannot be selected for a new Inventory.
Existing `StudentInventory.program` references remain unchanged.

A noncanonical active College is more sensitive because StudentAffiliation and
CounselorResponsibility express current Guidance routing. If such a College still has live
operational relationships, synchronization fails clearly and rolls back rather than guessing an
equivalent canonical unit. Once no live relationship or active child Program remains, the
noncanonical College may be made inactive.

A noncanonical Campus is likewise made inactive only when no active child College remains.
Synchronization failure is preferred to corrupting organizational scope.

New reconciliation emits one bounded SYSTEM `organization.catalog_synced` AuditEvent only when
persisted state changes. Existing historical structure-mutation AuditEvents remain valid history.

### Structural runtime CRUD is removed

The public HTTP contract retains safe Campus, College, and Program reads under
`organization.structure.view`.

The following mutation operations are removed:

```text
organizationCreateCampus
organizationUpdateCampus
organizationEnableCampus
organizationDisableCampus
organizationCreateCollege
organizationUpdateCollege
organizationEnableCollege
organizationDisableCollege
organizationCreateProgram
organizationUpdateProgram
organizationEnableProgram
organizationDisableProgram
```

Their runtime service functions and portal Add/Edit/Enable/Disable controls are also removed.
Institutional topology is not replaced by Django Admin, a hidden editor, an HTTP sync endpoint, or
another generic topology editor.

### GCO operational Organization management remains runtime-managed

`organization.manage` is retained because it has real product meaning independent of institutional
topology. It continues to govern:

- Counselor responsibility assignment/removal;
- Guidance Services Staff supervision assignment/removal;
- Student affiliation assignment/removal;
- eligible-person discovery used by those workflows.

Existing recent-MFA, role-transition, Head fallback, capability override, and organizational-scope
semantics remain unchanged.

The Organization workspace therefore has two conceptual parts:

```text
Reference structure
  Campuses   read-only
  Colleges   read-only
  Programs   read-only

Operational relationships
  Counselor responsibilities   managed
  Staff supervision            managed
  Student affiliations         managed
```

### Future authoritative integration is a source replacement, not a second truth

Today:

```text
source-controlled COMPASS canonical catalog
  -> sync_organization_catalog
  -> Campus / College / Program DB projection
```

A future supported UCN system may instead provide an authoritative organization feed:

```text
CAPS / SIS / ITSO authoritative contract
  -> bounded organization synchronization adapter
  -> the same DB projection
```

The invariant is that Campus, College, and Program do not become independently user-managed local
institutional truth. It is not a requirement that their source remain Python forever.

No CAPS/SIAS/ITSO client, OAuth/OIDC integration, web scraper, webhook, scheduler, event bus,
generic integration framework, or speculative external identifier/source-system field is added by
this decision.

## Consequences

- The portal can no longer redefine UCN institutional topology.
- Inventory and report selectors consume active canonical Programs while historical rows retain
  their saved identities.
- Existing current routing relationships are protected from unsafe automatic reconciliation.
- `organization.structure.view` remains the safe reference-read capability.
- `organization.manage` remains a legitimate operational GCO capability.
- OpenAPI and the generated frontend client lose twelve fake structural mutation operations.
- Campus/College/Program pages remain useful searchable/filterable read-only reference surfaces.
- Academic Year, Service Catalog, Institutional Forms, and Privacy ownership decisions are unchanged.
- Organization synchronization is not added to `/health/ready`; deployment explicitly owns it.
- No new database migration is required.
