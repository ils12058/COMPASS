# Authorization and recent MFA

`institution-access.ts` separates canEnterOrganization, canManageOrganization and
canManageOrganizationCatalog. Eligible staff with structure.view can browse. Catalog actions also
need the exact new capability. Relationship routes and tabs still require organization.manage.
Students retain reference API/selector behavior without a standalone administrative destination.
No baseline grants, authority bypasses, broad feature flags or backend permission changes were made.

The editor reads the current server session before review and immediately before submission,
comparing both account UUID and session UUID, and rechecking effective Catalog authority. The
backend still decides every request and MFA requirement. Changed owner unmounts all protected local
state; revoked capability removes controls/editor. An invalid/unconfirmed session stops submission.

`mfa_setup_required` and `recent_mfa_required` use existing StepUpDialog. Catalog does not use the
retained-operation useStepUpContinuation. The existing relationship helper remains unchanged.
After a refusal the review closes and local values remain. Verification performs only session and
record/impact reads, then explicitly asks for review and another confirmation. No retained command
is called by the verification callback; mutation retry is disabled.

Two optional shared-dialog props preserve existing defaults elsewhere:

- setupInNewTab: the existing Account Security setup link opens a separate tab with an announced
  destination; the Catalog form stays in memory in its original tab. Return to change closes the
  prompt. The next review rechecks current account/session, parent/target and impact.
- reviewAfterVerification: authenticator wording states that the person will review the latest
  details before submitting, and pending text describes loading rather than automatic mutation.

No new authenticator API, code storage, token or authentication subsystem exists. Actual setup
occurs exclusively through Account Security. Codes remain the shared dialog's transient state.
Deliberately navigating away can discard the local draft through the existing guard; no
institutional draft is written to localStorage/sessionStorage. A new session/account always clears it.

A recent-MFA timestamp or client verification is never added to a Catalog request. Setup completion
in another tab does not itself approve a mutation. If policy/version/dependencies change during
security verification, the next review must show authoritative current state and the backend may
still refuse. Real delegate appointment and institutional MFA/UAT approval remain separate gates.
