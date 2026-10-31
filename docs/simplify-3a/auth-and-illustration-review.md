# Authentication and illustration review — partial

Baseline `4bfc1b4185c46cff2a40598f071bad1f2e40168e`. This is a bounded source review and synthetic render observation, not a completed route, component, state, or cross-role audit.

| Route | Source-derived entry and task | State review and evidence | Disposition |
| --- | --- | --- | --- |
| `/login` | Publicly reachable sign-in; optional safe portal destination. | Source: loading, signed-out form, session-read failure, MFA challenge, mandatory setup, sign-in errors. Synthetic signed-out render at 320px/200% reveals clipped heading and brand; floating accessibility control covers the heading. A document-width-only check passed despite visible clipping because the shell clips overflow. | S3-009; [draft PR #347](https://github.com/ils12058/COMPASS/pull/347). The other states and real authentication still need visual/interaction review. |
| `/password` | Public password setup/reset request and confirmation. | Source: email request, challenge, new password, policy/error feedback and completion. Same `AuthShell` and `AuthSurface`; synthetic initial form inspected, but challenge, errors and success still require separate review. | Shared shell fix proposed under S3-009; workflow states pending. |
| `/login/verify` | Existing sign-in MFA challenge, including a recovery-code alternative; a missing flow requires restarting sign-in. | Source review only; direct route without the in-memory flow is not evidence for a live challenge. Preserve challenge boundaries and sanitized return destination. | Pending rendered state review. |
| `/login/setup-authenticator` | Mandatory setup, QR/manual key, verification, one-time recovery codes and explicit saved-codes acknowledgment. | Source review; missing in-memory challenge requires restarting. [Draft PR #347](https://github.com/ils12058/COMPASS/pull/347) checks a synthetic QR at 320px/200% and exercises the setup path in Chromium and WebKit. Recovery codes and other layouts still need visual review without publishing real secrets. | Partial synthetic evidence; remaining rendered states pending. |

`AuthSurface` is shared by all four routes. Public entry does not imply any portal entitlement; the backend remains authoritative. Synthetic fixtures cannot establish actual MFA, identity, email delivery, production authentication, physical-device use or institutional UAT.

## Illustration inventory — source observations

- `IllustratedIntroduction`: booking, Good Moral, Graduate Tracer and Individual Inventory. Draft #343 proposes right-side fades for the first three only; Inventory remains inside a distinct form introduction and needs its own state/composition review.
- `IllustratedEmptyState`: My Appointments, Student Messages and Exit Interviews. These are confirmed empty-state treatments with different context and actions; assess them in rendered states before changing placement or applying the larger decorative treatment.
- `PublicPageHeader`: Announcements object and Resources character are currently on the left. The character and public object have different identities and page purposes; assess each rendered header, especially mobile, before proposing a right-side blend.
- `HomeShortcuts`: selected Student, Counselor and GSS shortcut panels show a small object on the right. Their capability-derived destinations and density differ; do not expand decoration into clinical content or administrative records. Review the role-specific renders and the mask proposed in #343 before reuse.
- Public hero uses the existing character group; its text change and typography prototype are proposed in #345. This is not a request to crop or fade approved brand marks.

These are placement leads from source inspection, not visual validation of every state. Artwork stays decorative and must not obscure text or controls, imply service availability, or enter sensitive/failure contexts.
