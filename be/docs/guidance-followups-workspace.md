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
backend recent-MFA requirements use the shared setup/verify continuation flow (MFA-UX-1).

Reports use the same scoped queryset. Counts include pending/completed/cancelled, overdue, the
reader-selected due horizon (default explicitly seven days), completed in an aware period (default
30 days, at most 366), and categories. These are reporting intervals, not institutional reminder or
retention policies. No descriptions, outcomes, source IDs or exports are part of aggregate reports.

RELEASE-UNBLOCK-1 retires `GUIDANCE_FOLLOWUPS_ENABLED`; it no longer controls workspace
availability. Verify current identity policy, resource authorization and the independently
provisioned web-only Follow-Up keyring before release. Protected content fails closed when keys
are missing or unusable. Keep external dispatch controls at their separately approved values.
Written institutional UAT approval remains a distinct prerequisite; no approval is inferred
from this change. See `guidance-followups-operations.md` and the RELEASE-UNBLOCK-1 report.

Validation evidence must identify exact commits. Source/UI integration does not imply Agent 2's
Service Catalog has been reconciled: Agent 2 is implementing those slices separately in Antigravity. Final readiness requires the
separate My Work/notification slice, security/browser regression and combined exact-candidate tests.
