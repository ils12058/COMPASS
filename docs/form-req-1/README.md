# FORM-REQ-1 — Individual Inventory required fields follow the official F5 form

**Status:** Implemented on `integration/ux15-modernization`; not deployed.
**Updated:** 2026-11-09.
**Official form:** CNSC-OP-GCO-01F5, Individual Inventory, Revision 0.

The Student Individual Inventory requires the answers requested by the official F5 form when the
Student submits it. Drafts keep their looser validation so a Student can save incomplete work.

## 1. Canonical answer model

- "Prefer not to specify" is not an Inventory or Student Support choice.
- Truthful uncertainty uses the field-specific choices `NOT_SURE` or `UNKNOWN` where available.
- Parent status is the F5 checklist `parent_statuses`. It is multi-select; there is no separate
  single-choice parent-status category.
- Current location requires a real PSGC region and city or municipality.
- Permanent location is optional. When it is unanswered, its location row is omitted.
- Parent-income reporting distinguishes Reported, None, and Unknown. Derived report buckets use
  Unknown for an income that cannot be calculated.
- No compatibility aliases are accepted. Staging is reset before Evaluation.

## 2. Required at submission

The rules are implemented in `be/compass/inventory/services.py` and mirrored by
`fe/src/features/inventory/inventory-payload.ts`.

### Page 1 — Personal data

| F5 section | Required answers |
| --- | --- |
| Personal data | Full name, nickname, student number, date and place of birth, nationality, sex, birth order among siblings, civil status, current and permanent addresses, contact number, email address, languages spoken at home and most fluent in, religion from birth, and current religion. Other civil-status and religion details are required when Other is selected. |
| Location details | Current PSGC region and city or municipality. Permanent PSGC location remains optional. |

### Page 1 — Family and student support

| F5 section | Required answers |
| --- | --- |
| Family data | For each living parent: name, date and place of birth, current and permanent addresses, contact number, email address, educational attainment, occupation, annual-income status, business address and telephone, languages spoken, religion raised with, and current religion. Occupation detail is required for Other; an amount greater than zero is required for Reported income. Spouse details are required only when the Student is married. A deceased parent or a parent whose life status is Unknown is exempt from these detail requirements. |
| Parent status | At least one F5 parent-status checklist item. More than one item may be selected. |
| Guardian and emergency contact | Guardian name, relationship, address, and contact number; emergency-contact name and number. |
| Student support information | 4Ps status, Indigenous Peoples status, and mother and father life status. |

### Page 2 — Siblings, background, living, and health

| F5 section | Required answers |
| --- | --- |
| Siblings | At least one row and one row marked "This is me"; every row needs name, sex, and age. |
| Personal background and unique features | Friends in and outside school, special interest, special skills and talents, hobbies and recreation, ambition or goal, and characteristics. |
| Living conditions | Living arrangement, people in the present living place, and people sharing the room. Boarding-house residents also answer room exclusivity, landlord or landlady name, and boarding-house address. |
| Health conditions | Accidents, operations, height, weight, physical disadvantage, PWD status, illness this year, and previous illness. Accident or operation effects are required only when the experience is not "None". Immunizations are optional, with detail required when Other is selected. |

### Page 2 — Educational background and current study

| F5 section | Required answers |
| --- | --- |
| Educational background | Elementary, Junior High, and Senior High rows with school and address plus inclusive years. Preparatory, technical or vocational, and collegiate rows remain optional. |
| Current study | Active Program, Year Level, and satisfaction with the present schedule. An unsatisfied schedule requires a reason. Major remains optional. |

### Page 3 — Course choice, interests, perceptions, and plans

| F5 section | Required answers |
| --- | --- |
| Course choice and educational perception | First-choice answer, at least one course-choice reason, Other detail when selected, lowest and highest subjects with grades, and the three inclination answers. |
| Interests and daily routine | Other skills and hobbies, desired extracurricular activities, reading preferences, handedness, and all six daily-hours fields. The interests checkbox list is optional. |
| Plans after graduation | Ideal monthly allowance and intended work field, with detail for Other. |
| Prior counseling experience | The yes or no answer; counselor name, when, and where only after Yes. |
| Current concerns and fears | Current concerns and current fears. |
| Organizations and transportation | Organization memberships are optional. Every selected transportation mode requires its frequency; fare is optional. |

## 3. Correction behavior

A reopened correction is judged only on the answers named by its correction targets.
`_correction_required_keys` filters backend requirements, and
`inventoryCorrectionIssueAllowed` mirrors that behavior in the frontend. A reason-only correction
with no targets keeps the established behavior and does not introduce unrelated blockers.

## 4. Reports

- Parent status counts every selected checklist item. Because a Student may tick more than one,
  parent-status totals can exceed the Student population. PDF and XLSX reports state this.
- Program, college, campus, and current-location dimensions are required for submitted Inventory
  report rows. Missing structured data is a configuration conflict, not a legacy bucket.
- `HISTORICAL_LIMITED` remains the explicit historical-coverage state.
- Unknown derived income remains an explicit Unknown bucket.

## 5. PSGC behavior

The PSGC integration consumes the canonical `code` field from reference results. Submission
returns `503 psgc_reference_unavailable` if the reference service cannot validate the current
location. The draft remains saved and the frontend asks the Student to try submitting later.

## 6. What stays optional

| Optional | Reason |
| --- | --- |
| Permanent PSGC location | FORM-ADDR-1 is deferred; omission represents no permanent location answer. |
| Preparatory, technical or vocational, and collegiate education rows | Not every Student attended them. |
| Major | Not every Program has one. |
| Organization memberships | The F5 lists them but does not require an entry. |
| Transportation entries and each fare | A Student may use none of the listed modes; a selected mode still requires a frequency. |
| Interests checkbox list | Narrative interest answers carry the requirement. |
| Immunizations | The F5 does not require a selection. |
| Parent details when life status is Deceased or Unknown | These details may not be truthfully available. |
| Spouse details unless civil status is Married | The F5 asks for them only for a married Student. |
| Accident or operation effects after a "None" answer | There is no effect to describe. |
| Schedule reason when satisfied | The F5 asks for a reason only when not satisfied. |
| Prior-counseling details after No | The F5 asks for them only after Yes. |

## 7. Scope and security

Permissions, encryption, and confidential-content handling remain unchanged. The change does not
introduce a new `FormRevision` or alter the official document template layout. OpenAPI and the
frontend client are generated from the canonical backend contract.
