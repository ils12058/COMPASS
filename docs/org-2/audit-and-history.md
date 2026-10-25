# Synchronous Audit and restricted change history

Existing canonical events are reused:
`organization.{campus|college|program}.{created|updated|enabled|disabled}`. Official rename uses updated
with changed_fields=[name]. A complete policy change emits the added
`organization.program.policy_changed`. Initialization/adoption and historical catalog_synced actions
remain unchanged; ordinary mutations never reconcile against seed values.

Protected services record one SUCCESS event inside the catalog transaction after the row/version
write. Metadata includes catalog_change=1, stable code and parent UUID, changed fields, before/after
bounded name/state/policy, resource_version_before/after and bounded basis. Actor and timestamp use
the existing AuditContext/record_event service. Creation has before={} and version_before=null,
version_after=1. Status emits enabled/disabled, not a second updated event. No-op emits no event.
Existing Audit shape/byte/depth limits apply. No Student data, Inventory content, Counseling facts
or confidential dependency identities are copied. Audit persistence failure or a later security
recheck/outer transaction failure rolls back the row, version and event atomically.

History GET requires current Catalog management; it does not require or grant global Audit access.
Query is exact target_type/target_id, canonical catalog action, SUCCESS and catalog_change=1, ordered
by occurred_at/id descending. Pagination is page≥1, page_size 1–50, items/page/page_size/has_next;
there is no invented total. The response exposes event UUID/time, actor UUID, action and the explicit
catalog metadata projection. Nested before/after project only allowed catalog value fields.
No actor email/name, request ID, IP, user agent, arbitrary metadata or unrelated events are exposed.

ORG-1 system initialization history does not pretend to be individual versioned catalog changes.
Old unversioned historical updated events without the new marker are not projected. A future
approved migration of that history would need explicit safe attribution semantics, not guessed
versions or reconstructed name history. Effective-dated official names are not implemented.

Tests verify one event per actual mutation, exact actor attribution, no-op silence, target isolation,
paging/limits, strict schema and rollback for create/name/status/policy, including real independent
connections and a rollback after version increment. History is accountability evidence for the
supported path, not cryptographic tamper-proofing against privileged database operators.
