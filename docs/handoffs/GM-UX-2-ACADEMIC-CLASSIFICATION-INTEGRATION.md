# GM-UX-2 — Academic Classification Integration Handoff

**Dependency:** COMPASS-ACAD-1 Program metadata and Inventory enforcement
**Boundary:** Identify integration points for a later slice; no Good Moral eligibility or workflow
change is included in ACAD-1.

**GM-UX-2 implementation status (2026-10-18):** The integration described below is implemented.
The F4 rule now uses the linked current submitted Inventory's canonical Program classification and
stored Year Level. New F4 is limited to Bachelor's Programs with supported 1st–4th Year values.
F6 request intake is available across recorded Student lifecycle states because lifecycle is not
degree evidence. It remains a Student-reported claim; COMPASS has no authoritative completed-degree
source or documented GCO verification procedure. The [implementation report](../../outputs/COMPASS-GM-UX-2-IMPLEMENTATION-REPORT.md)
records the evidence audit, regression scenarios, and proposed minimal manual verification before
issuance.

## Classification source

Use the code-owned Organization Program catalog and its `ProgramSummary` metadata:

- `academic_classification`: `BACHELORS`, `MASTERS`, or `DOCTORAL` for exact canonical Program
  identities;
- `year_level_policy_status`: `CONFIGURED` or `PENDING_POLICY`;
- `applicable_year_levels`: the configured list, or `null` while policy is pending.

The current supported Bachelor's choices are 1st–4th Year. Master's and Doctoral Program limits
are not configured. `Master in Information Technology` is a Master's Program under CCMS, so no
Graduate School assumption is valid. Program classification must not be inferred from College,
name prefix, Student lifecycle, or free-text degree.

## F4 current-student request paths

### Student self-service

- API: `POST /api/v1/good-moral/me/requests/current-student`
  (`goodMoralCreateMyCurrentStudentRequest`).
- Frontend: `CurrentStudentRequestForm` in
  `fe/src/features/good-moral/good-moral-request-page.tsx`.
- Current input: the form displays a read-only Year Level derived from the submitted Inventory and
  collects the Semester. A legacy optional `year_level` payload is accepted only when it matches
  the Inventory-derived value.
- Backend: `create_my_current_student` calls `_create_current_student`, which requires a current
  Student and the current year's submitted Inventory, validates its canonical Program as
  Bachelor's and its stored Year Level as supported 1–4, then stores that Inventory foreign key
  and Inventory-derived snapshot.

The backend checks the queryable Program and Year Level fields and does not retrieve or decrypt
unrelated confidential Inventory content. If the linked Program is postgraduate, unclassified, or
the recorded Year Level is unsupported, the F4 request is blocked with an actionable response.

### Counselor/GSS-assisted creation

- API: `POST /api/v1/good-moral/requests/current-student`
  (`goodMoralCreateAssistedCurrentStudentRequest`).
- Frontend: the `CURRENT_STUDENT` path in
  `fe/src/features/good-moral/good-moral-assisted-request-page.tsx`.
- Backend: `create_assisted_request` dispatches to the same `_create_current_student` service.

The shared service applies the same F4 rule to student and assisted requests. The office-wide
selector exposes a minimal F4 eligibility summary from the same Inventory facts; it does not return
private Inventory answers or treat Student lifecycle as academic classification.

### F4 correction before issuance

- API: `PATCH /api/v1/good-moral/requests/{request_id}` (`goodMoralUpdateRequest`).
- Frontend: the `CURRENT_STUDENT` branch of
  `fe/src/features/good-moral/good-moral-correction-form.tsx`.
- Backend: `update_request` allows a pre-issuance `year_level_snapshot` correction and currently
  validates the separate canonical F4 1st–10th list only when that field changes. The F4 request
  retains its Inventory foreign key.

When a correction changes Year Level, it must agree with the request's linked submitted Inventory
and canonical Bachelor's policy. Untouched legacy snapshots, issued/cancelled records, historical
certificate content, and Student history access remain preserved.

## F6 graduate request paths

### Student self-service and assisted creation

- Student API: `POST /api/v1/good-moral/me/requests/graduate`
  (`goodMoralCreateMyGraduateRequest`).
- Assisted API: `POST /api/v1/good-moral/requests/graduate`
  (`goodMoralCreateAssistedGraduateRequest`).
- Frontend: the `GRADUATE` branch of the self-service and assisted request pages.
- Backend: `_create_graduate` requires an active Student with a recorded lifecycle value
  (`CURRENT`, `GRADUATED`, or `FORMER`); the submitted `degree` and `major` remain free text. The
  graduate request has no Inventory relation.

The approved Good Moral scope is for undergraduate current students and undergraduate graduates;
there is no approved postgraduate Good Moral form in current GCO scope. No lifecycle value proves
an undergraduate degree, and free-text degree does not prove degree classification. Later UCN or
external postgraduate status must not remove access to submit an F6 request for a previously
completed UCN Bachelor's degree. Conversely, postgraduate enrollment at UCN does not establish
that a UCN undergraduate degree was completed. Current COMPASS data cannot automatically resolve
either claim.

### F6 correction before issuance

- API: `PATCH /api/v1/good-moral/requests/{request_id}`.
- Backend: the graduate correction field is `degree_snapshot`; it remains free text and does not
  establish classification.

If a later approved evidence source is introduced, separately define how it relates to new F6
requests and pre-issuance corrections. Do not rewrite historical graduate snapshots or restrict
access to prior issued records.

## Evidence limitation and proposed GCO procedure

The audit found no Registrar/SIS completion feed, verified undergraduate degree model, or documented
GCO qualification-verification procedure. Graduate Tracer fields `graduated_college`,
`graduated_program`, and `graduation_year` are self-reported and explicitly do not represent
Registrar-verified credentials (`be/compass/reports/graduate_tracer.py`). F6 suggestions come from
the current Program catalog and free-text historical degree names; neither proves graduation.

Until UCN approves a source and records policy, COMPASS labels F6 degree/date as Student-reported
and leaves a submitted request in `REQUESTED`; lifecycle, current Program, Inventory, affiliation,
and degree text do not become proof. The minimal proposed GCO procedure is to check the claimed
UCN degree and completion date against an approved official Registrar source before issuance, then
record reviewer, date, source, and outcome on the request. This proposed manual check is not
currently enforced or auditable in COMPASS. GCO must approve the evidence source and procedure
before a future verification field or issuance gate is added. No academic-history subsystem or
external institution enrollment tracking is introduced by GM-UX-2.
