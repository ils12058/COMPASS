# Dedicated authority and recent MFA

[accounts/policy.py](../../be/compass/accounts/policy.py) registers `organization.catalog.manage`
with `organization.structure.view` as a prerequisite. No role/designation baseline grant contains it.
Identity synchronization installs the capability definition, not editor assignments. IT Admin,
Counselor, GSS and Head designation alone are insufficient. `organization.manage` remains a separate
operational relationship capability. No actual user grants are created by this change.

The technical eligible-role fence is active IT_ADMIN / COUNSELOR / GUIDANCE_SERVICES_STAFF.
[accounts/services.py](../../be/compass/accounts/services.py) suppresses the capability for unsupported
roles, including malformed direct-ORM grants. Both low-level override assignment and protected
Account Management reject granting it to unsupported roles. Existing prerequisite suppression,
revocation and expiry apply. Switching to an unsupported role makes a retained override unusable.
Eligible roles are a technical ceiling; choosing actual delegates remains an institutional decision.

HTTP calls retain canonical cookie session authentication and CSRF. The API checks catalog authority
and existing step-up semantics before calling protected services. The service independently acquires
the exclusive gate, reloads/locks the active actor, checks the role and effective capability, then
locks the confirmed active TOTP factor before AuthSession, matching authentication's existing order.
The session must belong to the actor, be unexpired/unrevoked and retain the authenticated credential
digest. A rotated credential invalidates an earlier resolved session object. Caller-supplied session
field values cannot replace persisted MFA evidence. A recent timestamp without an active factor is
insufficient. The Audit actor must match the current authenticated actor.

Missing factor yields `mfa_setup_required`; stale/future verification yields `recent_mfa_required`;
invalid actor session yields 403 `invalid_session`. Standard HTTP authentication may return 401
before the domain boundary for a missing/expired/revoked cookie. The service reloads time-sensitive
authority/session evidence again before the transaction exits, after any waits/domain work. Failures
roll back the catalog row, version and success Audit. Locks linearize supported grant revocation,
role/account changes, session revocation and factor disabling with the protected mutation.

Negative tests cover each role without a grant, synthetic eligible grants, malformed unsupported
role grants, Account Management override rejection, dependency revocation, expired/revoked override,
inactive actor, stale actor cache, foreign/missing/expired/revoked/rotated session, missing factor,
stale MFA, persisted evidence versus a forged in-memory verified timestamp, mismatched Audit actor,
CSRF and strict rejection of `mfa_verified` fields. Independent-connection tests cover revocation
and stale MFA while the catalog mutation waits.

Catalog authority does not imply Accounts management, relationship management, global Audit,
Student affiliation mutation or confidential Inventory/Counseling/Assessment/Good Moral access.
Existing role-derived privileges remain their own authority; this new capability adds none of them.
No GSS inheritance, Head designation or provider-owned confidentiality rule is changed.
