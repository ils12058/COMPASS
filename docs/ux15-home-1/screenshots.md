# Synthetic before/after evidence

All captures use the same synthetic Alex Rivera account, fixed institutional time
2026-10-22 09:30 Asia/Manila, and synthetic action/Announcement records. The browser timezone is
America/Los_Angeles, exercising institutional date/time presentation. No real Student identity,
Counseling text or institutional record is included.

Before captures use untouched production sources at integration
`613525bf9c7ed41dca8869fd717b5baf360f2f70` on the local development server (final matched recapture
in a temporary baseline worktree at port 3124). Final after captures use the ordinary optimized
build with synthetic intercepted API responses at port 3123. Each pair uses the same fixture, viewport and root
font setting. The test fixture is `fe/tests/support/ux15-home-fixtures.mjs`; the scenario suite is
`fe/tests/ux15-student-home.browser.mjs`.

| Scenario | Before | After | Review focus |
| --- | --- | --- | --- |
| 1440px, several pending actions | [Before](screenshots/before/ux15-student-home/before-desktop-pending.png) | [After](screenshots/after/ux15-student-home/after-desktop-pending.png) | Action-first hierarchy, server priority labels, bounded discovery and supporting counts. |
| 1440px, confirmed empty actions | [Before](screenshots/before/ux15-student-home/before-desktop-empty.png) | [After](screenshots/after/ux15-student-home/after-desktop-empty.png) | Shallow accurate empty state; services and updates remain useful. Counts remain independent of actionable work. |
| 390px phone | [Before](screenshots/before/ux15-student-home/before-mobile-pending.png) | [After](screenshots/after/ux15-student-home/after-mobile-pending.png) | Reading/action sequence, wrapping targets and discovery before supporting updates. |
| 320px, 200% root text | [Before](screenshots/before/ux15-student-home/before-narrow-enlarged.png) | [After](screenshots/after/ux15-student-home/after-narrow-enlarged.png) | Document width falls from 328px to 320px; heading and Announcement rows reflow. |
| 1440px, joinable E-Counseling | [Before](screenshots/before/ux15-student-home/before-join-now.png) | [After](screenshots/after/ux15-student-home/after-join-now.png) | Existing server time-sensitive classification and Join until time; no new urgency/deadline or consent action. |
| 1440px, action query failure | [Before](screenshots/before/ux15-student-home/before-failed-actions.png) | [After](screenshots/after/ux15-student-home/after-failed-actions.png) | Retry and independently usable service/context regions; no false completion claim. |
| 1440px, graduated Student | [Before](screenshots/before/ux15-student-home/before-graduated.png) | [After](screenshots/after/ux15-student-home/after-graduated.png) | Existing Tracer draft and authorized discovery; no Current-only Book command or Inventory obligation. |
| 1440px, Counselor/Head reference | [Before](screenshots/before/ux15-student-home/before-professional.png) | [After](screenshots/after/ux15-student-home/after-professional.png) | Existing My work/summary composition and designation context retained. |

Additional final evidence:

- [Action loading with confirmed context](screenshots/after/ux15-student-home/after-loading-actions.png)
- [Stale confirmed actions with Retry](screenshots/after/ux15-student-home/after-stale-actions.png)
- [Announcements at 320px/200%, including an unbroken synthetic title](screenshots/after/ux15-student-home/after-announcements-320-200-detail.png)
- [Baseline measurements](screenshots/before/ux15-student-home/geometry.json)
- [Final document/panel/target measurements](screenshots/after/ux15-student-home/geometry.json)
- [Baseline capture results](screenshots/before/ux15-student-home/results.json)
- [Final Chromium scenario results](screenshots/after/ux15-student-home/results.json)

Screenshots were visually inspected. Geometry assertions additionally check six requested widths
at normal and 200% root text, panel-internal reflow, focusable targets inside the viewport and no
overlapping Home links. Screenshots alone do not establish behavior or accessibility compliance.
Root-font enlargement is not browser zoom. See [validation](validation.md) and [follow-ups](followups.md).
