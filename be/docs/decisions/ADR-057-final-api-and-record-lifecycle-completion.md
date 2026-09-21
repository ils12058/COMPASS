# ADR-057 — Final API and Record Lifecycle Completion

**Status:** Accepted  
**Date:** 2026-09-20

## Context

COMPASS is entering frontend/UAT preparation with several bounded backend gaps still visible in otherwise established domains. These gaps concern explicit operational outcomes, safe correction of mistaken institutional records, and a few missing HTTP surfaces over already-established services.

The system must preserve institutional traceability. Physical deletion is not the ordinary correction mechanism for business records.

## Decision

### Institutional record lifecycle vocabulary

COMPASS uses domain-specific semantics rather than a global lifecycle framework:

- **EDIT** for mutable drafts and current configuration;
- **DEACTIVATE** for retired master/configuration data;
- **ARCHIVE** for published content no longer active;
- **CANCEL** for a request or reservation that should no longer proceed;
- **VOID** for an erroneously created institutional record that must remain traceable;
- **REOPEN** for controlled correction of a submitted form;
- **COMPLETE / NO_SHOW** for Appointment outcome.

No global `SoftDeleteModel`, `deleted_at`, `is_deleted`, generic archive mixin, generic state machine, generic PATCH-anything endpoint, or ordinary hard-delete business API is introduced.

Existing deletion/removal of current relationships, transient authentication state, availability exceptions, and replaceable profile-photo objects remains infrastructure/current-state cleanup rather than institutional-record deletion.

### Appointment lifecycle

Appointment status is:

`SCHEDULED -> CANCELLED | COMPLETED | NO_SHOW`

All three outcomes are terminal.

`cancelled_at/by`, `completed_at/by`, and `no_show_at/by` provide explicit terminal provenance with database consistency constraints.

Rescheduling and reassignment are controlled mutations while status remains SCHEDULED. They append typed `AppointmentChangeEvent` rows rather than generic JSON history.

Student self-rescheduling requires current Student lifecycle, ownership, `appointments.manage_self`, an unstarted SCHEDULED Appointment, and the existing cutoff evaluated against the pre-mutation start time. Administrative rescheduling requires `appointments.manage`, current Appointment scope, and recent MFA.

Rescheduling preserves duration, Student, Service, provider, delivery mode, reference code, and cancellation cutoff. It revalidates current Service/provider eligibility, Availability, and Student/provider conflicts, but deliberately does not re-run the initial Inventory prerequisite. An existing E-Counseling room binding blocks rescheduling.

Administrative reassignment requires `appointments.manage`, scope, recent MFA, an unstarted SCHEDULED Appointment, an eligible available active Counselor, and no provider conflict. Existing Routine Interview, Counseling Encounter, or E-Counseling room bindings block reassignment. No downstream Counselor record is rewritten.

Completion requires `appointments.manage`, scope, SCHEDULED state, and current time at or after the Appointment start. No-show requires the same authority, current time at or after Appointment end, and no linked Counseling Encounter.

Appointment history is a bounded projection of CREATED, typed reschedule/reassign events, and the current terminal event. Related self-viewers do not receive internal change reasons; scoped operational managers may receive bounded reasons.

A completed Appointment remains valid provenance for later Appointment-backed Counseling Encounter recording. First-time Appointment-backed Routine Interview creation remains SCHEDULED-only. E-Counseling eligibility remains SCHEDULED-only.

### Student Support roster

`GET /api/v1/student-support/students` is a current-Academic-Year operational roster, not analytics.

Regular Counselors see active Students under active current College responsibilities. Zero responsibility fails closed to an empty result. Head Guidance Counselor receives institution-wide active Student scope and may see a Student without a current affiliation.

The roster exposes only Student identity, current College when available, current Academic Year, Inventory status, availability of the submitted support projection, and the existing privacy-minimized indicators:

- PWD
- SOLO_PARENT
- FOUR_PS_BENEFICIARY
- INDIGENOUS_PEOPLES_MEMBER
- MOTHER_DECEASED
- FATHER_DECEASED

MISSING and DRAFT Inventory rows expose no indicators. Scope is applied before search, filters, ordering, and pagination.

### Profile photo HTTP completion

The authenticated owner may set or remove the current profile photo through:

- `PUT /api/v1/me/profile/photo`
- `DELETE /api/v1/me/profile/photo`

The API reuses the existing bounded raster validation, normalization, metadata stripping, private object storage, signed URL, replacement, and cleanup implementation. Removal is idempotent. Obsolete avatar binary deletion remains permitted because profile photos are replaceable user-owned media, not immutable institutional records.

### Notification read-all

`PATCH /api/v1/notifications/read-all` updates only the authenticated recipient's unread notifications using one server timestamp and returns the number changed. It does not delete notifications, mark them unread, or create audit noise.

### Referral void

An erroneous Referral may be voided with required bounded reason and explicit void provenance. The row and reference code remain permanently retained.

Default operational listing excludes voided Referrals; authorized direct retrieval remains available. Voided Referrals cannot receive status-note changes or new actions.

A Referral with a non-voided linked Call Slip cannot be voided. Correcting a bad Referral therefore means resolving/voiding the active Call Slip first, voiding the Referral, and creating a new Referral rather than rewriting source facts.

### Call Slip void and corrected reissue

A Call Slip has a derived lifecycle:

- ACTIVE when neither voided nor interview-completed;
- COMPLETED when interview completion is recorded;
- VOIDED when void provenance exists.

Only ACTIVE Call Slips may be voided. COMPLETED Call Slips remain historical. Student self-history may show VOIDED state but does not expose the internal void reason.

The Referral relation is a ForeignKey with a conditional uniqueness constraint allowing at most one non-voided Call Slip per Referral. Historical voided Call Slips remain linked, and a corrected replacement may be issued from the same non-voided Referral.

A voided Referral cannot receive a new Call Slip. A voided Call Slip cannot later record interview completion.

### Good Moral request cancellation

Good Moral adds only:

`REQUESTED -> CANCELLED`

for pending requests. Students may cancel their own REQUESTED request using existing self-service authority; operational Counselors may cancel REQUESTED requests using `good_moral.manage`.

CANCELLED records are retained and cannot be corrected, issued, or rendered as final certificate PDFs. ISSUED records remain immutable. No certificate revocation/reissue workflow is introduced.

### Audit and notifications

New structural audit actions are limited to:

- appointment.rescheduled
- appointment.reassigned
- appointment.completed
- appointment.no_show
- referral.voided
- call_slip.voided
- good_moral.request.cancelled

Generic Audit metadata excludes sensitive free-text reasons and Guidance content.

Repeatable Appointment reschedule/reassign notifications use `AppointmentChangeEvent` UUID as source identity so distinct legitimate changes do not collapse under notification uniqueness.

Code-owned mandatory operational events are added for Appointment reschedule/reassignment and Call Slip withdrawal. Their messages contain no internal reasons or Guidance narrative.

## Explicitly deferred

This ADR does not add Inventory/Exit/Routine/Graduate-Tracer/Feedback/Counseling deletion symmetry, Routine reopen, issued Good Moral revocation/reissue, generic Referral/Call Slip editing, Academic Year deletion, generic soft delete, or frontend workflow UI.

This decision supersedes only earlier deferrals for the concrete operational gaps above; it does not characterize those earlier deferrals as architectural mistakes.
