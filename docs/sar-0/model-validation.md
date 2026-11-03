# Model validation — proposed SAR models against current data

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
**Proposal:** *COMPASS — Student Academic Records*, lines 203–278 (models), 280–310 (retention and
consistency), 608–625 (capabilities), 636–696 (migration phases).
Claims are marked **Verified**, **Inferred** or **Unknown**.

## 1. Verdict summary

| Proposed model | Compatible with current data? | Safe SAR-1 scope? | Main reason |
|---|---|---|---|
| `StudentAcademicProfile` | **Yes, as an additive current-state table** | **Yes**, College-only backfill, all unverified | Current affiliation supplies one College; nothing supplies a verified Program or effective date |
| `StudentAcademicPeriodRecord` | **Partially; not backfillable as verified history** | **No** in SAR-1 | No term, enrollment, source or verification data exists; Inventory is per-year and unverified |
| `StudentGraduationRecord` | **No authoritative source** | **No** in SAR-1 | Tracer is self-reported year-only; Good Moral graduation date is request input, not an official record |

## 2. `StudentAcademicProfile`

### 2.1 Field validation

| Proposed field | Current equivalent | Compatibility | Required decision / action |
|---|---|---|---|
| `id` | UUID PK convention throughout | **Verified compatible** | Use UUID PK for consistency |
| `student_id` (1:1 `User`) | `StudentAffiliation.student` is `OneToOneField(primary_key=True)` (`be/compass/organization/models.py:199-206`) | **Verified compatible**; cardinality already matches | Add a role check/service rule; FK cannot constrain “must be a Student” |
| `current_college_id` nullable | `StudentAffiliation.college` is non-null (`:207-209`) | **Verified compatible**; backfill always has a value, but future removal needs null | Keep nullable; do not delete the profile when affiliation is removed without a decision |
| `current_program_id` nullable | No current Program; only per-year Inventory Program (`be/compass/inventory/models.py:224-230`) | **Verified absent**; do not infer | Backfill null; require Program College = current College when set |
| `placement_verification_status` | No verification field anywhere | **Verified absent** | Define vocabulary and authority; default `UNVERIFIED` |
| `placement_effective_at` | `StudentAffiliation.created_at`/`updated_at` only (`be/compass/organization/models.py:216-219`) | **Verified not equivalent** | Leave null at backfill; `created_at` is row creation, not academic effective date |
| `updated_by` | `StudentAffiliation.assigned_by` nullable SET_NULL (`:210-215`) | **Partially compatible**; may be null | Preserve only when known; never invent an actor |
| `created_at` / `updated_at` | Affiliation timestamps exist | **Verified compatible** | New rows can record migration time; original timestamps are provenance, not placement dates |

### 2.2 Gaps and conflicts

1. **Verification provenance is incomplete.** **Verified.** The proposed profile has a verification
   status but no `verified_by` or `verified_at`, unlike the proposed period and graduation models
   (proposal lines 217–225 vs 246–256, 266–275). Without them, a `VERIFIED` value cannot prove who
   verified it or when, except through audit. **Recommendation:** add verifier fields or define that
   profile verification is audit-only. This is a model decision, not a policy assumption.
2. **One status for two independent facts.** **Inferred.** College and Program may have different
   provenance (for example, a verified College with an unverified Program). A single
   `placement_verification_status` cannot express that distinction. The institution must either
   accept a combined status or split verification per field.
3. **Program/College consistency is not a database invariant.** **Verified.** A cross-table check
   cannot be expressed as a simple Django `CheckConstraint`; it needs service validation plus a
   reconciliation query, or a database trigger if the project accepts one. The proposal requires
   consistency but does not specify enforcement.
4. **Removal/former placement is not modeled.** **Verified.** `remove_student_affiliation` deletes
   the current row (`be/compass/organization/services.py:307-325`). A 1:1 profile has no status field for “no
   current placement.” Nulling College and setting `UNVERIFIED` is the least destructive option,
   but it loses the reason and date unless audit is consulted.
5. **Transfer history is not preserved.** **Verified.** Updating the profile in place repeats the
   current affiliation's limitation. The proposal's history intent lives in
   `StudentAcademicPeriodRecord`, which SAR-1 would defer. Therefore SAR-1 must explicitly state
   that it is current-state only and that audit is the only transition history.
6. **No Student entity distinct from `User`.** **Verified.** The proposal says “Student” but COMPASS
   represents Students as `User` + `STUDENT` role + optional lifecycle
   (`be/compass/accounts/models.py:166-233`). A profile row could exist for a non-Student if code is
   bypassed. Service validation and a data-quality query are required.
7. **Existing timestamps are not academic effective dates.** **Verified.** `created_at` on an
   affiliation records when the COMPASS row was created, which may be after the actual placement
   began or after a data import. The proposal says effective date “if known” (line 221); it is not
   known from current data.

### 2.3 Safe backfill rule

**Inferred, recommended for review:** for each existing `StudentAffiliation`, create at most one
profile with `current_college = affiliation.college`, `current_program = NULL`,
`placement_verification_status = UNVERIFIED`, `placement_effective_at = NULL`, and
`updated_by = affiliation.assigned_by` only if non-null. Do not set `VERIFIED`. Do not infer a
Program from the latest Inventory. Do not copy `created_at` into `placement_effective_at`.
Exclude or explicitly classify affiliations on non-Student/inactive accounts after DQ-02 is known.

## 3. `StudentAcademicPeriodRecord`

### 3.1 Field validation

| Proposed field | Current equivalent | Compatibility | Required decision / action |
|---|---|---|---|
| `student_id` | User | **Verified compatible** | Same role constraint as profile |
| `academic_year_id` | Existing `AcademicYear` | **Verified compatible** | Reuse; do not create a parallel year model |
| `term_code` | No term model; Good Moral has two text semesters (`be/compass/good_moral/models.py:42-45`) | **Verified absent** | Define term types/codes and calendar before modeling |
| `college_id` / `program_id` | Per-year Inventory Program and its College; affiliation College | **Partially compatible**; sources can disagree | Define precedence and conflict handling |
| `year_level` | Inventory integer 1–10 (`be/compass/inventory/models.py:233-237`) | **Verified compatible domain** | Retain 1–10; do not copy the F4 1–4 restriction into the record |
| `enrollment_status` | None | **Verified absent** | Define institutional states; do not infer from lifecycle or roster absence |
| `verification_status` | None | **Verified absent** | Define states and authority |
| `source_type` | None; audit has event actions only | **Verified absent** | Define allowed sources; do not invent codes |
| `verified_by` / `verified_at` | None | **Verified absent** | Required only for verified rows; define shape |
| `effective_at` | None | **Verified absent** | Define date vs datetime and timezone semantics |
| `created_at` / `updated_at` | Standard | **Verified compatible** | Revision policy still needed |

### 3.2 Gaps and conflicts

1. **No term calendar.** **Verified.** `AcademicYear` has no dates or terms
   (`be/compass/organization/models.py:23-40`). Good Moral's two-value semester is a form field, not an
   institutional calendar. A `term_code` model would encode an unverified policy.
2. **No enrollment source.** **Verified.** `CURRENT` is lifecycle, and the proposal explicitly says
   it is not enrollment (lines 313–327). No roster import exists. `UNKNOWN` must be the default;
   absence from a roster must not imply `NOT_ENROLLED` (proposal lines 329–335).
3. **No source of verified academic facts.** **Verified.** No current write path records a verifier
   or an authoritative source. The only potentially authoritative data is the organization catalog,
   which describes Programs, not a Student's participation.
4. **Inventory is not a period record.** **Verified.** Inventory is one row per Academic Year with a
   Program and Year Level, but it is Student-submitted and may be draft, corrected or deleted only
   through domain rules. It does not carry enrollment or verification and may disagree with the
   affiliation College. Copying it into a period record would launder unverified data into an
   academic history table.
5. **Uniqueness/revision policy is unresolved.** **Verified.** The proposal itself says a
   uniqueness and revision policy must account for transfers or corrections within the same term
   (lines 250–252). Current Inventory uniqueness `(student, academic_year)` does not answer whether
   a period is per term, per program change or per correction.
6. **Multiple Programs/degrees.** **Verified.** The proposal asks for a decision (line 848). The
   current model has one Program per Inventory per year and one Tracer response per Student per
   instrument version (`be/compass/graduate_tracer/models.py:417-423`). A period table could support multiple
   rows, but the source and rule do not exist.

## 4. `StudentGraduationRecord`

### 4.1 Field validation

| Proposed field | Current equivalent | Compatibility | Required decision / action |
|---|---|---|---|
| `student_id` | User | **Verified compatible** | Same role constraint |
| `graduated_college_id` | Tracer `graduated_college` nullable FK (`be/compass/graduate_tracer/models.py:259-265`) | **Partially compatible**, self-reported | Do not treat as official |
| `graduated_program_id` | Tracer `graduated_program` nullable FK (`:266-271`) | **Partially compatible**, service-checked only | Preserve provenance; do not infer |
| `graduation_date` | Tracer has only `graduation_year`; Good Moral graduate variant has a request-entered date (`be/compass/good_moral/services.py:857-920`) | **Verified absent as official date** | Cannot backfill; official date needs Registrar authority |
| `verification_source` | None | **Verified absent** | Define sources and evidence |
| `verified_by` / `verified_at` | None | **Verified absent** | Required for verified rows |
| `created_at` / `updated_at` | Standard | **Verified compatible** | — |

### 4.2 Gaps and conflicts

1. **Tracer is not a graduation record.** **Verified.** It is a self-reported survey; the Student FK
   is nullable, College/Program are nullable, and graduation year has no date or official source
   (`be/compass/graduate_tracer/models.py:240-273`). The proposal agrees it must not be treated as verified
   (lines 258–278 and migration phase 3).
2. **Good Moral is not a graduation record.** **Verified.** The Graduate variant captures degree
   text and a graduation date from the request, with no Registrar link
   (`be/compass/good_moral/services.py:857-920`). Multiple requests could disagree.
3. **Multiple degrees.** **Verified.** The proposed model notes the need to consider multiple
   completed degrees (lines 276–278), but current data has one Tracer response per instrument
   version and no degree-history table. The uniqueness/relationship model must be decided.
4. **Graduation Year derivation.** **Verified.** The proposal recommends deriving graduation year
   from the official date rather than storing it independently (lines 273–275). Current Tracer
   stores the year directly; a migration cannot reconstruct the date.

## 5. Capability and authorization validation

**Verified.** The proposed capabilities `student_academics.view_self`, `.view`, `.manage`,
`.verify`, `.import` do not exist (`be/compass/accounts/policy.py:608-760`). Existing roles do not
include a Registrar (`be/compass/accounts/policy.py:20-76`). `FACULTY` is capped at self-referral
capabilities (`:79-86`). `IT_ADMIN` receives `organization.manage` (`:617-626`).

**Inferred.** The proposal's authority split (“account-management authority does not inherently
grant authority to certify academic standing”, proposal lines 619–625) cannot be implemented by
reusing existing grants. It needs:

- A decided grant holder for `.verify` and `.manage` (possibly a designation, since no Registrar
  role exists).
- A scope rule for `.view`: current College, assigned students, historical periods, or another
  model. FAC-D10 leaves historical access/custody open
  (`docs/fac-5/institutional-decisions.md:132-145`).
- A decision on whether Students may see and request corrections (proposal decision 9).
- Review of the Faculty capability ceiling if any Faculty academic-contact feature is later
  approved; FAC-D9 currently forbids capturing an attestation.

## 6. Compatibility with proposal migration phases

**Verified.** Proposal phase 2 introduces the new models and canonical write path; phase 3 migrates
affiliations without classifying them as Registrar-verified and without inferring enrollment or
graduation (lines 653–672). That matches the evidence in this audit.

**Verified.** Phase 6 proposes removing live dependencies, retiring the old model/table, and
removing APIs/UI (lines 689–696). This is destructive and cannot be part of SAR-1. It requires a
separate cutover decision, backup, reconciliation and rollback plan.

**Inferred.** The proposal's “Existing Models to Retain” list (lines 280–295) matches current
domain ownership: `StudentInventory`, `GoodMoralRequest`, `GraduateTracerResponse` remain in their
domains. SAR should be an owner of placement/period/graduation facts, not a replacement for those
domain records.

## 7. Model validation conclusion

**Verified.** Only `StudentAcademicProfile` can be introduced safely against current data, and only
as an additive, current-state, College-only, unverified table. **Inferred.** Period and graduation
records require institutional decisions and an authoritative source before they can be modeled;
they should not be backfilled from Inventory, Good Moral or Tracer.
