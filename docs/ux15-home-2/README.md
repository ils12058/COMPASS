# COMPASS UX15-HOME-2 — Counselor Home

This slice gives Counselor accounts a focused professional Home organized around today's schedule and the existing canonical work queue. A Head Guidance Counselor retains that same self-scoped work and sees only oversight destinations granted by existing route and capability checks.

## Baseline and scope

- Verified base: `integration/ux15-modernization` at `1d8dcd3eb413955718904c1acb8e0b87d8766053`.
- Feature branch: `feat/ux15-counselor-home` in an isolated worktree.
- Pull request target: `integration/ux15-modernization` only.
- Proposal #15 remains experimental pending formal review and appropriate Counselor/Head Guidance Counselor UAT.
- No backend, database, OpenAPI contract, protected branch, or deployed environment was changed.

## Audited architecture

Before this slice, `PortalHome` already selected the Student-specific composition, while Counselors and other professional roles used the shared Overview: canonical work/actions and announcements with the existing summary panel. The shared source projections were already available: `useOverviewAttention` consumes `useWorkQueue` for authorized professional tasks; `OverviewSummary` preserves backend-defined metric meanings; `OverviewAnnouncements` retains existing audience, pinned, and navigation behavior. Counselors had no dedicated Home agenda.

The canonical `/api/v1/work` projection owns professional item selection, priority, ordering, pagination, and source destinations. `/api/v1/appointments/me` is the existing self-Appointment listing, with bounded date/status/order filters. Existing access helpers distinguish self Appointment reading from managed Appointment access. `portalWorkspaceGroups(user)` is the source for visible workspace destinations. A Head designation is not an access grant.

## Implemented experience

The Counselor Home presents a compact greeting and Philippine date, then puts Today's appointments beside My work. It follows with up to four authorized continuation destinations, an optional separately labelled Authorized oversight area for Head Counselors with corresponding capabilities, the unchanged Overview summary, and announcements. The Student and non-Counselor compositions remain in their existing branches.

The agenda reads only the self endpoint for users with `appointments.view_self`, filters scheduled records to the Manila institutional date, requests earliest-start order, and shows at most five appointments. It names the student and service, shows time/status/delivery mode, and links to the owning Appointment. It omits appointment purpose and narrative fields. The work preview keeps the server's first-page ordering and source routes; it does not create a second aggregator.

Loading, confirmed-empty, stale, failed, and authorization-denied cases remain distinct. Reads refresh periodically and on focus/reconnect; there are no Home mutations.

## Preserved invariants

- No new data aggregation, backend contract, or broad Head authorization.
- No inferred appointments, encounters, urgency, or completed responsibilities.
- Existing Overview summary semantics, `null` handling, routes, and announcements are reused.
- Student, GSS, IT Admin, and other shared professional Home paths are not replaced.
- Sensitive counseling narratives, assessment findings, referral reasons, and message bodies are not included in the Home preview.
- Screenshots and fixtures use synthetic data only.

## Changed files

Production changes:

- `fe/src/features/portal/home/portal-home.tsx` — select the Counselor composition and update the institutional clock while it remains open.
- `fe/src/features/portal/home/counselor-home.tsx` — agenda, canonical My work, continuation links, authorized oversight, and responsive composition.
- `fe/src/features/portal/home/counselor-home-presentation.ts` — role/capability checked destination selection.
- `fe/src/features/portal/home/overview-work.ts` — expose existing work pagination/retry state and source priority label to the new Home.

Verification and documentation:

- `fe/tests/support/ux15-counselor-home-fixtures.mjs`
- `fe/tests/ux15-counselor-home.test.mjs`
- `fe/tests/ux15-counselor-home.browser.mjs`
- `fe/tests/ux15-student-home.test.mjs` and `fe/tests/ux15-student-home.browser.mjs` — update assertions for the intentional Counselor-only composition while preserving the Student and other roles' checks.
- `docs/ux15-home-2/` — audit, IA, access notes, results, screenshots, and follow-ups.

See [experience audit](experience-audit.md), [information architecture](information-architecture.md), [privacy and access](privacy-and-access.md), [validation](validation.md), [screenshots](screenshots.md), and [follow-ups](followups.md).
