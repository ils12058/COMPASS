# ADR-021: Counseling encounter foundation

## Context

COMPASS needs a canonical record that Counseling actually occurred. Appointment remains a scheduled reservation; Availability remains potential scheduling time; Organization remains default routing/responsibility; Service Catalog remains the source of Service identity, delivery-mode support, and provider-role eligibility. Counseling must not collapse those domains or pre-build Routine Interview, Referral, Call Slip, Case Record, ServiceDelivery, e-Counseling delivery, or a generic workflow/form engine.

Counseling occurrence is sensitive even before narrative notes exist. Ordinary access therefore needs both a Counseling capability and assignment to the specific Encounter. College responsibility, Head designation, DPO designation, technical administration, or Student identity do not imply confidential-record access.

## Decision

Create a dedicated `compass.counseling` domain with one persistent `CounselingEncounter` model. It stores UUID identity, Student, assigned Counselor, canonical Counseling Service, optional one-to-one Appointment link, closed entry mode (`APPOINTMENT`, `WALK_IN`, `CALLED_IN`, `REFERRED`), delivery mode, actual start/end timestamps, creator, and timestamps. There is no Encounter status in this foundation: existence means an actual completed encounter was recorded.

Student, Counselor, Service, and Appointment use `PROTECT`; `created_by` uses `SET_NULL`. A database check enforces `started_at < ended_at`. A second local check enforces that `entry_mode = APPOINTMENT` requires an Appointment link. The reverse is deliberately not enforced because entry mode describes origin, not link type: a future CALLED_IN or REFERRED workflow may legitimately retain an Appointment.

The canonical Service binding is the stable Service Catalog code `COUNSELING`. Counseling requests do not create Service data. ADR-060 makes explicit deployment synchronization responsible for provisioning this system-required Service; Counseling still fails safely if the configuration is missing or invalid. New encounter creation requires that configured Service to exist, be active, allow the COUNSELOR provider role, and support the selected/derived delivery mode. The Service's normal 60-minute default is scheduling configuration, not an actual Encounter maximum. Appointment cancellation cutoff is not a Counseling rule.

Actual encounter times must be timezone-aware, satisfy `started_at < ended_at`, and end no later than current time. Public timestamps normalize to `settings.TIME_ZONE`. Actual times do not need to equal or fit inside Appointment time and are not checked against Availability or scheduling conflicts because this record describes historical service delivery.

For normal creation the authenticated active primary-role COUNSELOR is always `encounter.counselor`; clients cannot supply another Counselor. Direct WALK_IN/CALLED_IN/REFERRED creation requires an active Student and explicit delivery mode. Appointment is optional overall. If an Appointment is supplied for any entry mode, it is authoritative for Student, Counselor, Service, and delivery mode; mismatched duplicated client values are rejected. `APPOINTMENT` entry mode additionally requires the link.

Appointment-linked creation locks only the base Appointment row with `select_for_update`, then locks current Student/Counselor identities and the canonical Service before revalidation. The Appointment must be SCHEDULED, belong to the same Student and authenticated Counselor, use the canonical Counseling Service and same delivery mode, and not already have an Encounter. The nullable one-to-one relationship and database uniqueness remain authoritative for one Encounter per Appointment. Counseling creation never changes Appointment status.

Correction is a narrow assigned-Counselor PATCH. Student, Counselor, Service, creator, and creation time are immutable. Entry mode, Appointment link, delivery mode, and actual timestamps may be corrected with complete resulting-state validation. The Encounter row is locked first; when Appointment links are involved, old/new Appointment rows are locked in deterministic UUID order. Historical correction is not blocked merely because the Counseling Service was later disabled. If a direct Encounter's delivery mode is actually changed, the newly proposed mode must still be configured for the Counseling Service. No-op corrections produce no fake Audit event.

Add `counseling.view_assigned` and `counseling.manage_assigned`. COUNSELOR receives both. Guidance Services Staff, Student, IT Admin, DPO, and Head designation receive no Counseling-specific grant by default. Head remains a Counselor and therefore has normal access only to their own assigned Encounters. Capability overrides retain existing GRANT/REVOKE semantics, but capability alone never bypasses the primary-role COUNSELOR and `Encounter.counselor_id == actor.id` resource relationship.

The existing Organization people endpoint is not reused for Student selection because it requires organization-management authority and exposes broader account fields. Counseling therefore adds a narrow `/counseling/students` lookup for active Students, bounded search/pagination, deterministic ordering, and only `id` plus `display_name`. It does not apply College scope as a hard wall.

The current Redis idempotency response-replay mechanism is deliberately not attached to `POST /counseling/encounters`. It stores completed HTTP response bodies, while Counseling occurrence itself is sensitive and should not be cached in Redis without a proven need. PostgreSQL transactions, Appointment locking, and the one-to-one constraint remain authoritative. Direct non-Appointment retries can theoretically create duplicate historical records; a future privacy-safe/durable idempotency design may address that without inventing a second mechanism in this slice.

Audit records only `counseling.encounter.created` and `counseling.encounter.updated` with small metadata (entry mode, delivery mode, Appointment ID, or changed field names). No Student personal details, future notes, Routine Interview answers, recommendations, or response bodies are duplicated into Audit. Routine reads do not emit noisy `viewed` events yet, and Counseling actions are not projected into My Activity or Security Activity.

## Consequences

The public Counseling API is deliberately small: create Encounter, list the authenticated Counselor's assigned Encounters, get assigned Encounter detail, correct assigned Encounter metadata, and search minimal active Student identity. There is no delete, reassignment, broad view-all capability, live-session state machine, human Counseling reference code, generic notes/metadata field, role-transition blocker, or recent-MFA step-up for ordinary assigned-Counselor work.

Routine Interview, narrative/clinical note structure, Referral, Call Slip, Case Record, ServiceDelivery, Customer Feedback, Daily.co rooms/tokens/recording, recording consent, notifications, multi-Counselor teams, and broader confidential-record access remain explicit future decisions.
