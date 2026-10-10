# ADR-063: Code-owned institutional form compatibility with synchronized DB projection

- Status: Accepted
- Date: 2026-09-27
- Scope: Institutional Form Family and Form Revision ownership

## Context

ADR-022 introduced `FormFamily` and `FormRevision` so domain records could snapshot the official
controlled-form identity used when they were created. It also allowed Head Guidance to register,
activate, and deactivate revision metadata at runtime.

That runtime management surface is misleading for the current product. COMPASS does not contain a
dynamic form engine capable of adopting an arbitrary QMS revision. A database row with a familiar
internal schema version therefore cannot make an arbitrary official revision compatible with the
running software. Treating revision registration as portal configuration creates fake
configurability and allows persisted metadata to claim support that the application does not have.

Institutional document authority and application implementation support are separate concerns. QMS
remains the institutional authority for official controlled-document identity. The running COMPASS
version must remain authoritative for which identities its explicit domain code implements.

## Decision

### Canonical supported definitions live in code

One immutable Institutional Forms registry defines the Form Families supported by this COMPASS
version, their schema compatibility, and any confirmed official revisions:

| Family | Title | Confirmed supported revision |
|---|---|---|
| `individual_inventory` | Individual Inventory | `CNSC-OP-GCO-01F5`, Revision `0`, schema `1` |
| `routine_interview` | Routine Interview Form | None confirmed; schema compatibility `1` exists |
| `referral_slip` | Referral Slip | `CNSC-OP-GTA-01F9`, Revision `1`, schema `1` |
| `call_slip` | Interview Permit / Call Slip | `CNSC-OP-GTA-01F8`, Revision `0`, schema `1` |
| `good_moral_current_student` | Good Moral Character — Current Student | `CNSC-OP-GCO-01F4`, Revision `0`, schema `1` |
| `good_moral_graduate` | Good Moral Character — Graduate | `CNSC-OP-GCO-01F6`, Revision `0`, schema `1` |
| `customer_feedback` | Customer Feedback Form | `CNSC-OP-GTA-01F14`, Revision `0`, schema `1` |

The legacy `CNSC-*` values are confirmed controlled-document identities. The institution's UCN
branding transition does not rewrite them. No Exit Interview, Graduate Tracer, CSM, or other
workflow is added merely because the workflow exists.

Routine Interview deliberately has no fabricated official Form Revision. Its domain may operate
without a saved revision exactly as it did before this decision.

Schema compatibility is part of this same registry rather than an independently maintained map.
A persisted `FormRevision` is operationally supported only when family key, official code,
official revision, and internal schema version exactly match a canonical supported revision.
Matching schema version alone is insufficient.

### PostgreSQL remains the historical and relational projection

`FormFamily` and `FormRevision` remain database models. Downstream records continue to persist
their `FormRevision` foreign key so historical records remain interpretable even after the running
application changes.

Existing migrations remain historical records and are not rewritten. The current source of truth is
the canonical registry plus explicit synchronization.

Unknown or previously runtime-registered revisions are retained. Synchronization does not rewrite
their official identity and does not delete referenced rows. A noncanonical revision cannot remain
active for new records: synchronization deactivates it and restores the canonical active revision.
If persisted state cannot be reconciled without fabricating institutional history, synchronization
fails for operator intervention.

### Synchronization is an explicit deployment operation

Deployments run:

```text
migrate
sync_identity_policy
sync_canonical_services
sync_institutional_forms
check
```

`sync_institutional_forms` is transactional, idempotent, and safe to repeat. It creates missing
canonical rows, repairs code-owned titles/schema metadata/status, preserves existing canonical row
IDs, retires noncanonical active rows, and records a bounded SYSTEM synchronization audit event
when persisted state changes.

Synchronization is not run at import time, application startup, request time, or from the browser.
Institutional Forms are not added to `/health/ready`; the deployment command owns this
reconciliation boundary.

### Runtime revision management is removed

The public API retains only Form Family and Form Revision reads. Registration and
activation/deactivation operations are removed, as are their portal controls and recent-MFA flow.
The Institutional Forms workspace is a read-only reference surface.

Responses project whether each persisted revision is supported by the running COMPASS version.
Clients do not reconstruct compatibility from schema versions or lifecycle status.

`institutional_forms.view` remains canonical. `institutional_forms.manage` is retired from the
code-owned identity policy and Head Guidance grants. `sync_identity_policy` explicitly removes
persisted grants, overrides, and the retired capability row. Unknown unrelated capability rows
remain governed by the existing fail-closed behavior. Existing AuditEvents are not rewritten or
deleted.

Historical `institutional_form.revision_registered`,
`institutional_form.revision_activated`, and `institutional_form.revision_deactivated` events
remain valid history. New reconciliation uses a SYSTEM synchronization event rather than pretending
that a human approved a QMS revision.

### Document rendering remains a separate boundary

`FormRevision` is official controlled-form identity. `DocumentTemplateSpec` is the COMPASS
rendering implementation. They remain separate concepts; this decision does not introduce a generic
template builder.

### Future institutional document integration stays bounded

A future UCN Document/QMS system may become the authoritative source for which official revision
exists. Discovery of an official revision does not automatically make it operational in COMPASS.
The application still requires deployed implementation support for that exact identity.

No QMS client, webhook, scheduler, event bus, placeholder external ID, or adapter is introduced by
this decision.

## Consequences

- Arbitrary schema-`1` database rows can no longer masquerade as supported revisions.
- New records bind only to an active exact canonical revision; existing records retain their saved
  revision FK.
- Routine Interview keeps its current optional-revision behavior without invented metadata.
- The portal no longer exposes software compatibility as a business configuration action.
- Capability and generated API contracts become smaller and more accurate.
- Service Catalog ownership is unchanged and remains legitimately runtime-managed.
- Canonical Counseling retains its existing hybrid rules.
- Organization canonicalization and future CAPS/SIS integration remain separate follow-up work.
- No new database migration is required for this ownership change; historical migrations remain
  untouched.
