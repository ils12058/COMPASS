# Privacy Notices and Privacy & Security Activity

The canonical application baseline separates administrative Notice access from curated Activity.

| Default identity | Notices view | Notices manage | Activity view | Activity export |
| --- | --- | --- | --- | --- |
| IT_ADMIN | Yes | Yes | Yes | Yes |
| HEAD_GUIDANCE_COUNSELOR designation on COUNSELOR | No | No | Yes | No |
| INSTITUTIONAL_OFFICER | No | No | No | No |
| Other roles/designations | No additional grants | No additional grants | No additional grants | No additional grants |

Capabilities are `privacy_governance.notices.view`, `.notices.manage`, `.activity.view` and
`.activity.export`. Notice management requires effective Notice viewing; export requires effective
Activity viewing. Dependencies never grant the prerequisite. Notice viewing and Activity viewing
are independent. Only the actual Head Guidance designation adds Activity viewing to a Counselor.

IT Administrator is the sole default in-app Notice manager. It maintains institutionally approved
wording, creates and edits drafts, reads revision history, publishes and retires Notices. Publication
and retirement retain recent MFA. This assignment does not confer institutional privacy-policy
authority or introduce an application approval workflow.

Public/applicable published readership and exact-revision own acknowledgments remain independent
of all four administrative capabilities. Acknowledgment is not consent. Existing concurrency,
immutability, validation, publication timing, provenance and synchronous audit protections remain.

Activity preserves its closed minimized projection, pagination, filters and independently audited
CSV export. Head Guidance needs no Notice API to land in or use Activity, sees no draft links and
has no default export. No Activity or export operation can edit or delete audit evidence. Historical
retention event presenters/action identifiers remain only to read existing append-only evidence;
there is no policy register or management operation behind them.

The former application designation and Retention Policies feature are absent from the canonical
policy, API, routes, contracts, current personas and operating scenarios. Old URLs use ordinary
not-found behavior. Existing model definitions and baseline schema migrations remain unchanged.

Fresh installation/rebuilt database only: run the ordinary migrations and `sync_identity_policy`,
then seed using the existing dataset command if needed. No upgrade, account conversion, grant
cleanup, migration, compatibility mechanism, cutover or change-specific reset tooling is provided.
Deleting source definitions does not delete assignments/grants from populated databases.

Institutional privacy contacts in approval/decision documents are external reviewers, not application
identities. Historical test/CI evidence keeps its originally recorded outcomes and is not a claim
about current access. User output folders and Git/audit history are not rewritten.
