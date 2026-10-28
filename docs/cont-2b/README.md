# CONT-2B — Selected professional source reads

Repository `ils12058/COMPASS`. Verified starting integration SHA: `7afd4a41fe0a02b9723b5b4d22036beaef86f514`. Isolated managed worktree `cont-2b-confidential-source-access/COMPASS`, branch `feature/cont-2b-confidential-source-access`; target `integration/ux15-modernization`. Final implementation SHA and publication status are on the PR.

This adds two independent, read-only selected-source operations: one completed Counseling Encounter structural projection and one finalized Routine Counselor Evaluation projection. They require an exact receiving Counselor, effective sealed Grant/version/scope/revision, current account/Student/organization authority, operational policy **and separate field-level disclosure approval**. Ordinary author-owned getters and mutations remain unchanged. No Context object, source ownership, responsibility, reassignment or Handoff document is manufactured.

**Default runtime still denies every new disclosure.** Both `get_approved_policy()` and `get_approved_disclosure_policy()` return None. No environment flag, route, capability override or Head designation activates either provider. Test-only policy fixtures exercise actual encrypted Evaluation reads on isolated synthetic PostgreSQL. They are not institutional sign-off.

The operational policy may now bind a disclosure-policy digest inside its existing digest. That digest is already sealed into Grant provenance, so changing permitted fields, evidence, lifecycle/revision rules, dates or scope requires a new request/approval. Empty binding preserves all CONT-2A metadata-policy digests and cannot authorize a source read. There are **no schema changes or new migrations**; Grant/Scope models, canonical hashes and CONT-1B/2A migrations remain unchanged.

The read transaction coordinates supported identity and authority mutations using existing ordered User locks plus short PostgreSQL SHARE locks on a fixed authority-table inventory, preventing missing-row REVOKE phantoms as well as updates/deletes. Sources retain NOWAIT locking. Policy publication/invalidation has a dedicated transaction-scoped advisory fence. The final post-Audit authority/time check is the authorization linearization point; successful transaction commit precedes returning the prepared projection. A later browser arrival does not imply authorization after expiry or recall of previously viewed content.

Implementation record:

- [Per-read authorization and safe denials](authorization-contract.md).
- [Exact field inventories and source-owned adapters](source-projections.md).
- [Writer inventory, locking, release boundary and limits](concurrency-and-release.md).
- [Audit, privacy and no-store](audit-and-privacy.md).
- [Executed validation](validation.md).
- [CONT-3 prerequisites](cont-3-handoff.md).

Historical [CONT-0](../cont-0/continuity-authorization-design.md), [CONT-1A](../cont-1a/README.md), [CONT-1B](../cont-1b/README.md) and [CONT-2A](../cont-2a/README.md) records are preserved. Their prospective whole-Evaluation recommendation is narrowed here: no field is released without its own explicit approved V1 inventory. No frontend screen/navigation, notification event, source export, deployment, SSH, live migration/reset, real key operation or automatic merge belongs to this slice.
