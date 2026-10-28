# CONT-0 — Counselor case continuity audit

Status: source-verified architecture proposal; **no feature implementation or institutional approval**. Audit date: 2026-10-23 (Asia/Manila). Repository: `ils12058/COMPASS`.

## Verified baseline

`git fetch origin --prune` completed before worktree creation. Remote checkpoints matched the request:

| Reference | Verified SHA |
| --- | --- |
| `integration/ux15-modernization` | `5fddafec9e72ec987f6605533825e65795818b81` |
| `staging` | `0a843dae20c01984d0fb9aa46d5eef34102ab386` |
| `main` | `1a9933535a0b8c0cbd7764c35f301e8402f48375` |

Worktree: `/Users/reynantlntno/.codex/worktrees/cont-0-case-continuity/COMPASS`. Branch: `audit/cont-0-case-continuity`, created from the integration SHA above; PR target is integration. The primary checkout remained on staging with its pre-existing untracked files untouched. All current-behavior statements refer to this source snapshot, not deployed state.

## Findings and recommendation

1. **CONT-F01, high — audience mismatch confirmed.** Context selects a Student's published Shared Summaries across authors and decrypts their bodies. Its API requires `counseling.view_assigned`, not summary-view authority. Ordinary summary endpoints have narrower author/Student checks. Existing tests deliberately expect cross-author Context disclosure. CONT-1A should remove this Context section and endpoint, retaining author tools on the Encounter and the Student's published-summary workspace.
2. **CONT-F02, design boundary — preserve Context.** Exact provider/interaction identity plus a live time window authorizes Context, including across Colleges. Default windows are 24 hours before an Appointment, 24 hours of uncompleted grace, or seven days after a matching Encounter. This is neither permanent case ownership nor Head-wide access.
3. **CONT-F03, material disclosure boundary — Context is not uniformly minimal.** History is metadata only, but Inventory is the full Counselor detail projection, including sensitive submitted answers. Support indicators can disclose sensitive circumstances. Do not reuse the entire Context response as a continuity entitlement.
4. **CONT-F04, high migration risk — ciphertext identity is part of the rename.** Renaming a model/table does not transform the authenticated `counseling_shared_summary_id` binding. Ordinary key rotation preserves that binding. A coordinated reset/regeneration or verified decrypt/rebind/encrypt conversion is required.
5. **CONT-F05, readiness gap — continuity is absent.** No continuity grant, scoped approval workflow, Acting Head designation, or professional Handoff Summary exists. Current capability overrides can expire but do not themselves prove institutional delegation or Student-specific permission.
6. **CONT-F06, integration constraint — ownership must stay historical.** Appointments, Routine Interviews, Encounters, Follow-Ups, and E-Counseling have different assignment rules. A read grant cannot satisfy confidential Follow-Up **manage** eligibility or unblock linked Appointment reassignment.
7. **CONT-F07, hardening work — read revocation and cache controls need explicit design.** Current Context has frontend expiry clearing and server rechecks; new continuity requires its own per-read authority, concurrency and content-free audit contract. Inspected Counseling routes do not explicitly set private/no-store headers. No hosted-cache behavior was tested.
8. **CONT-F08, defense in depth — invalid persisted links.** Direct Context rejects a mismatched Encounter as a window extension, but overview displays the persisted Encounter link without the same matching predicate. Trusted writers validate links; this is a malformed-data projection risk, not a demonstrated remote write exploit. Track a narrow follow-up independently of the summary rename.

Adopt **one Student + one receiving Counselor + approved purpose + explicit selected source records + bounded interval + immediate revocation**. Keep Context and continuity as independent authorization mechanisms. Keep Student Session Summary, Counselor Handoff Summary and Routine Counselor Evaluation as separate resources. Approval does not confer professional-content access.

Primary non-production recommendation: a separately authorized **scoped destructive summary cutover plus synthetic regeneration**, preserving the canonical migration lineage and unrelated data/audit evidence. Disposable status and reset scope are conditions, not facts inferred about the live environment. Retained records require the data-preserving alternative.

## Audit package

| Document | Purpose |
| --- | --- |
| [Current architecture](current-architecture.md) | Domain ownership, relations and source evidence |
| [Context audit](counseling-context-audit.md) | Activation, invalidation, cross-College projections |
| [Confidential access matrix](confidential-access-matrix.md) | Current actors, resources, capabilities and evidence |
| [Student Session Summary audit](student-session-summary-audit.md) | CONT-1A correction and complete rename plan |
| [Rename file inventory](rename-inventory.csv) | Every tracked baseline file matching old terminology, exact lines and disposition |
| [Encryption and cutover](encryption-and-cutover.md) | Cryptographic identities, reset/retain routes and rollback |
| [Authorization design](continuity-authorization-design.md) | Proposed model, service boundaries, approval and races |
| [Source record policy](source-record-policy.md) | Allowed, selected, excluded and undecided projections |
| [Handoff workflows](handoff-workflows.md) | Planned/unplanned workflows, UI and notifications |
| [Threat model](threat-model.md) | 24 adversarial cases, regression tests and residual risk |
| [Implementation plan](implementation-plan.md) | CONT-1A through CONT-4 specifications |
| [Institutional decisions](institutional-decisions.md) | Unapproved policy defaults and release gates |
| [Validation](validation.md) | Reproducible checks, executed versus inspected tests, limitations |
| [Final recommendation](final-recommendation.md) | Risk disposition and precise next task |

Proposal #6 was inspected in the local **COMPASS Development Proposal Notes — Fifteen Proposals** Markdown, lines 3837–4680. Its historical staging findings were rechecked against integration. This request supersedes its proposed rolling compatibility/legacy-alias approach and broader permanent-transfer suggestions: final active contracts have one name and no permanent aliases. Source evidence and validation details are recorded below; no legal conclusion or institutional policy is inferred from proposal wording.

Next task: **CONT-1A only**, with backend denial tests first. Do not bundle new confidential source access, a cryptographic rename, or operational reset into that correction.
