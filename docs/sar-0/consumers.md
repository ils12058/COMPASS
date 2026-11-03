# Consumers — who writes and reads each academic fact

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
Every claim is marked **Verified**, **Inferred** or **Unknown**.

## 1. Consumer matrix

| Consumer | Academic data used | Source | Authorization / scope | Coupling risk | Evidence |
|---|---|---|---|---|---|
| Organization affiliation admin | Current College | `StudentAffiliation` | `organization.manage` + recent MFA | Only writer; destructive transfer/removal | `be/compass/organization/api.py:489,526-548`; `be/compass/organization/services.py:271-325` |
| Account creation / CSV import | None | — | Account management capability + MFA | Provisioned Student has no placement | `be/compass/account_management/services.py:668-747`; `be/compass/account_management/csv_import.py:37-39` |
| Account role change | Affiliation existence only | `StudentAffiliation` | Account management | Blocks role change until affiliation removed; lifecycle not cleared | `be/compass/organization/services.py:137-162`; `be/compass/account_management/services.py:940-999` |
| Individual Inventory (Student) | Program, Year Level | `StudentInventory` | `inventory.view_self` / self | No affiliation-College cross-check | `be/compass/inventory/services.py:1167-1245,1385-1455` |
| Inventory staff lists | Affiliation College, Inventory Program | both | Operational scope | Mixed sources in one workspace | `be/compass/inventory/services.py:432-439,1541,1612` |
| Good Moral (current Student) | Affiliation College; Inventory Program/year level; Program policy | both | `good_moral.view_self` / operational roles | College and Course snapshot can come from different Colleges | `be/compass/good_moral/services.py:455-544,790-839` |
| Good Moral (Graduate) | Degree text, graduation date | request input | self/operational | Independent of Tracer and SAR; not verified | `be/compass/good_moral/services.py:857-920` |
| Graduate Tracer | Graduated College/Program/year | self-report | `graduate_tracer.*_self` | Self-reported; no official record; service-only College/Program check | `be/compass/graduate_tracer/services.py:515-583` |
| Counselor routing / appointments | Current College | `StudentAffiliation` | Operational scope | Transfer changes future routing immediately; no as-of history | `be/compass/organization/services.py:105-134`; `be/compass/appointments/services.py:602,625` |
| Appointment access | Current College | `StudentAffiliation` | Operational responsibility scope | Inactive/anomalous affiliation denies access | `be/compass/appointments/access.py:40-46,98-107` |
| Counseling context / continuity / coverage / handoff | College + Program + Year Level | affiliation + Inventory | Encounter/assignment scope | Displays a College and Program that may belong to different Colleges | `be/compass/counseling/context_services.py:180-243`; `be/compass/counseling/continuity_access.py:66`; `be/compass/counseling/coverage_selection.py:59-86`; `be/compass/counseling/handoff_services.py:68` |
| Guidance follow-ups | Current College | `StudentAffiliation` | Operational responsibility scope | Routing and visibility follow the current College | `be/compass/guidance_followups/policy.py:190-249`; `be/compass/guidance_followups/recovery.py:59-107`; `be/compass/guidance_followups/workspace.py:114` |
| Guidance messages | Current College | `StudentAffiliation` | Operational scope | Same as follow-ups | `be/compass/guidance_messages/services.py:228,253` |
| Referrals / Faculty placement | Current College | `StudentAffiliation` | Faculty ceiling + GCO routing | Faculty placement resolver will need a SAR adapter | `be/compass/referrals/faculty_placement.py:22-40`; `be/compass/referrals/services.py:236-268` |
| Call slips | Current College | `StudentAffiliation` | Operational scope | Student selection depends on current affiliation | `be/compass/call_slips/services.py:253,268-270` |
| Student support | Current College | `StudentAffiliation` | Operational scope | Access denies without active affiliation | `be/compass/student_support/services.py:60-80` |
| Assessment records | Current College | `StudentAffiliation` | Operational scope | Student search depends on affiliation | `be/compass/assessment_records/services.py:85-95` |
| Operational student picker | Current College | `StudentAffiliation` | Scope input | Fail-closed empty scope; no affiliation means invisible | `be/compass/operational_students.py:79-131` |
| Reports | Inventory Program/Year Level; affiliation for current-year coverage | both | `reports.view` + active College scope | Same report can use different College sources | `be/compass/reports/services.py:413-433,1011-1027` |
| Group sessions | None | — | — | No academic filtering or snapshot | `be/compass/group_sessions/models.py:185-224` (registration stores Student only) |
| Notifications | No academic fields; events about Good Moral/Inventory/appointments | domain events | Recipient policy | Indirect only; no academic payload | `be/compass/notifications/policy.py:41-70`; `email_presentation.py` has no College/Program/Year fields |
| Privacy / retention | Audit metadata; retention register | audit + register | DPO/oversight | No academic-record retention category adopted | `be/compass/privacy_governance/retention_policy_register.py:96-118` |
| FUP-3C | Would require canonical current College | not implemented | — | **Unknown**; no `FUP-3C` reference in repository | repository search |
| Faculty academic-contact attestation | Would require enrollment/teaching verification | not implemented | — | **Unknown**; explicitly absent per FAC-D9 | `docs/fac-5/institutional-decisions.md:121-133` |
| Seeds / verification | Affiliation and Inventory consistency | both | seeding service calls | Seeds enforce persona alignment; no independent cross-check | `be/compass/staging_seed/organization.py:139-184`; `be/compass/staging_seed/history.py:147-171` |
| Frontend affiliation page | Current College | affiliation API | `organization.manage` | Table shows Student, ID, College, Campus only | `fe/src/features/organization/student-affiliations/student-affiliations-page.tsx:359-462,582` |
| Frontend Inventory editor | Program, Year Level, course text | Inventory API | self | Program change rewrites course text; Year Level filtered by policy | `fe/src/features/inventory/editor/education-section.tsx:92-175` |
| Frontend Tracer form | Graduated College/Program/year | Tracer API | self | Program list filtered by selected College; both required | `fe/src/features/graduate-tracer/graduate-tracer-form-sections.tsx:89-169` |
| Frontend Good Moral form | Year Level (read-only), Semester | Good Moral API | self | Year Level comes from submitted Inventory; no College/Program selection | `fe/src/features/good-moral/good-moral-request-page.tsx:236,313-330` |
| Generated API client | Affiliation request/response | OpenAPI | — | SAR-1 must not silently change these contracts | `fe/src/lib/api/generated/model/studentAffiliationRequest.ts`; `studentAffiliationResponse.ts` |

## 2. Writer map

**Verified.** The only writer of academic placement is `set_student_affiliation` /
`remove_student_affiliation` in `be/compass/organization/services.py:271-325`. Inventory,
Good Moral, Tracer and account provisioning write their own domain records; none writes
`StudentAffiliation`.

**Verified.** Seeds call the same services: `ensure_organization` calls `set_student_affiliation`
(`be/compass/staging_seed/organization.py:176-184`), and `seed_annual_inventory` calls
`replace_current_inventory`/`submit_current_inventory` (`be/compass/staging_seed/history.py:147-171`).
There is no direct `StudentAffiliation.objects.create` outside the service.

**Verified.** Account Management writes only a Faculty affiliation on account creation
(`be/compass/account_management/services.py:742-747`); Student provisioning has no equivalent
write.

**Inferred.** A future SAR writer must become the single write path before `StudentAffiliation` can
be retired. The proposal's Phase 4 consumer migration and Phase 6 retirement assume this, but the
current code has no compatibility adapter or second writer.

## 3. Reader map by concept

### 3.1 Current College

**Verified.** Current College is read from `StudentAffiliation` by:

- Counselor default resolution and appointment booking (`be/compass/organization/services.py:105-134`; `be/compass/appointments/services.py:602,625`).
- Appointment visibility (`be/compass/appointments/access.py:40-46,98-107`).
- Operational responsibility scope and all dependent workspaces (`be/compass/organization/access_scope.py:70-106`; `be/compass/operational_students.py:79-131`).
- Follow-ups (`be/compass/guidance_followups/policy.py:190-249`), messages (`be/compass/guidance_messages/services.py:228,253`), referrals (`be/compass/referrals/faculty_placement.py:22-40`), call slips (`be/compass/call_slips/services.py:253,268-270`), student support (`be/compass/student_support/services.py:60-80`), assessment records (`be/compass/assessment_records/services.py:85-95`).
- Counseling context (`be/compass/counseling/context_services.py:180-210`).
- Reports current-year coverage (`be/compass/reports/services.py:1011-1027`).
- Good Moral current-student college snapshot (`be/compass/good_moral/services.py:790-825`).
- Organization catalog impact counts (`be/compass/organization/catalog_services.py:518-566`).
- Staging seed verification (`be/compass/staging_seed/verify.py:505,615`).

### 3.2 Program and Year Level

**Verified.** Program and Year Level are read from the selected Academic Year's Inventory by:

- Inventory self and staff views (`be/compass/inventory/services.py:1167-1245,1385-1455,1541,1612`).
- Good Moral F4 eligibility and snapshots (`be/compass/good_moral/services.py:455-507,790-825`).
- Reports profiling (`be/compass/reports/services.py:413-433`).
- Counseling context (`be/compass/counseling/context_services.py:220-243`).
- Catalog impact (`be/compass/organization/catalog_services.py:518-566`).
- Seed inventory construction (`be/compass/staging_seed/history.py:147-171`).

**Verified.** No consumer reads a “current Program” outside an Academic Year. The only Program on a
Student-affiliated record is the per-year Inventory row.

### 3.3 Graduation

**Verified.** Graduation facts are read only from `GraduateTracerResponse` and the Graduate Good
Moral variant. The Tracer is self-reported and has no link to the Good Moral graduation date
(`be/compass/graduate_tracer/models.py:259-273`; `be/compass/good_moral/services.py:857-920`).

**Inferred.** No consumer currently reads a verified graduation record, because none exists.

## 4. Cross-domain inconsistency paths

1. **Inventory vs affiliation College.** **Verified.** A Student can select any active Program
   whose College is not their affiliation College. Good Moral then snapshots the affiliation
   College and the Inventory course together (`be/compass/good_moral/services.py:818-825`), and
   counseling context displays both (`be/compass/counseling/context_services.py:220-243`).
2. **Reports vs affiliation.** **Verified.** Current-year coverage counts Students by affiliation
   College, while submitted-inventory profiles are filtered by Inventory Program College
   (`be/compass/reports/services.py:413-433,1011-1027`). A report can show a Student as “missing”
   in one College while their submitted Inventory is profiled under another.
3. **Transfer vs history.** **Verified.** After a transfer, every reader in §3.1 sees the new
   College immediately; prior snapshots remain unchanged. The only relational trace is audit
   metadata. There is no supported “as of” query.
4. **Lifecycle vs role.** **Verified.** A role change away from `STUDENT` requires removing the
   affiliation first, but leaves `student_lifecycle_status` intact. If the account later returns to
   `STUDENT`, the old lifecycle value can be reused (`be/compass/account_management/services.py:976-979`).
5. **Tracer vs affiliation.** **Verified.** Tracer College/Program is self-reported and independent
   of the current affiliation; there is no consistency check between the two. This is intended for
   graduates, but it means “College” means different things in different records.

## 5. Consumer migration implications

**Inferred.** Replacing `StudentAffiliation` reads is not a single adapter change:

- Authorization scopes in at least ten domains use the affiliation relation directly in querysets,
  not through one resolver (`appointments`, `assessment_records`, `call_slips`, `counseling`,
  `guidance_followups`, `guidance_messages`, `inventory`, `referrals`, `reports`,
  `student_support`).
- `be/compass/referrals/faculty_placement.py:1-40` is the only file explicitly described as a
  read-only placement boundary that “SAR may replace”; it is not used by the other domains.
- Reports and Good Moral combine affiliation and Inventory in one response, so they need an
  explicit conflict rule, not a mechanical source swap.

**Recommendation for SAR-1:** do not migrate these consumers. Add a single read adapter and keep
`StudentAffiliation` authoritative until the institution approves a cutover and conflict policy.

## 6. Consumers with no current academic dependency

**Verified.** Group sessions identify registrants by Student FK only and have no College, Program or
Year Level fields (`be/compass/group_sessions/models.py:185-224`). Notifications carry event codes
and recipient policy, not academic fields (`be/compass/notifications/policy.py:41-70`). The privacy
activity export exports audit-event projections, not academic records
(`be/compass/privacy_governance/activity_export.py:28-75`).

**Unknown.** Whether any external report, spreadsheet or downstream office consumes CSV/XLSX
exports with College/Program columns. Repository inspection found no account-level academic CSV
export builder; the reports domain does produce PDF/XLSX outputs with academic dimensions
(`be/compass/reports/pdf.py`, `be/compass/reports/xlsx.py`), but those builders were not inspected
line-by-line. Operational use outside the repository cannot be verified.
