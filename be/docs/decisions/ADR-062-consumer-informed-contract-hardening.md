# ADR-062: Consumer-Informed Contract Hardening

- Status: Accepted
- Date: 2026-09-26
- Scope: Cross-domain API contracts, locking, and error mapping after the frontend integration audit

## Context

An audit of the frontend as the first API consumer found places where it rebuilt backend truth. It
duplicated eligibility rules and enums, parsed English error messages, and inferred state from the
first page of a list. It also fanned out per-row lookups and judged date legality with the browser
clock. The backend was missing projections, filters, and search that the workspaces needed. Call
Slip provenance was unrecorded. Some backend paths also locked more rows than intended. One made
an external HTTP call inside a row lock. Some classified errors by message text.

## Decision

**Closed values are enums.** Response fields and query parameters that carry a closed set are
published as OpenAPI enums: roles, designations, capabilities, lifecycle, statuses, sources,
failure codes, and targets. Clients use the generated constants and do not keep their own copies.
Enum values mirror model choices and are additive.

**Eligibility is projected, not rebuilt.** Where a client must decide whether to offer an action,
the owning domain projects that decision for the requesting actor. The projection is computed with
server time and linked records:

- Appointment detail `actions` gives each lifecycle action with `allowed` and a closed `blocker`.
- Appointment and Routine Interview details give `counseling_context_available`.
- Email deliveries give `manual_retry_allowed` and `manual_retry_blocker`.
- Notice revisions give `publish_readiness`.
- Call Slips give `void_notifies_student`.
- Services give `is_system_required`.

Projections are advisory. Every mutation revalidates under locks, so clients must still handle 409
and refetch.

**Errors are stable codes chosen by exception type.** A backend never selects an error code by
matching message text.

- Privacy Governance conflicts carry specific `privacy_*` codes.
- Good Moral creation-identity conflicts use the shared `idempotency_key_conflict` code, like the
  other idempotent creation routes.
- The Appointment cancellation cutoff has its own exception type.

**Discovery filters match counted populations.** An Overview count and the list it links to share
one filter implementation:

- Privacy Incidents `active`
- Call Slip `state`
- Appointment `upcoming` (SCHEDULED and not yet started)

Retention Policies accept a bounded `search`. Review detail includes a small Processing Activity
identity. Notice detail includes current and draft revision summaries. Clients do not scan pages
to find these.

**Provenance is recorded, not inferred.** Call Slips store an `issuance_mode`: `LIVE`,
`HISTORICAL`, or `LEGACY_UNKNOWN`.

- Existing rows are `LIVE` only when an issued notification proves it. All other existing rows are
  `LEGACY_UNKNOWN`.
- No history is fabricated.
- Voiding a `HISTORICAL` Call Slip does not notify the Student.

**Locks are scoped.** `select_for_update` uses `of=("self",)` unless a joined parent row is
deliberately part of the serialization. Those parents are named explicitly. External network calls,
such as PSGC resolution, run before locks are taken, and their results are revalidated under the
lock.

**Database failures map by SQLSTATE.**

- Uniqueness, foreign-key, and exclusion violations return 409.
- Check violations and data errors return 422.
- Any other integrity failure is logged and returns the generic 500.

Fallback queries that follow a caught `IntegrityError` run inside a savepoint. An idempotency
reservation is abandoned after an unexpected failure, so a retry is not replayed as in progress.

## Consequences

The frontend removes its duplicated rules, message parsing, page-one lookups, and per-row
fan-out. It uses these projections and filters instead. Contract changes are additive except for
two documented refinements:

- Enum typing narrows previously free-form strings.
- Good Moral key-reuse conflicts now return `idempotency_key_conflict` instead of
  `good_moral_conflict`.

No confidential fields are added for client convenience. Capability semantics and scope rules are
unchanged. This ADR adds no generic CRUD, search, expansion, or workflow engine.
