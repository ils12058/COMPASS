# ADR-073: Curated activity retrieval, DPO export and direct staff supervision

- Status: Proposed
- Date: 2026-10-04
- Refines: ADR-006 capability and organizational scope; ADR-011 append-only Audit Trail
- Preserves: ADR-013 self activity, ADR-069 historical retention registry, ADR-070 capability dependencies and ADR-072 operational retention/disposition

## Purpose and projection boundary

Activity surfaces remain closed, purpose-specific projections of internal evidence. An event is
invisible unless the surface's explicit action, target, outcome and presenter policy admits it.
No raw AuditEvent API/browser/export, arbitrary metadata query, IP address, User-Agent or request ID
is introduced. AuditEvent mutation/deletion protections and retention/disposition semantics are
unchanged. Curated activity is not the complete Audit Trail.

My activity and Security activity retain their existing self-only presenter allowlists and
page/page_size contracts. Neither accepts another person's scope or gains search, filters or
export. A separate Supervised staff view provides operational oversight, not staff security history.
Platform Technical Activity gains retrieval tools without expanding its existing five-action
allowlist or `platform_operations.view` authority. Privacy & Security Activity keeps all its existing
safe presentations, including the eleven ADR-072 retention/disposition actions and three historical
removed-registry actions; CSV uses exactly that same safe projection.

## Capability plus current direct supervision

`activity.supervised_staff.view` is baseline-granted only to Counselors. Head Guidance receives it
through the Counselor role, without any designation-based global scope. Student, GSS, IT Admin and
Institutional Officer/DPO gain no baseline grant. Existing explicit overrides remain effective.

The authenticated actor must have the effective capability. Every event additionally requires a
current StaffSupervision row whose supervisor is that actor and whose staff is the event's actor.
Both people must be active and satisfy the existing organizational relationship contract: Counselor
supervisor and GSS staff. These relationship checks constrain scope; the capability remains the
authorization gate. An exceptional capability grant cannot manufacture a StaffSupervision row.
No responsibility-college, Head Guidance or all-GSS fallback exists. The client cannot supply a
supervisor ID to expand scope; an out-of-scope staff filter returns no rows.

`GET /api/v1/me/supervised-staff` is a narrow paginated picker of current direct staff IDs and display
names. It grants no account/organization-management access or email discovery. The tab appears only
after the capability and nonempty current picker scope are confirmed. Direct navigation by an
unscoped eligible actor receives an intentional empty state.

### Current-assignment time boundary

StaffSupervision is one mutable row per staff member. Its existing mutation service updates
`updated_at` when supervisor changes; setting the same supervisor is a no-op. Consequently
`occurred_at >= StaffSupervision.updated_at` is the defensible current-assignment boundary. Initial
creation sets the same boundary. The current relationship, roles, active status and timestamp are
evaluated with SQL EXISTS inside the event SELECT, rather than using a previously fetched ID list.

After A → B reassignment, B sees only events from B's assignment start. A immediately loses all
access through the former relationship, including earlier events. Removal yields no staff data.
Reassignment back to A begins a new boundary. There is no historical supervision ledger or inferred
former-membership access. Backfilled or externally rewritten timestamps cannot establish historical
membership; this feature deliberately relies on the current canonical relationship mutation service.

## Exact supervised operational allowlist

Only successful USER events performed by a currently scoped GSS enter this projection. Each target
must match the owning resource contract and have a syntactically valid UUID. The resource is not
looked up and its target UUID is not returned. Titles/descriptions are static; metadata is not read.
The projected fields are event ID, closed type, timestamp, safe title/description, staff ID/name.

| Exact actions | Required target type | Current GSS authority |
| --- | --- | --- |
| `appointment.cancelled`, `appointment.rescheduled`, `appointment.reassigned`, `appointment.completed`, `appointment.no_show` | `appointments.appointment` | `appointments.manage`; existing appointment service scope |
| `referral.created`, `referral.status_updated`, `referral.voided` | `referrals.referral` | `referrals.manage`; existing referral service scope |
| `referral.action_recorded` | `referrals.referralaction` | `referrals.manage`; operational action service |
| `call_slip.created`, `call_slip.interview_ended`, `call_slip.voided` | `callslips.callslip` | `call_slips.manage`; existing Call Slip service scope |
| `announcement.created`, `announcement.updated`, `announcement.published`, `announcement.archived` | `announcements.announcement` | `announcements.manage` |
| `resource.created`, `resource.updated`, `resource.file_attached`, `resource.file_removed`, `resource.published`, `resource.archived` | `resources.resource` | `resources.manage` |

The 22 actions were checked against their current service emitters and API authority. In particular,
`appointment.created` is excluded: current creation is Student self-booking. Login/logout/session,
password/recovery/MFA/trusted-browser/profile/account activity and all other business action families
are excluded. Referral notes, Student identity, confidential record bodies, announcement/resource
contents, attached file names and internal delivery/provider details are never projected here.

## Retrieval contracts and performance

| Surface | Exact query criteria | Export |
| --- | --- | --- |
| Supervised staff | `search`, `staff_id`, closed `event_type`, `date_from`, `date_to` | None |
| Platform Technical Activity | `search`, closed `event_type`, `operator` display-name text, `date_from`, `date_to` | None |
| Privacy & Security Activity | `search`, existing closed `category`, closed `event_type`, `actor` display-name text, `date_from`, `date_to` | DPO CSV with these same criteria |

Criteria combine with AND. Search/name text is at most 100 characters, rejects control characters,
normalizes whitespace and case-folds. Search only evaluates presented fields: supervised static
action/title/description/staff name; Platform type/title/description/operator; Privacy
type/title/description/actor/artifact/format/scope/reference. Hidden metadata cannot create matches.
Failed authentication's suppressed actor identity remains unsearchable. Operator/actor filters use
the safe current display name, not email, raw account target IDs or historical identity snapshots.

Date bounds are calendar dates in the configured institutional timezone (Asia/Manila by default).
From is inclusive local midnight; to is exclusive midnight of the following day, making the entire
selected end day inclusive. Invalid/reversed ranges fail with a typed 422. All feeds order by
`occurred_at DESC, id DESC`. Page is 1–100000; page size is 1–50 (default 20). Projection validation
and safe criteria precede pagination, so malformed or nonmatching candidates do not consume a page
or create duplicate offset behavior. Rows with malformed admitted metadata fail closed.

Action/date/actor/scope selection happens in SQL using existing indexes. Text matching evaluates only
bounded presented candidates in Python, with a cursor chunk size of 256 and a 100000-candidate scan
ceiling. Exceeding the ceiling returns a typed narrow-filters error, never a falsely complete partial
result. Queries select only the presentation fields and actor name parts. Sparse searches can be
more expensive than action/date filters. Representative local EXPLAIN measurements on 15101
synthetic events used the existing action/time, account and supervision indexes; no speculative
index, migration, PostgreSQL full-text search or external search service is justified.

Frontend criteria live in URL search parameters. Explicit search/apply/clear resets page; pagination
preserves criteria, and reload/back restores them. Approved FloatingListTools, list panels and
canonical pagination supply responsive and keyboard behavior. Initial loading, filtered/unfiltered
empty states, safe validation errors and retry are explicit. Transient refresh failure retains
last-known data with a warning; access loss hides it. CSV is disabled during pending/refresh/error
states and is never offered on self, supervised or Platform activity.

## DPO CSV authority, snapshot and audit

`privacy_governance.activity.export` is baseline-granted only to the DPO designation, and requires
effective `privacy_governance.view` through ADR-070 dependencies. A view-only account cannot export;
an export-only grant cannot create view authority; revoking view also disables export. No additional
MFA step is introduced for this read/export operation. Existing recent-MFA retention mutations are
unchanged.

`GET /api/v1/privacy/activity/export` (`privacyGovernanceExportActivity`) accepts exactly the list's
six criteria and no paging. One canonical PrivacyActivitySpec supplies both list and export. A
single ordered SQL cursor statement snapshot materializes the complete matching safe dataset before
the export audit is appended. Zero matching rows produce a header-only file. Up to **10000 rows**
export; the 10001st match causes `privacy_activity_export_too_large` (422), with no file, truncation
or success audit. A candidate scan overflow likewise fails without a file.

The file is UTF-8 `text/csv; charset=utf-8`, with standard CSV quoting and institutional ISO timestamps
including timezone offset. Columns are, in order: Occurred At, Category, Event Type, Title,
Description, Actor, Artifact, Format, Scope, Reference. Every cell passes spreadsheet-injection
neutralization, including leading `=`, `+`, `-`, `@` after whitespace or leading tab/CR/LF. The stable
filename is `COMPASS-Privacy-Activity-YYYYMMDD-HHMMSS.csv`; responses are attachments with no-store and
nosniff. The canonical frontend binary download helper receives a Blob; structured JSON errors stay
structured. CSV never serializes AuditEvent storage objects or the exported event contents as audit
metadata.

Before bytes can be released, the existing fail-closed release-audit helper must append the stable
`privacy.activity.exported` action, target `privacy.activityexport`, opaque UUID. Metadata is limited
to exported row count, category/type/date bounds and booleans indicating search/actor criteria.
Search terms, actor filter text, file contents and protected identifiers are not copied. Audit
failure returns `release_audit_unavailable` (503) without a CSV. The event's governance presenter
shows a static safe export fact in subsequent activity reads. It cannot join its own frozen export.
An earlier export fact may legitimately appear in a later matching export. The audit proves that the
server prepared the release; it cannot prove the recipient saved the downloaded bytes.

## Rollout and limits

No schema migration is needed. Deployment must run `sync_identity_policy` to install the two codes
and baseline grants. Export OpenAPI from backend source, then run normal Orval generation; generated
client files remain ignored/uncommitted. No live deployment, real provider disposition, retention
rule activation or policy decisions are part of this slice.

Future activity families, oversight scope, security visibility or export surfaces require explicit
presenter, capability, scope and privacy decisions with tests. Current direct scope, scan/export
ceilings, mutable display names and no historical supervision reconstruction are intentional limits.
The companion validation report records focused test results, baseline failures and local browser
checks without claiming repository CI or live deployment success.
