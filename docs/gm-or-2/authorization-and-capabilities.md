# Authorization and capability governance

Canonical definition: `good_moral.verify_receipt`, with dependencies on `good_moral.view` and `good_moral.prepare` through the existing dependency resolver in `accounts/policy.py`. The existing policy synchronization command publishes the definition. **No role or designation baseline grant changes.** No account grants are migrated or seeded by GM-OR-2.

The service and API require an active saved account whose base role is COUNSELOR or GUIDANCE_SERVICES_STAFF and whose current dependency-coherent capabilities include the new capability. Audit actor must match the authenticated operator. Tests explicitly grant temporary synthetic inspectors through `set_user_capability_override`; these grants are neither an institutional grant matrix nor production instructions.

Counselor/GSS without the explicit capability, missing dependencies, revoked/expired overrides, deactivated users, Student and IT Admin are denied. Head Guidance designation does not imply inspection authority. IT capability administration does not make an inspector. Preparation retains its existing Counselor/GSS permission. Final issue always requires active COUNSELOR plus `good_moral.issue`, including when GSS/IT/Student has an unusual override. The inspector and preparer need not be the issuer.

Mutations refresh authority after the request fence. Inspection and active preparation/issuance lock the acting User row, sharing the normal override/account-management identity lock, and freshly recheck before returning from the transaction. A concurrent deactivation or supported override change that wins the account lock is seen; one that loses waits until the authorized action commits. Expiry is evaluated again using current server time. Active F4 issuance acquires acting Counselor and Student together in the existing account-management UUID order, retaining the Student CURRENT recheck.

This does not claim serializable authorization against a privileged direct override-table write, a role/designation policy synchronizer that ignores User locks, or an account change after the last check by such a writer. Supported account management locks actor/target identities; code-owned capability synchronization requires a controlled release/writer drain. Tests cover both commit orders for normal revocation/deactivation. No unrelated account-governance locks or blanket privileges are added.

Real inspectors need GCO-approved named/delegated grants, training and retention/access decisions before activation. No real grants were made.
