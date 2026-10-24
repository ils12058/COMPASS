# Integrity, authority and concurrent administration

Current facts are **VERIFIED CODE FACT**; all new rules below are **PROPOSED DESIGN** requiring the
identified institutional choices before activation. No permission or institutional policy is granted here.

## Institutional identity and hierarchy

Keep existing UUIDs. A rename changes `name`, timestamps and resource version on the same row;
there is no replacement row, FK rewrite, alias or code substitution. Trim/uppercase codes exactly
as current `normalize_code` does; reject blank/too-long codes/names and control characters using
bounded API/service validation. Preserve uniqueness at the existing database keys. Do not reuse a
retired code for a different institution entity: create a distinct approved code/UUID through a
separate decision. Display name is not uniqueness or entity identity.
Sources: [be/compass/organization/models.py:11](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L11);
[be/compass/organization/models.py:76](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L76);
[be/compass/organization/models.py:104](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L104).

Ordinary editing accepts name, permitted status and Program policy only. `code`, Campus parent and
College parent are immutable after create through these APIs; reject supplied structural fields,
not silently ignore them. New College requires active Campus; new Program requires active College
and Campus. Activation rechecks the whole chain. No automatic parent activation, child retirement
or reassignment. Existing contradictory active flags remain visible as migration findings; do not
repair them during backfill.

Structural transfers would move historical Inventory/Tracer/report grouping through current FK
joins and alter College routing/scope. Mergers or code substitutions would collapse identities and
external references without proof of equivalence. Exclude transfers, mergers, aliases, code changes
and effective-dated reorganization from ORG-2. A future workflow needs explicit institutional basis,
old/new identity mappings, period-aware placement, pending work ownership and historical-output
review. A normal rename requires none of that identity replacement.

## Retirement blockers and impact projection

Deletion is not an ordinary catalog operation. PROTECT alone blocks deletion, not `is_active=False`.
Use the [consumer-specific matrix](dependency-and-history-matrix.md), not a count of all foreign keys.

| Target | Hard blockers proposed | Warnings/preserved evidence |
|---|---|---|
| Campus | Any active child College; active-Student affiliations/responsibilities anywhere below if inconsistent pre-existing flags hide them | Inactive children and their historical references; open work ownership review |
| College | Any active child Program; any affiliation belonging to active STUDENT role (CURRENT, GRADUATING or ALUMNI); any CounselorResponsibility row | Inactive-account affiliation rows; submitted Inventory/Tracer via descendants; saved routing threads |
| Program | No automatic blocker for submitted history; block if future actual current-placement owner adds such a contract | Draft Inventory counts and pending F4/other work warning; submitted facts/certificates retained |

The active-Student blocker is deliberately broader than CURRENT-only to avoid silently stranding an
active GRADUATING/ALUMNI account that current routing still accepts. Inactive-account affiliation
retention can be permitted only with explicit reactivation remediation. Account reactivation must
check the retained affiliation's chain or return an actionable conflict; never silently reassign.
Blocking every stale responsibility row makes cleanup explicit rather than guessing whether its
inactive Counselor assignment is still intended. Head fallback is not a workaround for inactive
College/Campus, because current routing exits before fallback.

An open domain workflow is not automatically an infinite blocker. Preview open Guidance threads,
relevant pending delegated work and requests whose visibility depends on the retiring College;
require the owning domain to show preserved relationship access or explicit remediation. ORG-4 must
test those access paths before approving the blocker contract. Historical resolved threads and
issued certificates alone do not forbid retirement.

**PROPOSED API projection:** `organizationGet{Campus|College|Program}Impact` (GET, proposed names),
authorized by catalog management; bounded aggregate counts with target UUID, resource version,
observed_at, `can_deactivate`, typed blocker codes, warning codes and aggregate preserved-reference
categories. Count distinct rows with indexed foreign-key filters, not join-multiplied totals.
Include direct and descendant active children, all/active/CURRENT Student affiliations, all/valid
Counselor responsibilities, Inventory drafts/submitted records, Tracer references and open/resolved
routing threads. Pending F4 counts are indirect via Inventory Program or affected Student affiliation;
certificate College text alone is not a reliable FK count. Do not approximate such counts by matching
names. Bound examples, if any, and apply existing account/domain permissions; default to no names
or confidential content. Catalog authority does not authorize reading form contents.

No actual operational counts were queried in ORG-0. Fixtures can prove numeric aggregation only.
Preview is advisory and may become stale immediately; mutation repeats every blocker query under
its transaction gate. A version check on the target alone cannot detect a newly inserted child.

## Catalog authorization

Current `organization.manage` controls affiliation/responsibility/supervision and retains its
meaning. Existing policy grants it to IT Admin and Head Guidance designation. Safe structure reads
are separately authorized. Recent MFA is already enforced for relationship mutations.
Sources: [be/compass/accounts/policy.py:216](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/policy.py#L216);
[be/compass/accounts/policy.py:579](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/policy.py#L579);
[be/compass/accounts/policy.py:699](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/policy.py#L699);
[be/compass/organization/api.py:169](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/api.py#L169).

**Recommendation:** introduce `organization.catalog.manage`, dependent on
`organization.structure.view`, with **no default role or designation grant**. Permit backend
mutations only for active authenticated staff roles selected by institutional decision; initial
recommended eligible set is IT_ADMIN, COUNSELOR, GUIDANCE_SERVICES_STAFF with explicit individual
authority. Deny STUDENT and unsupported roles even if a malformed override names the capability.
Use the same role fence in effective capability validation, override assignment and domain services,
so an apparently granted but unusable capability is explained consistently. Broader staff delegation
versus IT-only initial use is an open policy choice; a role baseline is not an editor assignment.

Alternatives: reuse organization.manage (reject, overbroad); IT_ADMIN hardcode (simple but prevents
approved delegation and conflates IT with institutional authority); new designation (only if the
institution actually defines it); focused capability with explicit role fences (select). Existing
`institutional_designations.manage` plus `accounts.manage` shows an established distinct delegation
boundary; don't reuse that designation-specific permission as a catalog permission.
Sources: [be/compass/account_management/services.py:76](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/account_management/services.py#L76);
[be/compass/accounts/services.py:128](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/services.py#L128);
[be/compass/accounts/policy.py:741](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/policy.py#L741).

ORG-2 must require recent MFA in API **and the service entry point for user mutations**, using the
existing session helpers and authenticated actor, including active/role/capability recheck. Missing
active authenticator returns `mfa_setup_required`; stale verification returns `recent_mfa_required`.
A frontend check is UX only. CSRF/session authentication remains unchanged. No seed command or
system context is an alternate route for ordinary user CRUD.
Source: [be/compass/authentication/step_up.py:31](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/authentication/step_up.py#L31).

Grant installation, actor eligibility, approval evidence, approval owner and whether sensitive
classification changes require separate approval are **INSTITUTIONAL DECISION REQUIRED**. No
mandatory memo-number format is invented. A bounded institutional basis/reference can be recorded
when required by the approved procedure. Ordinary relationship managers receive no expanded rights.

## Audit evidence

Reuse existing actions where their semantics fit: `organization.campus.created/updated/enabled/disabled`,
College/Program equivalents already remain defined for historical records. Add a specific
`organization.program.policy_changed` action for academic policy changes and narrow initialization
seed/adoption actions. A rename can use `.updated` with changed_fields=[name] and old/new names;
avoid emitting two success events for one logical change. Existing `organization.catalog_synced`
remains valid old history, not the future administrator-action name.
Source: [be/compass/audit/actions.py:20](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/audit/actions.py#L20).

Record actor/request/target UUID, immutable code/parent identity, resource versions, changed fields,
bounded before/after name/status/policy, and approved basis reference where appropriate. Never copy
student lists, Inventory content or counseling facts into the catalog Audit. Use metadata limits:
8,192 bytes, depth 4, list length 64, string length 1,024; validate before committing.
Sources: [be/compass/audit/metadata.py:14](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/audit/metadata.py#L14);
[be/compass/audit/services.py:56](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/audit/services.py#L56).

Successful mutation and synchronous Audit append share the same atomic transaction. Failed audit
must roll back the entity and resource version. No-op requests produce no fake change event.
Unsupported structural requests are rejected by strict schema/service contracts; if a domain-denied
attempt is audited, persist only bounded denial codes in an independent transaction after rollback,
consistent with record_event's documented DENIED/FAILED convention. Do not attempt to preserve a
success audit inside a rolled-back transaction or add noisy per-field validation logs without need.

Restricted change history must not reuse broad privacy/audit access or expose unrelated events.
Propose a bounded target-specific projection, permission-scoped to catalog managers, containing only
catalog-safe fields. This is a new ORG-2 contract, not an existing change-history endpoint.

## Concurrency and transaction design

Existing code has row locks for relationships and Catalog sync and unique DB constraints. It has
no catalog resource-version field. Inventory currently locks Program, not its ancestors; F4 reads
policy without locking Program. Parent retirement, child insertion, account reactivation and policy
changes therefore need a shared concurrency contract before CRUD goes live.
Sources: [be/compass/organization/services.py:254](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L254);
[be/compass/inventory/services.py:542](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/services.py#L542);
[be/compass/good_moral/services.py:452](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L452).

**PROPOSED DESIGN:** start with one documented PostgreSQL transaction advisory gate for catalog
integrity. Catalog initialization/status/policy/name/create mutations take it exclusively. Dependent
writes that validate/select Catalog facts take it shared **before any user/domain/parent row lock**.
Ordinary reads do not need it. The gate is small, cooperative and justified by actual absent-child
and cross-domain status/policy races; it is not a generic lock framework, database authority fence
or defense against unmodified old code/raw SQL. Catalog writes are infrequent and serialize globally;
shared dependent operations still run concurrently. If later measurements justify finer granularity,
replace it only with equivalent race tests.

Participants include Organization relationship assignment, Inventory Program/year replacement and
submission, F4 academic creation/year correction, and Account reactivation/role transitions that can
change blocker status. All acquire the gate before their existing management/user mutexes. Catalog
writes take gate, then ancestry Campus → College → Program (sorted UUIDs for multiple rows), then
target row; they must not lock arbitrary dependent User rows afterward. Recheck actual code lock
order in ORG-2 and revise all participants together to avoid user→parent / parent→user deadlocks.
Future SAR current-placement writers must join the same contract. Historical-only reads and F6
reported-text creation need no invented policy lock. Do not strengthen F4 issuance eligibility
incidentally; if later approved, its new policy read must also participate.

Add positive integer `resource_version` to Campus/College/Program in ORG-2 (anticipated additive
migration after ORG-1). Mutations require expected version, lock and re-read, compare, validate,
write and increment once, audit, commit. No optional version bypass on user endpoints. Duplicate
creation still depends on DB uniqueness; catch IntegrityError at a savepoint and translate it to a
safe business conflict. Strictly reject parent/code edits before attempting database mutation.

| Race/failure | Protection / required PostgreSQL regression |
|---|---|
| Same normalized code twice | Unique DB key + normalized service input; one success, one typed duplicate conflict |
| Rename vs rename/status/policy | Exclusive gate + locked target + expected version; stale writer 409 |
| Child creation vs parent retirement | Exclusive gate serializes, parent recheck; no active orphan |
| Affiliation/responsibility vs retirement | Shared/exclusive gate before row locks; mutation sees committed blocker or assignment sees inactive parent |
| Student reactivation vs College retirement | Shared gate + account's retained-affiliation validation, or deactivation sees active user |
| Inventory submit/F4 create vs policy change | Shared gate locks decision until commit; new operation sees one coherent policy |
| Stale impact preview | Recount under exclusive gate; version alone not trusted |
| Audit validation/database failure | Same transaction rolls back state/version; failed-attempt evidence separately bounded |
| Direct privileged SQL / old writer | Cooperative gate cannot protect; operationally retire/restrict and audit these writers at cutover |

Actual concurrency tests are a future ORG-2/4 gate. Sequential audit regression results do not prove
these proposed locks, blocker rules or version checks exist today.
