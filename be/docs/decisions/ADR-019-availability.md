# ADR-019: Availability foundation

## Context

COMPASS needs a scheduling foundation that answers when the Guidance and Counseling Office and a specific operational provider can potentially deliver an active Service through a supported delivery mode. Availability is not an Appointment reservation and must not absorb Organization routing, Counseling encounter records, room scheduling, or e-Counseling delivery concerns.

The client confirmed that Counselors manage their own recurring Availability and temporary unavailability. Guidance Services Staff may have independent schedules but have not been granted self-management by default. Counseling normally uses a 60-minute Service default duration; that is a configuration default rather than a maximum. The client also confirmed a 30-minute Counseling Appointment cancellation cutoff, which belongs to the later Appointment domain and is deliberately not implemented here.

## Decision

Create a dedicated `compass.availability` domain with four explicit models: `OfficeAvailabilityWindow`, `ProviderAvailabilityWindow`, `OfficeUnavailability`, and `ProviderUnavailability`. There is no generic resource scheduler, recurrence DSL, RRULE engine, room model, holiday system, or persisted AvailabilitySlot.

Recurring weekly windows store a closed weekday name, local wall-clock start/end times, and an `AvailabilityModeScope` of `ALL`, `IN_PERSON`, or `ONLINE`. One row cannot cross midnight; such a future requirement is represented as two rows. Exact duplicates are prevented by database uniqueness. Semantic overlaps are rejected when rows share a weekday and their mode scopes overlap; adjacent half-open intervals are valid. `IN_PERSON` and `ONLINE` rows may overlap each other because they apply to different delivery contexts.

All interval semantics are half-open: `[start, end)`. Weekly recurrence is interpreted in `settings.TIME_ZONE`; the Availability domain does not hardcode UTC, host-local time, or Asia/Manila. Dated unavailability stores timezone-aware absolute datetimes. Effective queries use `start_date` inclusive and `end_date` exclusive and are limited to 31 days. The implementation does not promise special DST gap/fold policy beyond Python/ZoneInfo behavior; the intended institutional timezone can be configured as Asia/Manila.

Office and provider exceptions only subtract Availability. They may cover partial-day, full-day, or multi-day ranges and may be mode-specific. Short optional reasons are operational metadata, bounded to 255 characters, visible only through authorized raw configuration APIs, never returned by effective Availability, and never copied into Audit metadata.

Provider schedules belong to individual users with primary role `COUNSELOR` or `GUIDANCE_SERVICES_STAFF`. Organization scope does not determine provider Availability. Guidance Services Staff do not inherit a supervising Counselor's schedule. The Head Guidance Counselor remains a Counselor and must have their own Provider Availability; institution-wide responsibility does not imply automatic Availability.

New provider schedule rows and provider exceptions require an active provider-capable user. Existing provider configuration is preserved if an account becomes inactive. Effective Availability for an inactive or non-provider user is not applicable. Administrative cleanup remains possible: replacing an existing provider schedule with an empty set and deleting existing exceptions is allowed even after the provider becomes inactive, preventing cleanup deadlocks before later role changes.

Provider mutations lock the provider User row with `select_for_update`. This serializes self/admin schedule edits and provider role transitions around the same owner row. Office Availability has no natural parent row, so Office mutations take one transaction-scoped PostgreSQL advisory lock dedicated to Office Availability configuration. No Redis/distributed lock is introduced.

Account Management retains Organization role-transition validation and additionally calls an Availability-owned role-transition validator. A change from Counselor/Guidance Services Staff to a non-provider role is rejected with a controlled conflict while recurring Provider Availability or Provider unavailability exceptions remain. No Availability data is silently deleted and no signal or generic cross-domain policy engine is used.

Base Availability for a requested provider, Service, delivery mode, and bounded date range is calculated as:

`Provider weekly ∩ Office weekly − Office unavailability − Provider unavailability`.

The resolver uses Service Catalog as source of truth. The Service must be active, support the requested delivery mode, and allow the provider's active primary role through the canonical provider-role helper. A small Service Catalog delivery-mode helper prevents Availability from depending on ServiceDeliveryMode persistence details. Organization routing and student College scope are intentionally absent from this resolver.

Weekly intervals are expanded in the configured institutional timezone, normalized, intersected, then dated exceptions are subtracted. Results are clipped to the requested half-open range and returned in deterministic order. If `Service.default_duration_minutes` is set, resulting windows shorter than that default are removed. Longer windows remain whole intervals; the resolver does not split or persist slots. Appointments do not exist in this slice, so booked reservations are not subtracted.

Three Availability capabilities are added. `availability.view` reads effective Availability. `availability.manage_self` permits an active Counselor to manage only their own Provider weekly schedule and Provider exceptions. `availability.manage` is broad administrative authority for Office and any eligible provider's raw Availability configuration. IT Admin receives view/manage; Counselor receives view/manage_self; Guidance Services Staff and Student receive view only; the Head Guidance Counselor designation adds manage. DPO receives no Availability grant. Existing account GRANT/REVOKE semantics remain authoritative per capability.

Self-service uses explicit `/api/v1/availability/me/...` routes and derives the provider from `request.auth_user`; clients never supply their own provider ID. Self-service mutations require an active Counselor and effective `availability.manage_self` or `availability.manage`, but do not require recent MFA. Administrative mutation routes require `availability.manage` plus recent MFA. Raw Office/other-provider configuration is restricted to manage; effective Availability is available to `availability.view` callers and excludes internal exception reasons.

Availability mutations emit only the business actions `availability.office_schedule.updated`, `availability.office_exception.created`, `availability.office_exception.removed`, `availability.provider_schedule.updated`, `availability.provider_exception.created`, and `availability.provider_exception.removed`. Self and administrative paths call the same transactional Provider services; actor/target identifies who changed whose configuration. Equivalent weekly replacements emit no fake Audit event. Availability events are not projected into My Activity or Security Activity.

## Consequences

Availability remains understandable and explicit. It does not create Appointment, cancellation, booking, rescheduling, Appointment conflict logic, replacement-provider selection, preferred-counselor persistence, ServiceDelivery, Counseling encounters, service-specific office hours, room scheduling, notifications, or frontend code.

Counseling's current one-hour requirement is represented only as a future real Counseling Service configuration with `default_duration_minutes = 60`; Availability contains no Counseling code special case and no maximum duration. The confirmed rule that a Counseling Appointment may be cancelled only at least 30 minutes before its scheduled start is documented for the upcoming Appointment slice and has no effect on Availability.

When Appointments are introduced, final free booking time will conceptually be base Availability minus active Appointment reservations. Adding Availability exceptions must never silently move, cancel, reassign, or retime future Appointments; affected reservations will require explicit Appointment-domain handling.
