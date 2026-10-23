# Concurrency and content-release boundary

The source-read coordinator uses an outermost **durable** PostgreSQL transaction. It cannot return prepared plaintext into an uncommitted outer transaction. PostgreSQL READ COMMITTED is required explicitly; unsupported coordination/isolation fails closed. A transaction-local one-second lock timeout bounds intentionally waiting locks and Audit lock waits; source/authority conflicts do not retry automatically.

## Order and authority fence

1. Transaction-scoped shared advisory policy-publication fence (dedicated two-integer key, not a bearer permission).
2. Deterministic ascending-UUID User row locks for the exact receiver, Student and current approval actor. Historical original/requester identity is provenance, not a current activation predicate. User locks may wait, then backend time is recomputed.
3. Exact receiver-filtered Grant and sorted Scope locks, using NOWAIT. An unrelated Grant is filtered before locking, avoiding contention-based existence disclosure. A newly changed approval identity that was not in the initial lock set yields controlled conflict rather than acquiring an out-of-order User lock.
4. `LOCK TABLE ... IN SHARE MODE NOWAIT` on the fixed authority inventory below. Refresh User/Role data afterward: role definitions might have changed while User locks were being acquired. These table locks prevent ordinary DML updates/deletes **and missing-row insert phantoms**, including a new explicit REVOKE.
5. On HTTP calls, NOWAIT lock the exact current AuthSession by ID and original credential digest. Session rotation, revocation and expiry are rechecked.
6. Exact source rows/dependencies using NOWAIT: Encounter → Service/Appointment; or Routine → linked Encounter → Service/Appointment. Source-owned metadata/lifecycle/revision checks precede ciphertext retrieval.

All post-User acquisitions are non-waiting where they could invert existing writer order. Existing Routine/Encounter writers sometimes lock source before User; a busy source produces 409 instead of a reverse-order wait. Authority SHARE acquisition similarly refuses an in-progress relation writer rather than waiting while holding User locks. Locks acquired before a failed check are released by rollback; no partial Audit or source mutation remains. Ordinary existing writers are not rewritten or granted new authority.

## Relevant writer inventory and synchronization

| Authority/input | Existing application-managed writers inspected | Read protection |
| --- | --- | --- |
| User activity, primary role, Student lifecycle | `account_management.services.set_account_active/change_role/set_student_lifecycle`; CSV/account creation; `staging_seed/accounts.py`; User ORM updates | Same relevant User row locks, then fresh role projection; PostgreSQL UPDATE/DELETE also acquires conflicting row locks even without an explicit writer SELECT |
| User overrides, designation assignments | `account_management.services.set_capability_override/remove_capability_override/assign_designation/remove_designation`; `accounts.services.set_user_capability_override`; seed assignments | SHARE locks on accounts_usercapabilityoverride and accounts_userdesignation, covering insert/update/delete and absence phantoms; existing administrative session invalidation unchanged |
| Canonical roles, designations, capabilities, role/designation grants | `accounts.bootstrap.sync_identity_policy` and its grant/retirement reconciliation | SHARE locks on accounts_role, accounts_designation, accounts_capability, accounts_rolecapability and accounts_designationcapability; no per-reader parallel permission store |
| Student affiliation, active office scope | `organization.services.set_student_affiliation/remove_student_affiliation`; `organization.bootstrap.sync_organization_catalog` and its catalog repair/retirement helpers; seed affiliation writers | Student row plus SHARE locks on organization_studentaffiliation, organization_college and organization_campus; unchanged College/timestamp marker required |
| Grant state/version/scope | `continuity_services.request_coverage/decide_coverage` | Shared relevant User/Grant ordering; Grant/Scope locks and sealed snapshot; terminal revocation prevents new reads |
| Evaluation, Encounter and related source state | Routine creation/intake/evaluation/finalization/linking, Counseling create/update/link, Appointment lifecycle/reassignment and Service mutation services; rotation commands | Exact source/dependency row locks; NOWAIT conflict for source-first writers; revision/lifecycle checks; ordinary finalized Evaluation immutability remains authoritative |
| HTTP session validity | Authentication session revoke/rotate/security invalidation | Locked session ID + current digest, actor, unrevoked state and live expiry; no token returned |
| Operational/disclosure policy validity | No deployed approved provider or publication service exists | Shared advisory fence for reads; future publication/invalidation must use `continuity_policy_change()` exclusively before any provider-visible change and hold it through commit |

The fixed authority relation inventory is exactly the ten table names listed above. No caller-provided table/model/SQL identifier is accepted. These conservative table locks can briefly block an unrelated authority update, or return a bounded conflict if a writer already holds its DML lock. User/approver locks also serialize some otherwise independent reads. Local correctness evidence is not a production contention benchmark.

## Release linearization

Within the transaction, authorize receiver/capabilities, both policies and their bound digests, effective Grant/version/seal, Student/office conditions, exact source scope and source-owned revision/lifecycle. Reauthorize after source locks, then decrypt only the Evaluation section and construct the approved typed projection. Recheck current time/policy/authority, append the synchronous safe source-read Audit event, and **recheck once more after Audit insertion**. This last successful check is the authorization linearization point. If time/policy/session/authority fails after preparation or an Audit wait, roll back the event and return no body. Only successful transaction commit lets the projection return to the API.

If revocation or a relevant authority/source writer commits first, a later read observes the changed state or a bounded conflict before decryption. If an authorized read linearizes/commits first, the writer may complete afterward; the earlier release was legitimate. A response can arrive later than commit/expiry/revocation. Neither network arrival nor a successful Audit event proves that the person read the content, and previously delivered information cannot be recalled.

## Proven boundaries and remaining blockers

Real PostgreSQL tests cover actual account-management deactivate/role/lifecycle/override/designation flows, affiliation changes, Grant revocation, source updates, every authority relation's DML fence, REVOKE insertion into a previously absent override row, writer-first conflicts, policy-fence invalidation in both orders, a real User lock wait past exact expiry, source/User inversion, unrelated-Grant contention concealment, concurrent reads and concurrent Audit failure. Thread connections close explicitly; no mocked lock or SQLite result is offered as proof.

Ordinary PostgreSQL row/table DML locking protects the inspected account/organization paths without requiring every writer to call a new helper; tests also exercise direct ORM DML. This is **not universal protection against arbitrary privileged SQL, schema/trigger rewriting, fabricated policy evidence, mixed application versions or a provider that changes external/file/cache state outside the publication fence**. A future provider must use authoritative transactionally visible storage, synchronize all publication/invalidation through the same database fence, avoid stale allow caches and verify real evidence. The current synthetic mutable provider is a test fixture, not such a deployment implementation.

No real provider is approved or implemented, and both default providers return None, so these unresolved institutional/provider/deployment conditions cannot silently activate an affected pathway. Schema/consumer/key coordination and policy-provider verification remain release blockers before real-world disclosure. No deployment, migration, provider activation or live concurrency experiment is authorized here.
