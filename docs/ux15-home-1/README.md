# COMPASS-UX15-HOME-1 — Student Home

Experimental Proposal #15, October 22, 2026. A focused frontend redesign of `/portal` for Students:
understand current work, act in its owning workspace, discover relevant services and read updates.
No deployment or automatic merge is authorized or performed.

## Verified source

Fetched `origin` before creating the isolated managed worktree
`/Users/reynantlntno/.codex/worktrees/ux15-student-home/COMPASS` and branch
`feat/ux15-student-home`. Exact integration baseline:
**`613525bf9c7ed41dca8869fd717b5baf360f2f70`**.

Git history and GitHub PR metadata confirm these merged integration prerequisites:

| PR | Work | Integration commit |
| --- | --- | --- |
| #297 | Inventory pilot | `f7e2e8c3b3d4fac57e294ae1452be54b93957cf0` |
| #298 | Exit Interview pilot | `132be02d69316d8456b0a244704c0a9f263d1e13` |
| #299 | Graduate Tracer pilot | `c5f1bb2bdd37fd98eb640d563553b425771cd140` |
| #300 | Counselor Evaluation pilot | `f74ee48da7191e1a2a3f0e7ba5bc4e0127655870` |
| #301 | Routine Intake pilot | `a4c8bed349e0a7e774f8a6bde3bb805fb0168543` |
| #302 | Feedback/CSM pilot | `757eb933786b8067724394c365d3a760279a1627` |
| #303 | Unified forms consolidation | `af171d2a41fb1dab4d83b04fc9c285cec6365ce8` |
| #304 | Portal Shell accessibility | `613525bf9c7ed41dca8869fd717b5baf360f2f70` |

The PR targets only `integration/ux15-modernization` and remains for review. Proposal #15 remains
experimental; local results do not establish institutional UAT, release approval or readiness.

## Architecture and rationale

The existing shared Home already has the correct data architecture: one Overview count query,
canonical Student Actions first-five preview, authorized primary Book action, My work for Guidance
professionals, platform email context for IT, and visible-audience Announcements. ADR-058 defines
the count/null semantics, ADR-090 establishes ordering principles, and ADR-106 owns the current
Student Actions contract. The form consolidation and Portal Shell audit were reviewed before
implementation. Verified behavior and the initial plan are in [experience-audit.md](experience-audit.md).

The redesign keeps that architecture and separates only Student composition. It uses the hierarchy:

1. Concise Overview identity, existing institutional greeting/date and authorized Book appointment.
2. Full-width Needs your attention, preserving the first five server-ordered actions and View all.
3. A compact Guidance services selection and supporting At a glance counts.
4. Student-visible Announcements.

The action preview is full width so genuine work has the strongest visual position and an empty
result stays shallow. Initial visual review rejected a tall companion column beside a short empty
preview because it left a large blank area. Discovery and counts now sit together below actions
when the content region is wide enough; mobile follows the same DOM order in one column.

Four service entry points use existing self-view helpers: Appointments, Guidance Messages,
Inventory (or Graduate Tracer when authorized) and Good Moral requests. Copy describes opening a
workspace, never an obligation or available slot. Other destinations remain in the existing
authorized dock/search. `/portal/services` is management, so it is deliberately absent.

## Implementation

| File under `fe/src/features/portal/home/` | Responsibility |
| --- | --- |
| `portal-home.tsx` | Retains shared hooks/header; selects Student composition; excludes professional summary sections from Student consumption. Professional composition stays intact. |
| `student-home.tsx` | New Student composition and bounded service discovery list. |
| `student-home-attention.tsx` | New Student presentation of the existing preview: contextual links, backend-provided urgency, bounded loading and truthful confirmed/stale/failed states. |
| `student-home-presentation.ts` | Small pure destination selection using existing domain access helpers; no task rules or data fetching. |
| `overview-work.ts` | Exposes the existing presenter's priority label in its presentation type and supplies the existing Student query's retry callback. No inclusion, ordering or query change. |
| `overview-announcements.tsx` | Local emergency wrapping and content-width-dependent date/title stacking; no shared Panel or feed behavior change. |

Reused primitives: PageHeader, PageActionLink, Panel/Header/Message, Button/buttonVariants,
LoadingRegion, Skeleton, ordinary Next links, AnnouncementDate and existing typography/tokens.
OverviewSummary, professional OverviewAttention, all query hooks, access helpers, Portal Shell,
navigation, forms and workflow owners remain unchanged.

## Boundaries

- Backend domains still decide eligibility, source identity, timing, priority, ordering and scope.
- Home reads canonical projections and navigates. It never books, submits, consents, marks read,
  issues a certificate or completes a record.
- The same account-owned QueryClient, invalidations, realtime hints, focus/reconnect behavior and
  polling continue to apply. No storage, socket, cache, query hook or action aggregator was added.
- Current-only booking remains gated. Graduated Students receive Tracer discovery only through
  the existing graduated/self-view gate; Former/Graduated Inventory reading does not imply editing.
- Exact metrics, authorized destinations, null omission and confirmed numeric zero are retained.
- Student presentation never includes professional queue rows, Guidance metrics or email status.
  Counselor/Head, GSS, IT and Institutional Officer/DPO behavior is covered by focused regressions.
- Announcement audience, order, pins, first-three preview and reader links remain server-owned.

The reported 320px/200% Announcements spill is fixed locally. No clipping, global overflow
suppression, shared primitive change, questionnaire change, backend/contract change, migration,
permission change, CI configuration change, protected-branch mutation or deployment is included.

See [information architecture](information-architecture.md), [validation](validation.md),
[synthetic visual evidence](screenshots.md) and [follow-ups](followups.md).
