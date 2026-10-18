# COMPASS-MFA-UX-1 Implementation Report

## Initial architecture findings

This section records the pre-change audit before any shared MFA component was modified.

### Authentication and authorization

- `be/compass/authentication/step_up.py` translates backend `MFASetupRequired` and `RecentMFARequired` conditions into the distinct `403 mfa_setup_required` and `403 recent_mfa_required` responses.
- Recent verification is recorded on the authenticated server session. The session API and MFA status API expose recent/enabled state; the authenticator code and server-side verification material are not returned to the portal.
- The protected API handlers check role/capability authority and recent MFA before calling their domain mutation. The reviewed boundaries include account management, appointment reminders, group sessions, Guidance Follow-Ups, academic years, organization assignments, platform maintenance, privacy notice publication/retirement, and service catalog administration.
- Password, email-change, and authenticator security mutations keep their recent-MFA checks in the backend security/domain flow. Email identity is not committed before new-mailbox verification. Session invalidation remains server-owned.
- ADR-012 and ADR-049 confirm the server-managed session and proof boundaries. Frontend visibility is not authorization; backend capability and recent-MFA checks remain mandatory.

### Existing frontend behavior

- `stepUpRequirement` maps the two backend error codes but currently accepts them without checking that the HTTP status is 403.
- `StepUpDialog` verifies the TOTP code, closes, and then invokes a synchronous optional callback. It does not wait for an action to finish, report action completion, or prevent action cancellation while a continuation is running.
- Account, organization, institutional configuration, and service action helpers retain callbacks that reopen an earlier confirmation. Their user-facing notices ask the person to submit or confirm the same action again.
- Platform and Privacy Governance helpers show a manual-resubmission notice but retain no action. Follow-Up actions similarly leave the person to resubmit.
- Password change can ask for MFA before its mutation, but successful verification only changes local recent-state; the person still presses the submit button. The controlled password fields remain on the page.
- Authenticator disable/recovery-code regeneration ask for MFA before showing the consequential confirmation, then require selecting and confirming the action again.
- Appointment reminder sending handles the backend refusal through mutation error state and has no continuation. Its request key and confirmed selection are retained in the UI.
- Staff Group Session writes have backend recent-MFA enforcement, but their frontend handlers have no shared StepUp handling. Student registration/cancellation are outside this boundary and must remain unchanged.
- Existing automated coverage checks error-code mapping, static dialog copy, and feature allowlisting. It does not exercise a successful one-time continuation or the Group Session gap.

### Root cause and continuation safety

The backend intentionally rejects a protected request before the domain operation when recent MFA is missing. The frontend treats that refusal as a prompt to repeat the interaction, rather than retaining the already confirmed operation. The continuation can therefore retry only the first exact `403 recent_mfa_required` response. Setup requirements, permission failures, conflicts, network failures, malformed responses, and later failures must not trigger a replay.

The pending continuation will be an in-memory, one-shot callback bound to the current account and authenticated session. It may retain the confirmed operation's non-secret inputs and existing idempotency/version context. It will not contain TOTP codes, passwords, recovery codes, email verification codes, or other authentication secrets and will not use browser persistence. Cancellation, expiry, unmount, or account/session change clears it. A resumed mutation is dispatched once; the backend remains authoritative and a subsequent error is terminal for that continuation.

## Implementation and validation

### Implemented behavior

- Added a shared in-memory, one-time continuation controller for requests rejected with the exact `403 recent_mfa_required` response. It keeps the confirmed action for at most five minutes, consumes it before one continuation attempt, and never persists it in browser storage.
- After TOTP succeeds, the controller refreshes the authenticated session and checks the same account and session before dispatching the action. Cancellation, expiry, setup requirements, session changes, and component unmount discard the pending action. A second refusal, permission error, conflict, or network failure is terminal; it does not trigger another automatic request.
- The pending controller stores an operation callback, not password/TOTP/recovery-code values. Password and email forms keep sensitive values in their existing component state and callbacks read them only when the user completes verification. The TOTP dialog clears its code after successful verification and has an in-flight guard against repeated verification submissions.
- Updated the shared dialog to explain that the confirmed action will continue, show verification/continuation progress, prevent dismissal while busy, and await the actual operation result before the caller shows success. An account with no authenticator is sent to setup; the prior privileged action is not retained across setup.
- Preserved backend authorization, capability, recent-MFA, audit, rate-limit, and session-invalidation checks. No backend or API contract changed.

### Workflows covered

- Account creation, account access and security management, account import, roles/designations/capability overrides, and account-level authenticator operations.
- Password change and self-service email-change challenge, request, and confirmation. The email-change session invalidation and sign-out redirect still happen only after the backend confirms the mailbox change.
- Organization responsibilities and student affiliations; academic-year administration; Service Catalog administration; Platform Operations; Privacy Governance.
- Appointment reminder issuance; Guidance Follow-Up creation, editing, reassignment, and other lifecycle actions; staff Group Session writes, including attendance.
- Student Group Session registration and cancellation remain outside step-up because the backend does not require recent MFA for those actions.

Existing confirmation boundaries remain. Where a feature closes its review dialog when step-up starts, the already-confirmed operation remains in the one-shot continuation and the dialog does not claim success until the mutation succeeds.

### Changed files

- Shared mechanism, dialog, and error copy: `fe/src/features/account/security/step-up-continuation.ts` (new), `step-up.ts`, `security-shared.tsx`, and `fe/src/features/account/components/account-errors.ts`.
- Security pages: `authenticator/authenticator-page.tsx`, `email/email-change-page.tsx`, and `password/password-change-page.tsx`.
- Shared action helpers: Accounts, Organization, Institution Configuration, Platform, Privacy Governance, and Services.
- Feature handlers: account create/detail/import flows, organization responsibilities and affiliations, academic years, service detail/editor, appointment reminders, Guidance Follow-Ups, and staff Group Sessions.
- Regression coverage: `fe/tests/step-up.test.mjs`, `email-change.browser.mjs`, and `service-group-sessions.browser.mjs`.

### Focused validation

Run from the feature worktree on 2026-10-18:

- `pnpm typecheck` — passed.
- `pnpm lint` — passed.
- Focused Node tests across step-up, Group Sessions, Guidance Follow-Ups, Service Catalog, and academic-year options — 30 passed, 0 failed.
- `COMPASS_UI_BASE_URL=http://localhost:3108 node tests/email-change.browser.mjs` — 11/11 Chromium checks passed, including phone layout, invalid and duplicate TOTP submission, cancellation, account/session change, navigation during session refresh, permission/network/repeated-step-up failures after verification, refresh discovery, successful one-time continuation, and admin pending/completed status.
- `COMPASS_UI_BASE_URL=http://localhost:3108 node tests/service-group-sessions.browser.mjs` — 3/3 Chromium checks passed, including a confirmed staff publish continuing exactly once after TOTP.
- `git diff --check` — passed.

The browser checks used synthetic API fixtures and a local Next server. No backend source changed, so no backend test suite was run. Full CI, the complete frontend suite, production build, and WebKit browser checks were not run locally; the PR's remote checks remain separate from this focused validation.

### Remaining limitations

- The continuation is intentionally limited to the mounted page and its current authenticated account/session. Leaving the page, changing sessions, or taking longer than five minutes requires reviewing and initiating the action again.
- Backend recent-MFA and permission checks remain authoritative. The frontend only retries the exact first recent-MFA precondition refusal once; it does not reinterpret later failures as permission to retry.
