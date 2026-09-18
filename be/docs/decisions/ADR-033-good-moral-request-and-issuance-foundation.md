# ADR-033: Good Moral request, issuance, and PDF foundation

## Status

Accepted for the Good Moral foundation.

## Context

COMPASS needs a small source-faithful workflow for the Guidance and Counseling Office's two
confirmed Good Moral Character controlled forms:

- `CNSC-OP-GCO-01F4`, Revision `0` — Current Student Good Moral Character
- `CNSC-OP-GCO-01F6`, Revision `0` — Graduate Good Moral Character

The supplied F4 and F6 PDFs were inspected as the source authority for certificate wording and
visible fields. F4 certifies a current Student and includes year level, College, course/program
text, major, semester, Academic Year, Guidance Counselor signature, and the official-receipt
block. F6 certifies a graduate and includes degree, major, graduation date, Guidance Counselor
signature, and the same receipt block. Physical underline/wrapping regions are presentation
details and do not create Department, Program, enrollment, Registrar, or other domain models.

Student lifecycle already distinguishes `CURRENT`, `GRADUATED`, and `FORMER` while retaining
`STUDENT` as the canonical primary role. Individual Inventory already provides the canonical
current submitted Inventory prerequisite and its bound Academic Year. Institutional Forms owns
QMS FormFamily/FormRevision identity, while the Documents foundation separately owns code-based
presentation templates and current institutional branding.

## Decision

### One request aggregate and two explicit variants

Add one `GoodMoralRequest` aggregate with exactly two variants:

- `CURRENT_STUDENT`
- `GRADUATE`

and the deliberately small lifecycle:

- `REQUESTED`
- `ISSUED`

A Student may create multiple Good Moral requests. No Student/year or Student/variant uniqueness
constraint and no COMPASS human certificate/reference number are introduced.

The same existing `STUDENT` account and User UUID owns every request. No `ALUMNI` role, second
graduate account, AlumniProfile, or Counselor-created graduate intake is introduced.

### Lifecycle eligibility and historical ownership

Initiation is server-selected by purpose-built endpoints rather than a client-supplied variant:

- `CURRENT` may initiate only F4.
- `GRADUATED` may initiate only F6.
- `FORMER` may initiate neither.

`FORMER` is not interpreted as `GRADUATED`.

Lifecycle controls future initiation eligibility. It does not rewrite existing request ownership,
variant, provenance, or snapshots. Active Student accounts retain owner-only historical list,
detail, and issued-PDF access across CURRENT/GRADUATED/FORMER transitions.

### F4 creation and exact Inventory provenance

F4 creation runs transactionally and locks the Student User row before lifecycle evaluation and
snapshot composition. After confirming `CURRENT`, it calls the existing
`require_current_submitted_inventory(locked_student)` exactly once.

The exact returned `StudentInventory` is saved as request provenance and
`request.academic_year` is assigned from `inventory.academic_year`. Good Moral does not perform
a second independent current-Academic-Year resolution.

F4 initially snapshots:

- current Accounts profile full name,
- current StudentAffiliation College name,
- Inventory course,
- Inventory major,
- Student-supplied bounded nonblank year-level text,
- Student-supplied bounded nonblank semester text.

Semester remains normalized bounded text because the supplied F4 source does not establish a
closed institution-wide term enumeration. No AcademicTerm/Semester domain is introduced.

Missing/incomplete current Inventory and missing active Student affiliation are translated to
controlled Good Moral conflicts. Good Moral does not mutate Inventory or Organization data.

### F6 creation

F6 creation also runs transactionally and locks the Student User row before lifecycle evaluation.
It requires `GRADUATED`, snapshots the current profile full name, and stores certificate-local
degree, major, and graduation-date facts supplied by the same Student account.

F6 deliberately does not resolve or require current Inventory, Academic Year, StudentAffiliation,
College, Appointment, Service Catalog, Registrar, SIS, or enrollment history. GRADUATED lifecycle
establishes workflow eligibility only; it does not manufacture verified degree/major/date facts.

### Pre-issuance correction

Authorized Counselors may correct only REQUESTED certificate-local fields and receipt fields.
Variant, Student ownership, F4 Inventory provenance, and F4 Academic Year provenance are immutable.
Corrections never write back to User/Profile, Inventory, StudentAffiliation, College, or lifecycle.

Receipt number, date, and amount are modeled because both source forms visibly contain that block.
They remain optional unless later institutional evidence establishes otherwise. No Payment, Fee,
Cashier, billing, payment-gateway, or receipt-verification subsystem is introduced.

### Issuance authority and concurrency

Counselors receive narrow scope-free `good_moral.view`, `good_moral.manage`, and
`good_moral.issue` capabilities. Students receive only self-view/request capabilities. Guidance
Services Staff, IT Admin, and DPO receive no Good Moral content authority by default. Head Guidance
requires no duplicate designation grant because the Head already operates with the canonical
Counselor primary role.

Issuance requires recent MFA, locks the request row, and is idempotent after successful issuance.
For F4, issuance additionally locks the Student User row and re-checks that the Student is still
`CURRENT`, because F4 makes a present-status assertion. Failure preserves the REQUESTED record;
it never converts F4 to F6 or refreshes Inventory, Academic Year, or snapshots.

At successful issuance COMPASS freezes:

- `issued_at` from server time,
- `issued_by`,
- `issued_by_name_snapshot`,
- exact QMS `form_revision`,
- exact `document_template_key`,
- exact `document_template_version`.

Issued certificate and receipt facts are immutable in this slice. Void, revocation, corrected
issuance, and reissue workflows are deferred.

### Canonical mandatory supported-FormRevision boundary

Institutional Forms now exposes:

`require_active_supported_form_revision(family_key)`

with mandatory-consumer semantics:

active revision exists
+ internal schema version is supported by this COMPASS build
→ return that exact FormRevision

No active revision or unsupported active revision
→ `InstitutionalFormConflict`

`get_active_supported_form_revision()` remains for genuinely optional consumers.

As a surgical consistency retrofit in this same branch:

- Individual Inventory uses `require_active_supported_form_revision()` underneath its existing
  Inventory configuration-error translation.
- Referral uses the canonical required helper underneath its existing Referral configuration
  adapter.
- Call Slip uses the canonical required helper underneath its existing Call Slip configuration
  adapter.
- Routine Interview is intentionally unchanged and remains an optional-revision consumer using
  `get_active_supported_form_revision()`.
- Good Moral issuance uses the required helper for the family selected from the saved variant and
  translates Institutional Forms failures into a controlled Good Moral configuration conflict.

No generic requirement engine, resolver hierarchy, or broader Institutional Forms redesign is
introduced.

### Controlled form identity

Institutional Forms owns bootstrap of two confirmed families/revisions:

- `good_moral_current_student`
  - official code `CNSC-OP-GCO-01F4`
  - official revision `"0"`
  - internal schema version `1`
  - initially ACTIVE
- `good_moral_graduate`
  - official code `CNSC-OP-GCO-01F6`
  - official revision `"0"`
  - internal schema version `1`
  - initially ACTIVE

Both schema version 1 values are listed in `SUPPORTED_SCHEMA_VERSIONS`.

FormRevision is intentionally not bound at request creation. It is resolved as active + supported
and frozen only at successful issuance. A later active revision does not rewrite an already issued
request. Historical CNSC controlled codes are not rewritten to fabricated UCN codes.

### QMS provenance and presentation provenance are separate

Good Moral freezes two deliberately separate provenance concepts:

- `FormRevision` = official QMS/control identity used at issuance.
- `document_template_key + document_template_version` = exact COMPASS presentation implementation
  used at issuance.

Both template values are null while REQUESTED and structurally required once ISSUED. PDF rendering
of an issued request uses the saved key/version, never a fresh variant-to-latest mapping. If that
saved presentation version is unavailable to the running build, rendering fails closed with a
controlled document/configuration failure instead of silently switching versions.

This presentation provenance is not generated-PDF persistence.

### Database constraints

Database checks remain structural:

- F4 structurally requires Inventory + AcademicYear and has no graduate-only degree/date shape.
- F6 structurally has no Inventory/AcademicYear and has no current-student-only field shape.
- REQUESTED structurally has no issuance/QMS/template provenance.
- ISSUED structurally requires issued time, issuer, issuer-name snapshot, FormRevision, and template
  key/version.

Printable completeness such as meaningful F4 course/year/College/semester or F6 degree/date is
validated by the issuance service, not by over-broad database constraints, so REQUESTED records may
remain correctable.

### PDF rendering

Good Moral reuses the existing Documents renderer, current `DocumentBrandingProfile`, local
packaged assets, Django templates, Playwright/Chromium, and remote HTTP/HTTPS blocking.

Two versioned CERTIFICATE template specs are code-owned:

- `good_moral_current_student` version 1
- `good_moral_graduate` version 1

Both use `show_page_numbers=False`. Their templates render their own source-controlled footer with
the saved official code, saved official revision, and source-faithful `Page 1 of 1`, avoiding the
generic Chromium page footer.

Issued PDFs use only saved GoodMoralRequest certificate facts, saved issuance time, saved issuer
name, saved FormRevision, and saved template key/version. They do not refresh Profile, Inventory,
Academic Year, StudentAffiliation, College, lifecycle, or currently active FormRevision.

Current institution/office branding still comes from the shared current
`DocumentBrandingProfile`, consistent with ADR-029. On-demand rendering therefore does not claim
pixel-identical archival output after future branding changes. No GeneratedDocument, PDF database
storage, MinIO/S3 certificate archive, or other PDF persistence is added.

### Audit and privacy

Add privacy-safe actions for request creation, pre-issuance correction, and issuance. Audit metadata
is limited to stable operational values such as variant, transition, changed field names, controlled
form identity, and template provenance. Applicant/certificate/receipt values and PDF bytes are not
copied to Audit metadata.

Good Moral is not added to My Activity or Security Activity in this slice.

### API and scope boundaries

Student endpoints provide purpose-built F4/F6 initiation plus owner-only history/PDF reads.
Counselor endpoints provide an office-wide operational queue, detail, REQUESTED-only correction,
issuance, and issued PDF download. No College-based Good Moral processing scope is invented.

This foundation does not change Service Catalog, Appointment, Availability, Counseling, Exit
Interview, Referral workflow semantics, Call Slip workflow semantics, or Routine Interview workflow
semantics beyond the narrow shared FormRevision resolver consistency described above.

It introduces no Exit Interview prerequisite, Graduate Tracer, Registrar/SIS/enrollment subsystem,
ALUMNI role, payment/billing/cashier system, generic certificate/workflow/approval engine,
notifications, QR verification, digital signatures, or PDF archive.

## Consequences

CURRENT Students can request source-faithful F4 certificates using the exact current submitted
Inventory provenance; GRADUATED Students can request source-faithful F6 certificates using the same
Student account without current-student prerequisites; FORMER Students cannot initiate either but
retain historical ownership.

Counselors can correct REQUESTED certificate-local facts and issue controlled certificates with
recent MFA. Issued records preserve both official QMS identity and the exact COMPASS presentation
key/version used at issuance while continuing to use shared current branding for on-demand renders.

The Institutional Forms required-resolution contract is now consistent for Inventory, Referral,
Call Slip, and Good Moral, while Routine Interview deliberately remains optional.
