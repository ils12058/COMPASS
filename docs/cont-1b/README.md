# CONT-1B — Student Session Summary contract cutover

Starting integration SHA: `0ba5024a8468b3e27b2b1b3723cf431bf0390f61`. Branch `feature/cont-1b-student-session-summary`, isolated managed worktree. Target: `integration/ux15-modernization`. This implements the [CONT-0 plan](../cont-0/README.md) after [CONT-1A](../cont-1a/README.md); those historical records remain unchanged.

The active resource is now `compass.counseling.StudentSessionSummary`, table `counseling_studentsessionsummary`, reverse relation `student_session_summary`, with one encrypted draft/publication per Encounter. UUIDs, Encounter-derived author ownership, publication immutability/idempotency and Student own-published access retain their behavior. No historical summary read is available through Counseling Context, including another College's exact provider, direct anchors or a Head provider. No continuity or handoff authority is added.

The coordinated change covers service/content/rotation modules, API schemas/operation IDs/errors, capabilities, future audit emitters, Notification source/target/event/template/link contracts, Compose/runtime secret inventory, frontend route/components/Help, synthetic seeders, tests and CI selection. The old ordinary API/frontend routes and forwarding modules are removed. Generated clients remain ignored.

Canonical endpoints:

- Student: `/api/v1/counseling/me/student-session-summaries[/{summary_id}]`.
- Author: `/api/v1/counseling/encounters/{encounter_id}/student-session-summary[/publish]`.
- Frontend detail: `/portal/counseling/student-session-summaries/[summaryId]`.
- Capabilities: `student_session_summaries.view_self`, `.view_assigned`, `.manage_assigned`.
- Publication: `counseling.student_session_summary.published`; Notification source `student_session_summary`, target `STUDENT_SESSION_SUMMARY`, audit target `counseling.studentsessionsummary`.

Additive registered migrations: `accounts.0002_student_session_summary_capabilities` and `counseling.0002_student_session_summary_contract`. Canonical baseline files/hashes remain unchanged. The new schema also names the PK, Encounter uniqueness/backing index, FK and ciphertext-presence constraints consistently. Capability identities are renamed in place, preserving grant/override foreign keys, effects, reasons, timestamps and expiries. Mixed old/new collisions abort before mutation; normal policy sync refuses unconverted legacy rows. Affected users' reusable authentication state is invalidated through the established account authority-change mechanism. Runtime evaluation accepts only canonical capability codes.

The schema migration refuses legacy summaries or publication Notifications. Scoped disposable cleanup is a separate explicit operator action; no migration deletes content. Historical append-only AuditEvent rows are retained. The new adapter accepts only the new authenticated binding, so retained old tokens cannot accidentally become readable after a setting/table rename.

Implementation and operational boundaries:

- [Rename verification](rename-verification.md), [127-file checklist disposition](rename-disposition.csv), and [remaining historical references](historical-reference-allowlist.csv).
- [Encryption contract](encryption-contract.md).
- [Migration/cutover and recovery runbook](migration-and-cutover.md).
- [Executed validation and limits](validation.md).

Code and local synthetic rehearsal are separate from staging readiness. No deployed database, data, key, worker or service was accessed or changed. No SSH, deployment, merge, `staging` or `main` update is authorized by this implementation. Live key provisioning, data-classification approval, consumer fencing, backup/recovery and coordinated release remain operational prerequisites.
