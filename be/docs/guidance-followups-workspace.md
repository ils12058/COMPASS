# Guidance Follow-Up workspace and API integration

This dependent slice builds on FUP-1A PR #259. It implements FUP-1B/FUP-1C and the bounded
operational report portion of FUP-1E. My Work and staff notification producers are separate slices.

The workspace uses `/portal/follow-ups`, `/new`, `/{id}` and `/report`. The generated OpenAPI/Orval
contract owns every request. Staff selectors are domain-owned: no Accounts-directory shortcut.
Student selection is scoped to active current Students in operational responsibility (Head has
operational institutional scope). Confidential source contexts require the existing Counselor
relationship; assignment never creates that relationship. Confidential creation/assignment offers
only the source's authorized Counselor. Every submission independently rechecks source/recipient
and effective capabilities. GSS's persisted code is `GUIDANCE_SERVICES_STAFF`.

Lists contain only records currently assigned to the reader and authorized by current resource
policy. Assignee filters narrow that set; they do not grant oversight. Due-date filters/order run
before bounded pagination. Source context returns only an authorized canonical Encounter, Referral
or Routine Interview. Dedicated source pages share one contextual component. E-Counseling reaches
the same canonical Counseling Encounter; rooms/media/transcripts are never Follow-Up sources.
An operational follow-up survives Referral voiding, with unavailable source navigation suppressed.
Confidential access is removed if the source relationship is lost. No Follow-Up action changes the
source's lifecycle or creates another professional record.

Detail exposes encrypted content only after current authorization and supplies actor names and
terminal provenance. History is paginated at 20 events. Creation freezes an unconfirmed submission
and its durable key for Retry. Edits retain input on conflict; a fresh saved version must be reviewed
before a new attempt. Complete/cancel/reassign use the standard consequential confirmation. Retained
backend recent-MFA requirements use the existing setup/verify flow and never replay actions.

Reports use the same scoped queryset. Counts include pending/completed/cancelled, overdue, the
reader-selected due horizon (default explicitly seven days), completed in an aware period (default
30 days, at most 366), and categories. These are reporting intervals, not institutional reminder or
retention policies. No descriptions, outcomes, source IDs or exports are part of aggregate reports.

Configuration: keep `GUIDANCE_FOLLOWUPS_ENABLED=false` until web-only independent keyring provisioning
and rollout are approved. No new secret is generated or installed by this implementation. Workers,
Beat and realtime must not receive the Follow-Up content keyring. Preserve ordered old keys during
rotation; use record-bound codecs and tested backups. Existing canonical baseline bytes are pinned
and the new domain migration is explicitly registered. No baseline reset or data reseeding is needed.

Validation evidence must identify exact commits. Source/UI integration does not imply Agent 2's
Service Catalog has been reconciled: that work has not yet started. Final readiness requires the
separate My Work/notification slice, security/browser regression and combined exact-candidate tests.
