# UX15 HOME-3 — Guidance Services Staff Home

This slice adds a dedicated operational Home for Guidance Services Staff. Its baseline is the fetched `integration/ux15-modernization` commit `217e1677bd78dc53640b6fb5c49e892e3ec1f734` (HOME-2 PR #307). The feature branch is `feat/ux15-gss-home`; the PR target is `integration/ux15-modernization`.

The Home puts the canonical **My work** preview first, followed by today's authorized managed Appointments, a compact **Office workload** summary, and a short list of authorized workspace destinations. Announcements remain below the operational areas. The shared Overview summary is not fetched for GSS because its Guidance counts overlap the scoped Guidance Operations projection and are not needed in this composition.

The implementation reuses:

- Work Queue through `useOverviewAttention`'s canonical item projection and the existing `/portal/work` destination.
- Guidance Operations through `useGuidanceOperations` and its existing GSS-scoped aggregate response.
- Managed Appointments through `getAppointmentAccess(user).canManage` and the generated `appointmentsListManaged` query.
- Office destinations through `portalWorkspaceGroups(user)` and the existing per-domain access helpers.
- Existing freshness, React Query, retry, focus/reconnect, date/time-zone, Panel, and Portal Shell patterns.

The Home adds no backend endpoint, database migration, permission, workflow mutation, new role, or separate cache. The managed schedule uses a five-item, scheduled-only, chronological preview bounded to the current `Asia/Manila` date. GSS accounts without `appointments.manage` make no managed Appointment request and see no empty-schedule claim.

Student Home, Counselor/Head Home, and the existing shared Overview for other roles remain on their existing compositions. No changes were made to `staging` or `main`; no deployment was performed. The PR is intentionally not merged by this slice.

See [the experience audit](experience-audit.md), [information architecture](information-architecture.md), [privacy and access notes](privacy-and-access.md), [validation](validation.md), [screenshots](screenshots.md), and [follow-ups](followups.md).

## Changed-file inventory

- Production UI: `fe/src/features/portal/home/gss-home.tsx` adds the GSS composition; `gss-home-presentation.ts` applies existing access helpers and formats work, metrics, schedule parameters, and authorized destinations; `portal-home.tsx` selects the role-specific branch; `overview-work.ts` exposes the canonical Work Queue projection and its freshness state to the Home.
- Tests: `fe/tests/ux15-gss-home.test.mjs`, `ux15-gss-home.browser.mjs`, and `support/ux15-gss-home-fixtures.mjs` add focused synthetic coverage. Existing Student and Counselor Home tests are updated to assert the new role branch and preserve the existing role compositions.
- Documentation and evidence: this directory records the audit, hierarchy, privacy boundaries, validation, screenshots, and follow-ups. After-state Chromium and WebKit screenshots, result files, and responsive geometry are under `screenshots/after/`.

The access boundary remains source-owned: the backend supplies canonical authorized Work Queue items, managed Appointment authorization still uses `appointments.manage` and server scope, Guidance Operations remains a scoped aggregate, and every continuation link is selected from `portalWorkspaceGroups(user)`. The Home adds no mutation action.
