# GM-UX-2 — Academic Classification Integration Handoff

**Dependency:** COMPASS-ACAD-1 Program metadata and Inventory enforcement
**Boundary:** Identify integration points for a later slice; no Good Moral eligibility or workflow
change is included in ACAD-1.

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
- Current input: a manually selected Year Level from the separate 1st–10th F4 list, plus semester.
- Backend: `create_my_current_student` calls `_create_current_student`, which requires a current
  Student and the current year's submitted Inventory, then stores that Inventory foreign key and
  snapshots the user-selected Year Level as text.

The Inventory link already gives this path a canonical Program identity and stored numeric Year
Level. Today, creation does not require the selected F4 Year Level to match either value or check
that the linked Program is Bachelor's. A follow-up should decide and implement the approved
relationship using the linked Inventory record. It should use the queryable Program and Year Level
fields rather than retrieving or decrypting unrelated confidential Inventory content.

### Counselor/GSS-assisted creation

- API: `POST /api/v1/good-moral/requests/current-student`
  (`goodMoralCreateAssistedCurrentStudentRequest`).
- Frontend: the `CURRENT_STUDENT` path in
  `fe/src/features/good-moral/good-moral-assisted-request-page.tsx`.
- Backend: `create_assisted_request` dispatches to the same `_create_current_student` service.

Apply any approved F4 Program and Year Level rule in the shared service so student and assisted
requests cannot diverge. The existing office-wide student selector distinguishes only CURRENT and
GRADUATED lifecycle; it does not establish academic degree classification.

### F4 correction before issuance

- API: `PATCH /api/v1/good-moral/requests/{request_id}` (`goodMoralUpdateRequest`).
- Frontend: the `CURRENT_STUDENT` branch of
  `fe/src/features/good-moral/good-moral-correction-form.tsx`.
- Backend: `update_request` allows a pre-issuance `year_level_snapshot` correction and currently
  validates the separate canonical F4 1st–10th list only when that field changes. The F4 request
  retains its Inventory foreign key.

For GM-UX-2, define whether corrections must agree with the request's linked Inventory Program and
Year Level. Apply the rule only when a correction explicitly changes the relevant value. Preserve
untouched legacy snapshots, issued/cancelled records, historical certificate content, and student
history access.

## F6 graduate request paths

### Student self-service and assisted creation

- Student API: `POST /api/v1/good-moral/me/requests/graduate`
  (`goodMoralCreateMyGraduateRequest`).
- Assisted API: `POST /api/v1/good-moral/requests/graduate`
  (`goodMoralCreateAssistedGraduateRequest`).
- Frontend: the `GRADUATE` branch of the self-service and assisted request pages.
- Backend: `_create_graduate` requires `student_lifecycle_status == GRADUATED`; the submitted
  `degree` and `major` are free text. The graduate request has no Inventory relation.

The approved Good Moral scope is for undergraduate current students and undergraduate graduates;
there is no approved postgraduate Good Moral form in current GCO scope. `GRADUATED` status does not
prove an undergraduate degree, and free-text degree does not prove degree classification. GM-UX-2
must identify an institutionally authoritative proof or verification process before adding a
Bachelor's-only F6 eligibility gate. Do not infer from text or expand ACAD-1 into an SIS/Registrar
subsystem.

### F6 correction before issuance

- API: `PATCH /api/v1/good-moral/requests/{request_id}`.
- Backend: the graduate correction field is `degree_snapshot`; it remains free text and does not
  establish classification.

If a later approved evidence source is introduced, separately define how it relates to new F6
requests and pre-issuance corrections. Do not rewrite historical graduate snapshots or restrict
access to prior issued records.

## Institutional decisions for GM-UX-2

1. Confirm Bachelor's-only F4 eligibility for current students, including how a linked Program that
   is inactive or has pending classification is handled.
2. Confirm whether F4's Year Level must equal the submitted Inventory's stored Year Level, whether
   the F4 form may record a different value, and what to do when the two disagree.
3. Confirm how F4 correction should use the immutable source Inventory and how to preserve old
   snapshots when current catalog metadata later changes.
4. Identify authoritative undergraduate-degree evidence for F6 and how GCO verifies it when the
   COMPASS account is merely marked `GRADUATED`.
5. Confirm that postgraduate applicants remain outside current Good Moral form scope until an
   approved form and policy exist.
