# ADR-089: Service Catalog semantic consolidation and Counselor provider qualification

## Status

Accepted. Refines the Service Catalog, scheduling, and provider parts of
[ADR-018](ADR-018-service-catalog.md), [ADR-019](ADR-019-availability.md),
[ADR-020](ADR-020-appointments.md), [ADR-021](ADR-021-counseling.md),
[ADR-024](ADR-024-ecounseling-daily.md), [ADR-050](ADR-050-final-operational-gap-closure.md), and
[ADR-060](ADR-060-canonical-counseling-service-bootstrap.md). The rest of those decisions stands,
as do ADR-087 (Routine ↔ Encounter linking) and ADR-088 (optional Inventory provenance).

## Context

The Service Catalog's configuration had drifted from what COMPASS enforces:

- **Appointment policy.** `appointment_policy` offered `NONE`, `OPTIONAL`, and `REQUIRED`, but only
  `NONE` changed behavior. `OPTIONAL` and `REQUIRED` were both simply bookable. ADR-018 stored the
  three states ahead of workflow enforcement that never came, and Counseling is legitimately
  recorded as `APPOINTMENT`, `WALK_IN`, `CALLED_IN`, or `REFERRED` whatever the policy said.
- **Provider roles.** Since ADR-050, Counselor is the only operational provider class and every
  active Service must allow it. The "Provider eligibility ☐ Counselor" choice was therefore not a
  real choice.
- **No per-Service qualification.** COMPASS could not say that only some Counselors provide a
  Service (Psychological Testing by Counselors A and C, Career Guidance by B and C).
- **Fulfillment re-checked live configuration.** E-Counseling and Appointment-backed Counseling
  checked the Service's current delivery modes and provider eligibility. Removing ONLINE, or a
  Counselor, after booking could make an already valid Appointment impossible to fulfill.

## Decision

### What the Service Catalog answers

| Question | Owner |
| --- | --- |
| What Service exists? | Service Catalog |
| Can it be booked through Appointments? | `appointment_booking_enabled` |
| How may new instances be delivered? | delivery modes (`IN_PERSON`, `ONLINE`) |
| Who is qualified to provide new instances? | `provider_coverage` (+ selected Counselors) |
| Does booking need a submitted current Inventory? | `requires_current_inventory` |
| How long is a newly booked Appointment? | `default_appointment_duration_minutes` |
| What is the Student self-service cutoff? | `cancellation_cutoff_minutes` |

The Catalog does not decide which College owns or may use a Service, who a Student's default
Counselor is, when a Counselor is available, or who may access confidential records. Those
questions belong to Organization, Availability, and the record domains.

### Appointment booking

The three-state `appointment_policy` is replaced by `appointment_booking_enabled`.

- **Off:** the Service cannot be newly booked.
- **On:** the Service may be booked.

An enabled Service does not claim that every workflow requires an Appointment; each domain owns
its direct initiation. Canonical COUNSELING is bookable and still records walk-in, called-in, and
referred Counseling.

Migration `service_catalog.0004` maps `NONE` to off and `OPTIONAL`/`REQUIRED` to on. No enforced
behavior is lost, because the two were indistinguishable. The old enum is removed from the model,
API, and generated client.

### Appointment-only settings

`default_duration_minutes` becomes `default_appointment_duration_minutes`.

- **While booking is off,** the duration and cutoff are NULL and `requires_current_inventory` is
  false. A database constraint enforces this.
- **Turning booking off** clears all three in the same transaction. Supplying one explicitly
  alongside booking off is rejected rather than discarded.
- **An active Service with booking on** needs a duration; the cutoff and the Inventory
  prerequisite stay optional.
- **Inactive Services** may be incomplete.

The migration clears these settings on existing booking-off rows.

`requires_current_inventory` remains purely a new-booking prerequisite. It never gates Service
delivery, Counseling, Routine Interviews (ADR-088), rescheduling, or completing an existing
Appointment.

### Provider qualification

Counselor is the V1 provider class and is no longer a configurable choice. `ServiceProviderRole`
is legacy: its historical rows, including Guidance Services Staff ones, are kept untouched but are
never written or read for eligibility.

`Service.provider_coverage` is either:

- `ALL_COUNSELORS` (the default for every migrated Service and for new ones); or
- `SELECTED_COUNSELORS`, with `ServiceCounselorProvider` rows. Each row has one Service and one
  Counselor (PROTECT), is unique per pair, and carries no College, Availability, or routing data.

`service_counselor_eligible(service, counselor)` is the one rule for **new** work:

```
active account AND primary role COUNSELOR AND (
    ALL_COUNSELORS OR the Counselor is selected
)
```

A Head Guidance Counselor qualifies through their Counselor role. The rule never consults
CounselorResponsibility, Student College, Availability, record access, or Appointment ownership,
and qualification grants no record access.

**Selection rules:**

- Only active Counselors can be newly selected.
- A selected Counselor who later becomes inactive stays selected but is not eligible. Coverage is
  never widened automatically.
- An active `SELECTED_COUNSELORS` Service needs at least one active selected Counselor.
- With `ALL_COUNSELORS`, no selection is stored.

### College boundary

ADR-020 stands. College responsibility resolves a Student's default Counselor and organizational
scope; it does not restrict explicit Counselor choice and is not copied into the Catalog. There is
no Service-to-College relationship.

### New work uses current configuration

Each of the following uses current Service state, current delivery modes, and the qualification
rule:

- **Appointment booking.** The Service must be active, bookable, have a duration, and support the
  delivery mode. The chosen Counselor must be qualified. The Inventory prerequisite applies when
  set, followed by Availability and conflict checks.
- **Booking discovery.** It lists only bookable Services with at least one qualified Counselor.
- **Eligible-Counselor discovery.** It lists qualified Counselors. The College default is marked
  only when that Counselor is in the list; it is never forced in. If the caller omits a provider
  and the default is not qualified, booking fails with
  `appointment_default_provider_not_qualified` rather than substituting someone else.
- **Effective Availability** for a Service, Counselor, and mode. It is unavailable for an
  unqualified Counselor. The Appointment duration shapes windows only while booking is on.
- **New direct Counseling and direct Routine Interviews.** Includes their creation options.
- **Rescheduling and reassignment.** These modify a reservation, so they bring it back under the
  current rules. A reassignment target must be qualified, but the current provider need not be:
  losing qualification is a reason to reassign.

### Existing Appointments keep their provenance

A validly booked Appointment stays fulfillable as booked. Its saved Student, Counselor, Service,
delivery mode, duration, cutoff, and reference stand. Later Catalog changes govern only new work.

- **E-Counseling** trusts the saved ONLINE Appointment: canonical Service identity, ONLINE mode,
  SCHEDULED status, the Student/Counselor relationship, current account and capability rules, and
  Daily readiness. It no longer re-checks live ONLINE support or the Counselor's coverage.
- **An Appointment-backed Encounter** derives its Student, Counselor, Service, and mode from the
  Appointment. It still requires the relationship, lifecycle, one Encounter per Appointment, the
  canonical Service, and valid times. The Counselor's own Appointment candidates are not filtered
  by current modes.
- **Ensuring an Appointment's Routine Interview** and listing a Student's Appointment candidates
  use the Appointment, not current modes or coverage. First creation still requires SCHEDULED,
  and ADR-087 linking and ADR-088 provenance are unchanged.
- **Corrections:**
  - An Appointment-linked Encounter keeps its Appointment's mode, which need not still be offered.
  - Relinking to another Appointment derives from that Appointment.
  - A direct Encounter's new delivery mode must be currently offered.

### Consequence review

Explicit acknowledgement is required, and Appointments are never changed, when a legal change
affects future SCHEDULED Appointments:

- booking turned off while any exist;
- a delivery mode removed that one uses;
- a coverage or selection change that would make the provider of one ineligible for new work;
- disabling an ordinary Service while any exist (the disable request carries
  `acknowledge_scheduling_consequences`).

Enabling ONLINE for canonical COUNSELING keeps its acknowledgement that E-Counseling provider
readiness is managed separately. Name, description, duration, cutoff, and Inventory-prerequisite
changes need no review, because Appointments keep their snapshots.

The 409 `service_scheduling_consequence_review_required` details are:

- `existing_appointment_dependency_detected`
- `provider_dependency_detected`
- `counseling_online_enabled`

Audit metadata records the same flags when acknowledged.

### Canonical COUNSELING

**Fresh configuration:**

- active;
- booking on, 60-minute duration, 30-minute cutoff;
- no Inventory prerequisite;
- `IN_PERSON` only (ONLINE stays an explicit deployment decision);
- `ALL_COUNSELORS`;
- no legacy role rows.

**Synchronization:**

- keeps valid operator configuration, including selected coverage and ONLINE;
- never resets coverage;
- repairs only structural drift: a blank name, a missing or invalid duration while booking is
  on, missing or invalid delivery modes, and an inactive Service. Repairs are acknowledged system
  updates.

A selected coverage with no active Counselor is reported by readiness
(`selected_counselors_missing`) for an operator to fix, not widened. COUNSELING still cannot be
disabled. Daily readiness is not a Catalog dependency, and ONLINE remains a delivery mode of
Counseling, not a separate Service.

### API

**Service request and response fields:**

- Service create, update, and response use `appointment_booking_enabled`,
  `default_appointment_duration_minutes`, and `provider_coverage`.
- Create and update also take `selected_counselor_ids`.
- Responses include `activation_blockers`: why an inactive Service cannot yet be enabled
  (`DELIVERY_MODE_MISSING`, `APPOINTMENT_DURATION_MISSING`, `SELECTED_COUNSELORS_MISSING`).
- `appointment_policy` and `provider_roles` are removed.
- The list filter is `appointment_booking_enabled`.

**Provider configuration:**

- It is written through the Service mutation: `services.manage`, recent MFA, transactional, with
  consequence review.
- It is read through `GET /services/{id}/providers` (selected Counselors with `is_active`) and
  `GET /services/provider-candidates` (active Counselors, `id` and `display_name` only, no College
  filter). Both require `services.manage`; catalog readers see only the coverage.

Code uniqueness, the reserved COUNSELING code, no delete endpoint, no-op updates without audit,
and the capability model are unchanged.

## Consequences

- Administrators configure booking as Available or Not available and choose all or selected
  Counselors, with no redundant Counselor checkbox.
- Booking, Availability, direct Counseling, direct Routine Interviews, and replacement-provider
  discovery share one qualification rule.
- Catalog changes stop new work without retroactively invalidating Appointments that were valid
  when booked; changing such an Appointment may require bringing it into the current
  configuration.
- No historical provider-role data is deleted, and the Catalog remains institution-wide.
