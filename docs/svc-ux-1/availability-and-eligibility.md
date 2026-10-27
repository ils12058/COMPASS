# Availability and eligibility

Pathway configuration indicates an option the Service supports, not that a Counselor time, fixed slot or registration seat currently exists. Flexible availability comes from the existing booking service, Counselor and time operations; fixed opportunities from `servicesListBookableSlots`; group session eligibility and capacity from `groupSessionsDiscover`. The backend revalidates all mutations.

A current Student with `appointments.manage_self` can initiate booking; viewing requires the relevant self-view access. Group browsing remains available to eligible viewers without granting registration. Non-current Students and users missing manage capability receive a non-mutation state; the backend remains authoritative. Account/capability changes remount the affected booking state.

The existing flexible flow displays current-year Inventory when configured. The fixed panel now displays the same requirement only when the actual Service flag is true; fixed-only configuration does not imply it. Group registration has no invented Inventory prerequisite. Current backend fixed-slot error mapping returns generic 500 for Inventory exceptions, so it cannot reliably communicate a definitive Inventory refusal in that case; see [contract assessment](api-contract-assessment.md).

Modes reflect the returned Service or offering. Online is not equated with E-Counseling for ordinary Services; existing canonical Counseling copy and separate readiness rules remain unchanged.
