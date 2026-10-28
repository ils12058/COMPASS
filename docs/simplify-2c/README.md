# SIMPLIFY-2C illustration integration

University of Camarines Norte (UCN). Verified base: `1e907f928f151fdc5cd8f35c3b216f2f07d84e06`
on `integration/ux15-modernization`, including SIMPLIFY-2A #339 and SIMPLIFY-2B #340.
The PR records the final implementation SHA. All 14 approved PNG hashes match the
[merged manifest](../simplify-2b/asset-manifest.json); no artwork was regenerated or changed.

## Implemented placements

Eight feature objects are used across Home discovery and seven feature journeys. Existing
role/lifecycle/query conditions decide when an introduction is appropriate; artwork adds no access.

| Object | Placement and rationale |
| --- | --- |
| Appointment calendar | Student Guidance services and GSS continuation, only with their existing appointment destination; also confirmed unfiltered empty My Appointments. A scheduling cue after primary work, outside records and schedules. |
| Guidance Messages | Counselor continuation, including Head Counselor, only with its Messages destination; also a successfully empty Student directory with no open conversation. No illustration accompanies message bodies or identifiers. |
| Service Catalog | Booking's existing “Ways to get support” introduction, before selection and only with available service data. Flexible, fixed-slot and group pathways keep their own actions and conditions. |
| Individual Inventory | First current-year entry with no history and no draft, before the questionnaire; omitted on pending/failed history, start errors and unavailable management. Introduces the document without decorating answers. |
| Good Moral | Request heading for a successfully eligible current Student, apart from the certificate-type/academic details and submission controls. The toy document conveys a service concept, not issuance or approval. |
| Exit Interview | Open, startable opportunity before any record exists; omitted for missing prerequisites, start errors and blocked access. Existing Start and opportunity language remain authoritative. |
| Graduate Tracer | Manageable graduate entry after the server confirms no response exists. Omitted once a draft or submitted response exists, on uncertainty or on unavailable access. |
| Announcements | Public title band replaces the pointing-up character with the megaphone object. Only one illustration appears there. |

IT Home receives no artwork. The public landing retains the GCO group and Resources its pointing
character. The unused point-up and wave files remain approved and intact. Counseling and Follow-Ups
objects were evaluated but deferred: booking already has a service introduction, while selected
Counseling proceeds into prerequisites and time selection. Follow-Ups has no separate introduction
outside operational lists that justifies another accent in this batch.

## Composition and accessibility

Home accents are 64–80px, introductory objects 80–112px, empty-state accents 64px, and the public
title object 96px. The four introduction consumers share `IllustratedIntroduction`; empty messages
share `IllustratedEmptyState`. Neither adds a card, heading, eligibility rule or onboarding step.
All keep existing text, Lucide controls and actions. Decorative images use `next/image`, correct
512×512 intrinsic dimensions, reserved aspect ratio, empty alt text and no focus stop. Optional
artwork hides when narrow containers or enlarged text leave insufficient room. Content remains
complete with image requests blocked. A local wrapping adjustment keeps the booking Service pager
inside narrow screens at 200% root text; pagination behavior is unchanged.

## Before and after

Local production builds with synthetic fixtures. The baseline is the integration SHA above;
matching routes and fixture states were captured at 320/390/1024/1440px. Selected pairs:

| Surface | Before | After |
| --- | --- | --- |
| Student Home, 1440px | [Before](screenshots/before-student-1440.png) | [After](screenshots/after-student-1440.png) |
| Counselor Home, 390px | [Before](screenshots/before-counselor-390.png) | [After](screenshots/after-counselor-390.png) |
| GSS Home, 1440px | [Before](screenshots/before-gss-1440.png) | [After](screenshots/after-gss-1440.png) |
| Head Counselor, 1024px | [Before](screenshots/before-head-1024.png) | [After](screenshots/after-head-1024.png) |
| Empty My Appointments, 320px | [Before](screenshots/before-appointments-empty-320.png) | [After](screenshots/after-appointments-empty-320.png) |
| Booking, 1440px | [Before](screenshots/before-booking-1440.png) | [After](screenshots/after-booking-1440.png) |
| Empty Messages, 390px | [Before](screenshots/before-messages-390.png) | [After](screenshots/after-messages-390.png) |
| Inventory entry, 1440px | [Before](screenshots/before-inventory-1440.png) | [After](screenshots/after-inventory-1440.png) |
| Good Moral introduction, 1440px | [Before](screenshots/before-good-moral-1440.png) | [After](screenshots/after-good-moral-1440.png) |
| Exit entry, 390px | [Before](screenshots/before-exit-390.png) | [After](screenshots/after-exit-390.png) |
| Tracer introduction, 390px | [Before](screenshots/before-tracer-390.png) | [After](screenshots/after-tracer-390.png) |
| Public Announcements, 1440px | [Before](../simplify-2b/screenshots/chromium/public-illustrations/announcements-desktop.png) | [After](screenshots/after-announcements-1440.png) |

[IT, 390px](screenshots/after-it-390.png) records the intentional absence of artwork;
[public landing](screenshots/public-landing-1440.png) was visually reverified unchanged.

## Validation and limits

Client generation, lint, typecheck and production build passed. Focused Node batches passed
23/23 Home, 46/46 header/Exit/Tracer, and 20/20 Good Moral/date/fixed-slot checks.
Chromium and WebKit each passed the 37-case Home/empty-state suite, 34 feature cases (including a focused WebKit rerun after fixing an asynchronous test wait),
13-case public artwork suite and existing keyboard/focus regression. Checks cover all four widths,
enlarged text, image decoding/aspect ratio, accessible decoration, no control overlap, reserved
geometry, image failure, and no illustration on blocked/error/private states. The booking pager's
enlarged-text failure was corrected and rechecked. A missing populated-appointment fixture was
corrected before final Home runs; the booking fixture now supplies canonical pagination metadata.

Follow-ups: consider Counseling only if a real pre-service introduction emerges, and Follow-Ups
only outside operational records. Synthetic fixtures and visual review do not establish authenticated
backend integration, physical devices, native zoom, screen-reader acceptance or UCN institutional
UAT. No deployment or merge is included.
