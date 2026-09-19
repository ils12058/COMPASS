# ADR-048: Student Support Profile and Context

- Status: Accepted
- Date: 2026-09-19
- Scope: backend-only Student Support Profile storage and privacy-minimized counselor context

## Context

COMPASS uses the controlled Individual Inventory / F5 form
`CNSC-OP-GCO-01F5 Revision 0` as the authoritative annual Student Inventory source.

Some normalized facts used by Guidance reporting are direct structured interpretations of actual F5
content. Other useful support/profile facts are not present on the controlled F5 and must not be
represented as though they were official form fields.

This ADR establishes that boundary and adds a small privacy-minimized Student Support Context for
authorized Counselors.

## Source-fidelity boundary

Facts actually present on F5 remain on `StudentInventory` or its F5 child rows and may receive
canonical structured normalization.

Facts not present on F5 are stored separately in `StudentSupportProfile`.

A future frontend may render the official Inventory and supplemental support information on one page.
That does not make the supplemental data part of the controlled F5 revision.

Any future official F5 PDF or print representation must include only the approved controlled F5
projection. Supplemental Student Support Profile fields must not silently appear as F5 Rev. 0 fields.

## PWD canonicalization

The F5 contains a Physical Disadvantage response. GCO profiling practice uses this source dimension as
the PWD / Physical Disability reporting dimension.

The canonical structured field is therefore:

`StudentInventory.pwd_status`

with values:

- `PWD`
- `NON_PWD`
- `NOT_SPECIFIED`

The source narrative `physical_disadvantage` remains on the Inventory because the F5 itself contains
that descriptive answer.

`PWD` here is a canonical interpretation of the F5 Physical Disadvantage response. It does not claim
formal government PWD registration, PWD ID verification, diagnosis, severity, or accommodation need.

When `pwd_status = PWD`, a nonblank Physical Disadvantage description is required. `NON_PWD` and
`NOT_SPECIFIED` clear contradictory narrative detail.

Legacy migration is exact and non-inferential:

- `HAS_PHYSICAL_DISADVANTAGE -> PWD`
- `NONE -> NON_PWD`
- `NOT_SPECIFIED -> NOT_SPECIFIED`
- null remains null

Narrative text is never used to infer missing status.

## Supplemental annual profile

`StudentSupportProfile` is a one-to-one extension of `StudentInventory`.

It stores only:

- `four_ps_status`
- `indigenous_peoples_status`
- `mother_life_status`
- `father_life_status`

plus identity and timestamps required by the model.

Student and Academic Year are not duplicated because the owning Inventory already supplies them. The
profile is part of the same annual historical snapshot.

## 4Ps

`FourPsStatus` is explicit self-reported supplemental data:

- `BENEFICIARY`
- `NOT_BENEFICIARY`
- `NOT_SPECIFIED`

No household identifier, beneficiary number, payment information, proof upload, or inferred status is
stored.

Low income or a derived income band never implies 4Ps membership.

## Indigenous Peoples status

`IndigenousPeoplesStatus` is explicit self-reported supplemental data:

- `MEMBER`
- `NOT_MEMBER`
- `NOT_SPECIFIED`

No tribe/group text, genealogy, certificate number, proof upload, or ethnicity narrative is collected
in this foundation.

The status is never inferred from language, surname, address, religion, birthplace, municipality, or
appearance.

## Parent life status

Father/Mother Living/Deceased was previously stored on `InventoryFamilyMember.life_status` as a
digital profiling extension even though F5 does not explicitly ask those separate questions.

That field is removed from F5 family rows.

The values move to:

- `StudentSupportProfile.father_life_status`
- `StudentSupportProfile.mother_life_status`

with `LIVING`, `DECEASED`, and `NOT_SPECIFIED`.

Migration copies only existing Father/Mother life-status values. Missing values remain null. Spouse
rows do not receive parent life status. No parent name, occupation, address, or income is used to infer
life status.

All actual F5 family information remains on `InventoryFamilyMember`.

## Existing normalized facts are not duplicated

Solo Parent remains represented only by
`StudentInventory.civil_status_category == SOLO_PARENT`.

Parent low-income classification remains derived from canonical parent income status/amount.

OFW-related facts remain in existing parent/family categories.

No duplicate boolean support fields are introduced for these facts.

## Inventory API integration

The Student-owned Inventory workflow remains one intake flow.

Supplemental fields appear only under the nested object:

`support_profile`

The official F5 fields are not flattened together with supplemental fields.

Current and historical Inventory detail responses return the same nested support profile. Family rows
no longer expose parent life status. `physical_disadvantage_status` is replaced by the single
canonical `pwd_status` field.

Draft supplemental statuses may be null.

For prospective Inventory submission, the Student must explicitly provide:

- `pwd_status`
- `four_ps_status`
- `indigenous_peoples_status`
- `mother_life_status`
- `father_life_status`

`NOT_SPECIFIED` is an allowed deliberate response. Missing values are never silently converted to
`NOT_SPECIFIED`.

Existing submitted historical records remain readable and valid when migrated supplemental values are
null.

Root Inventory data, child rows, and Student Support Profile update in the same authoritative Inventory
transaction. Submission remains one transaction and one operation.

Once the owning Inventory is submitted, the Student Support Profile has no separate mutation endpoint.

## Student Support Context

The read-only endpoint is:

`GET /api/v1/student-support/students/{student_id}/context`

with operation ID `studentSupportGetContext`.

It is not a raw Inventory or raw Student Support Profile endpoint.

The response is limited to:

- Student UUID and display name
- current Academic Year UUID and label
- Inventory source status: `MISSING`, `DRAFT`, or `SUBMITTED`
- availability flag
- closed indicator codes and labels

No support-profile object, F5 payload, narrative, exact income, address, religion, family names,
counseling concerns, fears, medical history, or referral reasons are exposed.

## Capability and scope

The capability is:

`student_support.view`

Default grant is only the `COUNSELOR` role.

It is not granted by default to Student, Guidance Services Staff, IT Admin, Institutional Officer, or
DPO.

Capability and resource scope are independent checks. A non-Counselor does not gain operational access
merely because of an unusual capability override.

Head Guidance Counselor may resolve support context institution-wide because Head is a Counselor
designation.

An ordinary Counselor may resolve a Student only when the Student's current `StudentAffiliation`
belongs to an active College/Campus for which that Counselor holds
`CounselorResponsibility`.

Out-of-scope resources use concealment/not-found semantics. Inactive organization state never broadens
scope.

This support-context authority does not expand Counseling-note access.

## Current-year and submission source

Student Support Context resolves the canonical current Academic Year once.

It never falls back to historical Inventory data.

Only a current `SUBMITTED` Inventory may produce positive support indicators.

A current `MISSING` or `DRAFT` Inventory returns no positive indicators. Draft answers are not
projected as authoritative Counselor-facing facts.

## Closed indicator catalog

Initial positive indicators are:

- `PWD`
- `SOLO_PARENT`
- `FOUR_PS_BENEFICIARY`
- `INDIGENOUS_PEOPLES_MEMBER`
- `MOTHER_DECEASED`
- `FATHER_DECEASED`

The ordering is code-owned and deterministic.

Negative or unknown source states do not create opposite-state badges. Absence of a badge is not proof
of the opposite fact.

## No scoring or inference

Student Support Context exposes factual support context only.

COMPASS does not calculate a risk score, vulnerability score, support score, priority score, high-risk
or low-risk classification, automatic counseling need, intervention requirement, disability severity,
academic-performance inference, or recommendation from these indicators.

No AI/NLP classifier or generic dynamic indicator engine is introduced.

## Counseling, Routine Interview, and Referral boundaries

Support indicators are not copied into Counseling Encounter records, Counseling notes, Routine
Interview Intake/Evaluation, or Referral responses.

Future authorized interfaces may request the context endpoint alongside those views. No duplicated
snapshot is persisted.

Guidance Services Staff participation in Referral workflows does not automatically grant access to the
more sensitive support context.

## Student Profiling report

The existing aggregate-only Student Profiling report now reads:

- PWD distribution from `StudentInventory.pwd_status`
- Mother Life Status from `StudentSupportProfile.mother_life_status`
- Father Life Status from `StudentSupportProfile.father_life_status`

The physical-disability presentation is labeled `PWD Status`.

Program columns, denominators, privacy boundaries, PDF/XLSX behavior, and all unrelated report
sections remain unchanged.

4Ps and Indigenous Peoples sections are not added to the formal Student Profiling report in this
slice.

## Audit boundary

Existing Inventory create/submit Audit Trail behavior remains authoritative.

Generic Inventory AuditEvent metadata does not store PWD status/detail, 4Ps status, Indigenous Peoples
status, or parent life status.

No duplicate Student Support audit table is introduced.

Normal Student Support Context reads are not comprehensively read-audited in this slice.

## Explicitly deferred

This ADR does not introduce:

- support or vulnerability dashboards
- bulk lists or cohort analytics
- risk/vulnerability scoring
- AI classification or automatic intervention recommendations
- 4Ps inference from income
- IP inference
- formal PWD registration verification
- PWD/IP/4Ps proof uploads
- generic configurable indicator taxonomies
- support-triggered notifications or Counselor alerts
- F5 PDF/print
- frontend UI

These require separate stakeholder and privacy decisions.
