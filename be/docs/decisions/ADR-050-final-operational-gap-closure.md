# ADR-050: Final Operational Gap Closure

- **Status:** Accepted
- **Date:** 2026-09-20

## Context

COMPASS already provides password setup and recovery through email OTP, TOTP MFA,
recent-MFA step-up, revocable sessions, trusted-browser state, and verified email
change. It did not provide a deliberate authenticated password-change workflow.

Appointment administration also remained institution-wide whenever
`appointments.manage` was present. Guidance Services Staff need to assist with
Appointment operations, but capability possession alone must not expose Appointments
outside the Colleges currently handled by their supervising Counselor.

This is the final planned backend functional slice before defense preparation.
After this slice, planned backend functional scope is frozen except for defects,
UAT blockers, security defects, and explicit stakeholder-required corrections.

## Decision A — Authenticated password change

COMPASS exposes `POST /api/v1/auth/password/change` as a dedicated authenticated
operation rather than routing deliberate password changes through anonymous password
recovery.

Authorization depends on current MFA policy:

- If `mfa_required_for_user(user)` is true, the account must have an active TOTP
  factor and the current AuthSession must satisfy existing recent-MFA policy.
  Email OTP and current-password fallback do not replace required TOTP.
- If MFA is not required, the user must prove the current password. Failed attempts
  use the existing authentication rate-limit infrastructure and do not log submitted
  credentials.

The new password reuses the same password-policy validator as setup/recovery,
including Django password validation, maximum length, and exact-current-password
reuse rejection.

The mutation is atomic. On success COMPASS:

- changes only the password;
- retains the current AuthSession;
- revokes all other AuthSessions;
- revokes all TrustedSessions;
- invalidates pending LoginChallenges;
- invalidates password-recovery and initial password-access email OTP challenges;
- preserves TOTP factors and recovery codes;
- records `auth.password.changed` with only the safe method
  (`recent_mfa` or `current_password`);
- creates the mandatory `security.password.changed` notification.

A deliberate password change remains semantically distinct from
`auth.password.reset` / `security.password.reset`.

## Decision B — Scoped Guidance Services Staff Appointment management

`GUIDANCE_SERVICES_STAFF` receives the existing `appointments.manage` capability.
The capability does not by itself confer institution-wide record access.

Appointment administration uses a small Appointment-local resource-scope resolver:

- Head Guidance Counselor: institution-wide;
- ordinary Counselor with `appointments.manage`: Colleges in that Counselor's
  current active `CounselorResponsibility` rows;
- Guidance Services Staff with `appointments.manage`: Colleges in the active
  supervising Counselor's current active responsibilities, resolved through
  `StaffSupervision`;
- unsupported roles with accidental or stale capability overrides: empty scope.

For Guidance Services Staff, supervision by Head Guidance does **not** inherit Head's
institution-wide authority; only the supervisor's explicit responsibility Colleges
are inherited.

College scope is applied through the Appointment Student's current
`StudentAffiliation`. Active College and Campus state is required. Authorization is
resolved at request time and is not snapshotted into Appointment rows.

The same scope is enforced before managed-list filters/pagination, on direct
Appointment GET, and on administrative cancellation. Out-of-scope direct access is
concealed as not found. Administrative cancellation retains the existing
`appointments.manage` + recent-MFA API rule.

Student self-service and provider self-view remain separate from administrative
scope. Guidance Services Staff remain non-provider operational administrators: this
change does not broaden provider eligibility, Counseling access, Availability
provider authority, or E-Counseling provider authority.

## Consequences

- Password change has a purpose-built strong-auth and audit/notification contract.
- The current browser remains usable after password change while reusable access from
  other sessions and trusted browsers is removed.
- Guidance Services Staff can assist with Appointment administration without
  cross-College leakage.
- Capability overrides for ordinary Counselors remain resource-scoped rather than
  becoming institution-wide authority.
- Head Guidance retains institution-wide Appointment oversight.
- Existing Appointment routes and operation IDs are preserved.
- No generic cross-domain authorization-scope framework is introduced.
- No new backend functional domain is planned after this slice before defense.
