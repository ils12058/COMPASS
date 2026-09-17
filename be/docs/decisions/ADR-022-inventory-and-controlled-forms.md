# ADR-022: Controlled form identity and annual Individual Inventory

## Context

COMPASS needs the Student Individual Inventory before later Routine Interview and other
inventory-dependent service workflows. The Inventory is both an annual Guidance profile and an
institutional controlled form. Those concerns are related but not the same: domain code owns the
explicit fields and workflow, while institutional document governance owns official controlled-form
identity.

The supplied rendered three-page source document was inspected directly. It identifies the form as
`INDIVIDUAL INVENTORY`, controlled-document code `CNSC-OP-GCO-01F5`, Revision `0`. The source
layout also confirms the personal/family table, sibling/living/health/education sections, and the
course-interest/organization/transport/perception sections represented by this implementation.
Legacy CNSC branding and controlled-document identity are not rewritten merely because the
institution is now UCN.

## Decision

### Institutional document authority

UCN Quality Management System (QMS), not COMPASS, issues and approves official controlled-document
codes and revisions. COMPASS records QMS-approved metadata and selects which compatible approved
revision is active for new GCO records. The words `register revision` in the API mean record an
already issued/approved QMS revision; they do not mean issue, increment, approve, or generate an
official institutional revision.

A minimal `compass.institutional_forms` domain owns only `FormFamily` and `FormRevision`. Revision
identity (`family`, `official_code`, `official_revision`, `internal_schema_version`) is append-only;
there is no generic PATCH. Activation/deactivation is separate operational state. At most one
revision is active per family, activation retires the previously active revision transactionally,
and historical records or existing drafts retain their original revision FK.

The initial migration registers only:

- family key `individual_inventory`, title `Individual Inventory`
- official code `CNSC-OP-GCO-01F5`
- official revision `0`
- internal schema version `1`
- active status

Future QMS revisions do not require a dynamic form engine. A code-level compatibility map declares
which internal schema versions the running backend understands; currently
`individual_inventory -> {1}`. An unsupported registered revision cannot be activated. If a future
QMS revision changes form meaning or fields, explicit domain code/schema/migrations must be deployed
before that revision can become active.

Head Guidance Counselor receives explicit `institutional_forms.view` and
`institutional_forms.manage` designation capabilities. Registration and activation/deactivation
require recent MFA. IT Admin has no magic form-governance bypass. Audit records only safe revision
metadata through `institutional_form.revision_registered`,
`institutional_form.revision_activated`, and `institutional_form.revision_deactivated`.

### Academic Year operational configuration

A minimal `organization.AcademicYear` stores UUID, unique label, `is_current`, and timestamps. There
are no semester, term, enrollment, school-calendar, or guessed date boundaries. A PostgreSQL partial
unique constraint and transactional service guarantee at most one current Academic Year.

Academic Year is normal business/institutional configuration, not deployment-only configuration.
The narrow API lists years, creates a year, and sets one current. Head Guidance Counselor receives
explicit `academic_years.view` and `academic_years.manage`; ordinary Counselor receives view only.
Mutations require recent MFA. IT Admin, Student, GSS, and DPO do not receive manage authority by
default. Changing the current year does not move or rewrite any historical Inventory. Audit records
only safe year labels through `academic_year.created` and `academic_year.current_changed`.

### Annual Individual Inventory

`compass.inventory` owns an explicit typed `StudentInventory` plus child tables for repeated source
rows: family members, siblings, education entries, organization memberships, and transportation
entries. Fixed source checkbox groups use typed PostgreSQL arrays backed by closed enums. The model
is deliberately not `GenericForm`/`Question`/`Answer`/JSON-schema storage.

Each Student has at most one Inventory per Academic Year. A new Inventory snapshots the active
`individual_inventory` FormRevision and never re-resolves it on read. If the active FormRevision
changes while a draft exists, the existing draft keeps its original revision; only a newly created
annual Inventory uses the newly active revision.

The annual form snapshots the values written on that year's controlled document rather than
rendering history from mutable Account/Organization data. Student number, course/major and other
form values therefore live explicitly in the Inventory. Student age is not redundantly stored; date
of birth is stored instead. The Student FK remains the canonical person relationship.

Student self-service receives only `inventory.view_self` and `inventory.manage_self`. No Counselor,
Head, GSS, DPO, or IT Admin Inventory-content endpoint is introduced in this slice because the
resource/time assignment rule for such highly sensitive baseline data is not sufficiently grounded.
Submitted records are locked; there is no delete or administrative reopen workflow yet.

Draft editing uses full atomic replacement (`PUT /inventory/me/current`): scalar values and repeated
child collections are saved in one transaction under a row lock. Submission also locks the bare
Inventory row. `SUBMITTED` means the Student deliberately submitted a structurally valid record;
COMPASS does not invent a percentage-completeness policy. Only confirmed conditional semantics are
enforced, such as OTHER selections requiring specification and stale prior-counseling details being
inconsistent with an explicit `false` answer.

Inventory responses are not stored in the Redis response-replay idempotency boundary and Inventory
answers are not copied into Audit metadata or Activity projections. The narrow TOTP encryption
helper is not repurposed for this domain. Application-level field encryption is deferred until a
shared domain-content encryption/key-management abstraction exists; deployment/database
at-rest protection remains an infrastructure concern.

### Service and Appointment prerequisite

Service Catalog gains `requires_current_inventory`, default `false`. It is independent of
appointment policy and no migration silently turns it on for the existing Counseling Service.
Business operators can enable the prerequisite through the existing Service Catalog management
workflow.

When a Student creates a new Appointment for a Service requiring current Inventory, Appointment
checks the Inventory status after Student/Provider/Service row locking and normal Service validation,
but before Availability computation, overlap queries, APT reference allocation, Appointment
creation, or Audit. Missing current Academic Year is a configuration error distinct from a Student
having no submitted Inventory. Missing or DRAFT current Inventory produces
`current_inventory_required`; missing current-year configuration produces
`current_academic_year_not_configured`.

These failures remain `AppointmentError` subclasses so the existing Appointment API abandons its
Redis idempotency reservation. A failed prerequisite attempt therefore consumes no Appointment,
reference counter, appointment Audit event, or poisoned idempotency key.

Counselor discovery is not blocked by the Inventory prerequisite. Existing Appointment records are
not rewritten.

### Counseling occurrence boundary

Inventory is an initiation prerequisite, not a historical-reality gate. Counseling Encounter
continues to record actual Counseling that occurred, including `WALK_IN`, even when the Student has
no current submitted Inventory. No Inventory check is added to Counseling Encounter creation, and
Availability is unchanged.

## Consequences

The implementation creates a reusable controlled-document identity foundation without a form
builder and an annual typed Inventory without turning COMPASS into a SIS or generic workflow engine.
Future Routine Interview, E-Counseling, Good Moral, Exit Interview, and other service workflows may
reuse the stable current-Inventory resolver and minimal form registry while continuing to own their
actual domain fields explicitly.

Institutional display branding/profile, print templates, semester/calendar configuration,
administrative Inventory reopen, Counselor Inventory-content access, and generalized sensitive-field
encryption remain deliberate future concerns rather than hidden scope in this foundation.
