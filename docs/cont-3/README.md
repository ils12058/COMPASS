# CONT-3 — Case coverage and confidential Counselor Handoff

Verified starting integration SHA: `dedf1a649c8adb4f8a5508a513d8bf0dd994fa1d`. Managed isolated worktree `cont-3-counselor-handoff/COMPASS`, branch `feature/cont-3-counselor-handoff-workflows`, target `integration/ux15-modernization`. Final implementation SHA/publication state belong on the PR. No automatic merge or deployment.

The Counseling workspace now links to Case coverage: contextual planned requests, exact policy-authorized office cases for unexpected absence, independent metadata-only decisions, receiver review of selected CONT-2B projections, and an optional distinct encrypted Counselor Handoff. Original author, requester, approver and receiver remain separate identities. Coverage does not change ordinary source ownership, Context, Appointments, Follow-Ups, or Student Session Summary audiences.

**Default runtime remains unavailable.** Operational, disclosure and new coverage/Handoff workflow providers all return None. No flags, Head designation, capability overrides or technical key provisioning replace verified institutional evidence. Positive workflows use explicit synthetic fixtures only. Existing metadata-only/CONT-2B policy digests remain compatible when the new workflow binding is empty; they cannot authorize Handoff or new selector access.

Implementation record:

- [Planned/unexpected workflows and metadata selection](coverage-workflows.md).
- [Handoff domain, audience, versioning and migration](handoff-domain.md).
- [Independent keyring, authenticated binding and rotation](handoff-encryption.md).
- [Protected client state and accessible UX](frontend-safety.md).
- [Deferred notices and synchronous content-free Audit](notifications-and-audit.md).
- [Executed validation and limits](validation.md).
- [Institutional/deployment gates and CONT-4 handoff](release-gates.md).

Historical CONT-0 through CONT-2B documents are preserved as historical evidence. A technical implementation is not GCO/UCN approval, real-key recovery verification, institutional UAT, hosted CI, deployment, or live disclosure proof.
