# Dependencies, history and routing

**VERIFIED CODE FACT:** current code relationships and behavior below. **PROPOSED DESIGN:** migration,
blocker and regression columns. No counts describe a deployed population. `D` = direct catalog FK,
query or policy lookup; `I` = indirect through affiliation, Program FK or scope resolver.
Owners: ORG-1 authority/policy conversion, ORG-2 mutation safeguards, ORG-3 UI, ORG-4 regression.

## Complete catalog foreign-key inventory

| Reference | Category | Retirement/historical rule (proposed) |
|---|---|---|
| College.campus (PROTECT) | Current hierarchy | Active child blocks Campus retirement; inactive child remains readable |
| Program.college (PROTECT) | Current hierarchy | Active child blocks College retirement; no cascade |
| StudentAffiliation.college (PROTECT) | Current Guidance placement | Block while any active STUDENT account is affiliated (all lifecycle states); explicit reassignment/removal; inactive account rows preserved as warning |
| CounselorResponsibility.college (OneToOne PROTECT) | Current routing configuration | Block any assignment row, including stale/inactive Counselor; explicit cleanup first |
| StudentInventory.program (nullable PROTECT) | Draft operational / submitted history | Draft is warning and future-submit conflict; submitted references never block Program retirement by themselves |
| GraduateTracerResponse.graduated_college/program (nullable PROTECT) | Student-submitted graduation facts | History never deleted/reparented; explicit historical choice policy, not current placement |
| GuidanceThread.routing_college (nullable PROTECT) | Saved routing context, open or resolved work | Count separately; open threads require ownership/scope review; resolved history preserved, not blanket retirement blocker |

Sources: [be/compass/organization/models.py:62](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L62);
[be/compass/organization/models.py:117](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L117);
[be/compass/organization/models.py:141](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/models.py#L141);
[be/compass/inventory/models.py:224](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/models.py#L224);
[be/compass/graduate_tracer/models.py:259](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/graduate_tracer/models.py#L259);
[be/compass/guidance_messages/models.py:30](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/guidance_messages/models.py#L30).

StaffSupervision has no catalog FK; Accounts has no Campus/College/Program fields. Good Moral stores
an Inventory FK and local certificate facts, not direct College/Program FKs. Exit/Routine use
Inventory/AcademicYear and Student/Counselor references rather than new catalog placement fields.
No current StudentAffiliation Program FK exists; future SAR is not an existing dependency.

## Cross-domain consumer matrix

| Consumer and source | D/I; current behavior; historical/live need | Migration impact / failure mode | Required regression and owner |
|---|---|---|---|
| [be/compass/organization/services.py:203](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L203) and catalog API | D: optional status/parent filters, live names, inactive detail | Row-only active filters can leak active child under inactive parent to selectors | Shared active-chain selector; preserve reference reads, ORG-1/4 |
| [be/compass/organization/services.py:268](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L268) | D: current College; locks Student and active College/Campus | Retirement can strand active Student; rename should not change assignment | Assignment vs retire race, explicit reassign, no UUID change, ORG-2/4 |
| [be/compass/organization/services.py:324](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L324) | D: current routing row, active roles/parents | Stale/inactive Counselor leaves fallback or unresolved result | Missing/inactive/wrong-role Counselor and retirement blockers, ORG-2/4 |
| [be/compass/organization/services.py:387](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L387) | I: current supervision → Counselor scope | Retired College shrinks inherited scope; no capability inheritance | GSS with ordinary/Head/inactive supervisor, ORG-4 |
| [be/compass/organization/access_scope.py:109](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/access_scope.py#L109) | I: active College/Campus; Head sees all active Colleges; handled workload is separate | Retiring College removes ordinary and general Guidance visibility | General scope vs handled fallback equality and denials, ORG-4 |
| [be/compass/account_management/services.py:661](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/account_management/services.py#L661) and [be/compass/account_management/csv_import.py:33](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/account_management/csv_import.py#L33) | No placement creation; CSV accepts identity/role + optional middle_name/suffix only | Do not assume account provisioning configures affiliation/Program | New Student remains unaffiliated; reject speculative CSV catalog headers, ORG-4; SAR later |
| [be/compass/account_management/services.py:865](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/account_management/services.py#L865) and account active-state mutation | I: Organization role-transition validator; disabling retains relationships | Role change blocked; disable makes routing/scope unavailable, no automatic cleanup | Reassign/remove before role transition; disabled relationship retained, ORG-4 |
| [be/compass/accounts/services.py:92](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/accounts/services.py#L92) / policy / account management | I: role/designation/override authority | Broad reuse of organization.manage would overgrant official edits | Catalog-specific dependency/revoke/expiry/role tests, ORG-2/4 |
| [be/compass/inventory/services.py:542](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/services.py#L542) and `_validate_program_year_level` | D: new Program active chain, current metadata; records retain FK/year/course | Unknown policy permissive in Inventory; stale Program/parent policy race | Configured/pending/unknown, parent retire vs submit, ORG-1/4 |
| [be/compass/inventory/api.py:891](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/api.py#L891) / [be/compass/inventory/documents.py:200](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/documents.py#L200) | D: live Program summary plus saved course for document | API label may rename while printed submitted course remains old | Preserve both semantics explicitly; never backfill course from current name, ORG-4 |
| [be/compass/good_moral/services.py:452](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L452) / F4 creation/correction/issue | I: Inventory Program and current policy; affiliation College for new snapshot; local saved facts | New DB Program fails Python whitelist; policy changes affect new/corrected year, not generic issuance recheck | Approved new Bachelor, pending/non-Bachelor, level 5, replay, pending/issued snapshots, ORG-1/4 |
| [be/compass/good_moral/services.py:849](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L849) / F6 | I: reported historical qualification, no current catalog eligibility lookup | Changing suggestions into whitelist would reject legitimate history | F6 current postgraduate reenrollment, historical degree text and issuance, ORG-1/4 |
| [be/compass/good_moral/api.py:685](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/api.py#L685) | D: code-registry Bachelor names, advisory options | Names/additions/retirements stale after DB maintenance | DB active-chain suggestions; duplicates deduplicated names as existing shape, ORG-1 |
| [be/compass/graduate_tracer/services.py:551](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/graduate_tracer/services.py#L551) / API projections | D: validates existence and parent match; no active-chain validation on supplied FK | Historical inactive degrees still submit through crafted payload; ordinary options omit some inactive rows | Keep inactive historical reference semantics deliberate; active-new vs historical policy decision, ORG-4 |
| [be/compass/graduate_tracer/services.py:1081](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/graduate_tracer/services.py#L1081) | D: active College; active Program+College, missing Campus status filter | Active child can appear beneath inactive Campus | Active-chain current options plus explicit retained/historical option path, ORG-1/4 |
| [be/compass/reports/graduate_tracer.py:307](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/reports/graduate_tracer.py#L307) and `graduate_tracer_xlsx.py` | D: submitted response population; live names; IDs in filters; codes in release/file labels | Rename changes report labels, transfer reclassifies old grouping | Retired history remains filterable; totals stable under rename, ORG-4 |
| [be/compass/reports/services.py:413](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/reports/services.py#L413) | I: submitted Inventory Program/year; current parent joins; current scope | College transfer moves historic profile grouping; inactive scope can remove scoped access | UUID rename preserves population, global inactive history vs scoped access explicit, ORG-4 |
| [be/compass/reports/services.py:57](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/reports/services.py#L57) / coverage | I: coverage Campus/College from current Guidance affiliation; profile from Inventory Program | False assumption that coverage and profiling populations match | Keep coverage semantics and no-inventory population, ORG-4 |
| [be/compass/operational_students.py:79](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/operational_students.py#L79) | I: active CURRENT Students, current College; inactive org gives no College / scoped exclusion | Retirement can remove Students from narrow operational pickers | Block/remediate live affiliation; selector access regressions, ORG-2/4 |
| [be/compass/appointments/services.py:37](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/appointments/services.py#L37) and [be/compass/appointments/access.py:52](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/appointments/access.py#L52) | I: default provider routing; existing provider relationship; non-Counseling handled College access | Retirement loses default routing/GSS delegated access but must not rewrite provider ownership | Provider-owned Counseling stays relationship-only; Head not blanket owner, ORG-4 |
| [be/compass/counseling/context_access.py:50](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/counseling/context_access.py#L50) / [be/compass/counseling/context_services.py:177](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/counseling/context_services.py#L177) | I: time-bounded provider context; live affiliation and Program/course overview | Must not equate catalog manage/Head with confidential access | Name/status changes never grant encounter access; no ownership/key changes, ORG-4 |
| [be/compass/counseling/continuity_services.py:74](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/counseling/continuity_services.py#L74) / `continuity_access.py` | I: affiliation marker plus policy/scoped grants, selected source revisions | Reparenting/removing affiliation may invalidate grants; rename must not authorize more | Existing default-deny policy stays unchanged; no auto reassignment/rebinding, ORG-4 |
| [be/compass/exit_interviews/services.py:39](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/exit_interviews/services.py#L39) / [be/compass/exit_interviews/opportunities.py:32](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/exit_interviews/opportunities.py#L32) | I: lifecycle/opportunity eligibility, Inventory-derived saved course, current operational/Head scope | Retirement changes selectors, must not rewrite submitted Exit facts | Eligibility unchanged, stored snapshots and historical authorized reads, ORG-4 |
| [be/compass/routine_interviews/services.py:372](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/routine_interviews/services.py#L372) / [be/compass/routine_interviews/api.py:436](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/routine_interviews/api.py#L436) | I: optional Inventory/current year context; saved course text when submitted | Linked inventory is context, not academic enrollment authority; no automatic mandatory-inventory rule | Direct initiation without Inventory, linked snapshot after rename, ORG-4 |
| [be/compass/guidance_messages/services.py:255](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/guidance_messages/services.py#L255) / `policy.py` | D/I: saved routing_college and Counselor; default routing and current scopes | Open thread may become operationally unreachable after College retirement | Review open-thread owner/scope; historical closed read policy remains, ORG-2/4 |
| [be/compass/referrals/services.py:214](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/referrals/services.py#L214) / `call_slips/services.py` / `student_support/services.py` | I: handled/general scope and current affiliation, domain permissions | Retirement shrinks current queues/selectors; no historical FK repair | Existing allowed/denied actions, pending workloads preview, ORG-4 |
| [be/compass/assessment_records/services.py:77](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/assessment_records/services.py#L77) | I: current organizational Student discovery; domain confidentiality | Catalog permission must not expose protected assessment content | Selector scope and confidential denied access unchanged, ORG-4 |
| [be/compass/guidance_followups/workspace.py:13](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/guidance_followups/workspace.py#L13) / `policy.py` / `recovery.py` | I: current College visibility, owned cases and recovery | Retiring current org can orphan work/resolution; no silent handoff | Count relevant pending work, preserve case ownership/denials, ORG-2/4 |
| [be/compass/activity/supervised.py:14](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/activity/supervised.py#L14) / `service_catalog/access.py` / `group_sessions/access.py` | I: supervision/role/resource access, not catalog authority | Overbroad new grant/gate could leak supervised work | No authority inheritance; group/provider ownership unchanged, ORG-4 |
| [be/compass/staging_seed/organization.py:80](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/staging_seed/organization.py#L80), `students.py`, `staff.py`, verify/reports | D/I: fixture code identities and display labels; seed mutates operational rows | Direct sync or canonical active checks erase/reject edits | Preserve admin changes, fail fixture preflight explicitly; authority inventory, ORG-1/4 |
| Proposed SAR | Future, no current implementation | A second hardcoded catalog would recreate dual authority | Consume UUID lookup/current-policy/active-selection interfaces below; no ORG-0 SAR work |

## Historical presentation matrix

A finalized record is not automatically a complete snapshot. This table distinguishes stored facts
from related-record presentation; **no full name-history subsystem is proposed**.

| Consumer | Stored historical snapshot | Current related presentation | Rename/retirement recommendation |
|---|---|---|---|
| Submitted Inventory | `course_currently_enrolled`, major, year, person/form/submission facts | Program code/name/College ID in API; reporting traverses current parents | Printed/submitted course unchanged; label linked reference as current; preserve FK |
| Issued F4 | applicant, College/course/major/year/semester text; form/template/version, issuer/time | AcademicYear label remains a join (separate ownership) | Catalog rename never alters certificate text; no reissue |
| Issued F6 | applicant, reported degree/major/date, issuance/form/template facts | No catalog FK needed for degree text | Reprint saved facts; advisory suggestions can change |
| Graduate Tracer | respondent name, graduation year and academic education rows; College/Program IDs | `graduated_college`/`graduated_program` names are live; no frozen catalog name fields | Treat labels as current catalog identity unless institution requires as-of names; if required, snapshot new submissions only; older names not inferable |
| Exit Interview | course/major/person snapshots copied from Inventory then controlled form facts | Student identity/academic-year links and operational College context elsewhere | Preserve saved course; do not refresh finalized form on catalog edit |
| Routine Interview | selected form/interview facts, optional Inventory FK | `_inventory_payload` reads linked submitted Inventory course, not a separate Routine course snapshot | Catalog rename leaves Inventory course; reopened Inventory changes are a separate existing domain concern |
| Counseling Context | encounter/provider ownership; linked academic sources | current affiliation names; Program code/name reference is live, separately from Inventory course snapshot | Explicit mixed current/history labels; no new confidential access |
| Profiling/coverage reports | Inventory year/Program FK and saved academic facts; no frozen report-level catalog names | Current parent/name/grouping and current scoped/coverage affiliation | Rename updates labels, not identity/population; no structural moves in CRUD |
| Guidance Messages | routing_college FK, Counselor/assignment relationships | live catalog name/scope | Preserve row and thread ownership; review open work before retirement |

Sources: [be/compass/inventory/models.py:287](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/models.py#L287);
[be/compass/inventory/api.py:891](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/inventory/api.py#L891);
[be/compass/good_moral/models.py:115](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/models.py#L115);
[be/compass/good_moral/services.py:1695](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/good_moral/services.py#L1695);
[be/compass/graduate_tracer/api.py:545](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/graduate_tracer/api.py#L545);
[be/compass/exit_interviews/documents.py:91](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/exit_interviews/documents.py#L91);
[be/compass/routine_interviews/api.py:436](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/routine_interviews/api.py#L436);
[be/compass/counseling/context_services.py:167](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/counseling/context_services.py#L167).

**INSTITUTIONAL DECISION REQUIRED:** whether formal Tracer exports or reports need historical
as-of official names. An Audit rename event explains changes but is not a complete historical name
resolver. Do not reconstruct names by guessing from current code or synthesize past policy.

## Routing truth table and retirement remediation

Source: [be/compass/organization/services.py:103](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/services.py#L103);
[be/compass/organization/access_scope.py:57](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/access_scope.py#L57);
[be/compass/organization/access_scope.py:92](https://github.com/ils12058/COMPASS/blob/7522e55c94193a28e2e8c6773c634426be48856c/be/compass/organization/access_scope.py#L92).

| Situation | Current default routing result | Required safeguard |
|---|---|---|
| Nonexistent/inactive/non-Student | UNRESOLVED / INVALID_STUDENT | No arbitrary replacement |
| No affiliation | UNRESOLVED / NO_AFFILIATION | Explicit existing affiliation workflow |
| College or Campus inactive | UNRESOLVED / INACTIVE_ORGANIZATION **before Head fallback** | Block retirement while active Student affiliations remain |
| Valid active Counselor assigned | COLLEGE_RESPONSIBILITY | Keep relationship UUIDs through rename |
| Assignment absent, inactive Counselor or wrong role; one valid Head | HEAD_GUIDANCE_FALLBACK | Count fallback workload; don't manufacture per-College responsibility rows |
| Same, no valid Head | UNRESOLVED / NO_HEAD_FALLBACK | Explicit staffing repair; catalog activation cannot promise a counselor |
| Same, multiple valid Heads | UNRESOLVED / AMBIGUOUS_HEAD_CONFIGURATION | No first-row choice; institutional account/designation repair |

GSS with inactive/non-Counselor supervisor resolves empty workload. The unique Head's handled
workload covers otherwise unassigned valid Colleges; general Head College visibility separately
covers all active Colleges. Provider-owned confidential records have different authorization.

**PROPOSED DESIGN:** block College retirement on all active Student-role affiliation rows (not only
CURRENT lifecycle) and every responsibility row; display narrower CURRENT counts separately. Warn
on inactive-account affiliation rows because reactivation will need remediation. Block Campus on
active children and summarize affected relationships across descendants. Do not automatically
remove/reassign relationships. Current behavior blocks all affiliations during old synchronization;
loosening that for inactive accounts is a proposed explicit distinction, not a verified rule.
Open workflow dependencies require owner/scope review where the matrix identifies an actual risk.

Program retirement has no current StudentAffiliation Program placement to migrate. Submitted
Inventory, Tracer and certificate facts stay readable under existing domain authorization. Drafts
cannot newly select/submit inactive Programs; historical Tracer choices require their own policy,
not a blanket prohibition on reporting an old qualification.

## Proposed stable interfaces for future SAR

Organization owns `get_catalog_reference(UUID, include_inactive=True)`, active-chain listing,
`get_program_policy(UUID)` with explicit unresolved values, hierarchy validation and mutation impact.
These are proposed service responsibilities, not existing APIs. SAR should save UUIDs and historical
academic facts, validate new placement against current policy, and keep finalized facts independent
of later catalog renames. It must not use seed codes as identity authority, copy canonical constants,
change Student lifecycle via catalog edits, or replace StudentAffiliation until separately migrated.

Ordinary name edits preserve UUIDs. Transfers/mergers/code reuse would reclassify old FK joins,
change counselor/default scope, affect pending eligibility and stale external code references;
exclude them from ORG-2. A future restructuring workflow needs explicit old/new identities,
period-aware placement, ownership review, snapshots, reconciliation of external codes and separate
institutional approval. Never implement a merge as bulk FK substitution.
