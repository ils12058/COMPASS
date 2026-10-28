# Scoped fixed-slot access

The operational entry point is `/portal/appointments/slots`. Its frontend visibility hint requires
`appointments.manage` and either the `COUNSELOR` or `GUIDANCE_SERVICES_STAFF` role. It does not
grant a capability.

The existing backend operations continue to validate account activity, role, capability, direct
GSS supervision, provider qualification, Service pathway, ownership, and current scope. A
Counselor remains self-scoped; supervised GSS remains scoped to the active supervising Counselor.
Service Catalog administrators do not gain slot authority merely from `services.manage`.

The selector uses paginated `servicesList`; it does not claim that one page is the whole catalog.

