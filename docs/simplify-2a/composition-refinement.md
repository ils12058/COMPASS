# SIMPLIFY-2A composition refinement

University of Camarines Norte (UCN). The implementation builds on the Home pilot merged in
[PR #338](https://github.com/ils12058/COMPASS/pull/338) and the
[product assessment](product-experience-assessment.md).

## Completed

- Counselor and Guidance Services Home place actionable work first, followed by a compact
  time-column agenda and capability-filtered destinations and context. Head Counselor oversight
  remains distinct and capability-gated. Student actions, service destinations and IT capability
  content retain their existing states and links.
- Clickable task rows present the subject, timing and urgency once; shortcuts and section actions
  use existing Lucide icons with labels. Summary counts are compact and announcements retain title,
  priority and publication date. Work and agenda can grow independently without stretching a short
  queue beside a long schedule.
- Shared page actions, header layout, workspace tabs and coarse-pointer controls apply the same
  interaction language throughout the application. Contextual Help has a named icon control, a
  keyboard tooltip, a touch-visible label and a focus-returning dialog. Forced-color focus outlines
  supplement the existing focus rings.
- Messages measures the actual portal header and viewport so the composer remains reachable.
  Embedded Good Moral requests have one page heading and Back link; Graduate Tracer avoids a
  repeated title; Service Catalog combines its booking summary; the appointment booking sheet no
  longer repeats its roadmap. Domain rules, permissions and backend contracts are unchanged.

The source inventory covered 130 route entry points; a shared-header contract check covered 196
compositions and 19 forwarding wrappers. This is an inventory, not a claim that every route, role
and state received a separate rendered or authenticated review.

## Synthetic before and after

The before images below are the prior merged Home pilot or the product-assessment baseline. Both
sides use local synthetic fixtures, never real student or counseling records.

| Surface | Before | After |
| --- | --- | --- |
| Counselor, 1440px | [Before](composition-screenshots/before-counselor-1440.png) | [After](composition-screenshots/after-counselor-1440.png) |
| Counselor, 390px | [Before](screenshots/after-counselor-390.png) | [After](composition-screenshots/after-counselor-390.png) |
| Student, 1440px | [Before](screenshots/after-student-1440.png) | [After](composition-screenshots/after-student-1440.png) |
| Head Guidance Counselor, 1440px | [Before](screenshots/after-head-1440.png) | [After](composition-screenshots/after-head-1440.png) |
| Guidance Services Staff, 390px | [Before](screenshots/after-gss-390.png) | [After](composition-screenshots/after-gss-390.png) |
| IT Administrator, 1440px | [Before](screenshots/after-it-1440.png) | [After](composition-screenshots/after-it-1440.png) |
| Good Moral F6, 1440px | [Before](product-screenshots/good-moral-1440.png) | [After](composition-screenshots/after-good-moral-1440.png) |
| Graduate Tracer, 390px | [Before](product-screenshots/tracer-390.png) | [After](composition-screenshots/after-tracer-390.png) |

Home role fixtures also ran at 320 and 1024px. Separate synthetic cases cover short and long work
queues, empty agendas, absent summaries, unavailable work, restricted oversight, enlarged text,
keyboard order and forced-color focus. Screenshots are visual evidence of fixtures, not a substitute
for real-backend authorization, physical devices, native zoom, screen readers or institutional UAT.

## Follow-on candidates

1. **Individual Inventory:** investigate mobile orientation and action proximity without changing
   controlled questions or validation.
2. **Guidance Follow-Ups:** examine busy filtered lists and responsibility/timing hierarchy with
   realistic work volume and distinct empty, unavailable and stale states.
3. **Appointments and Accounts collections:** check floating search and filters against pagination,
   long identities and enlarged text; preserve their different search timing.
4. **Counseling and E-Counseling:** assess the relationship between tabs, case content and call
   state with real workflow input; preserve continuity, consent and confidentiality.

The illustration owner retains the asset directories and public illustration components. A later
handoff may place an approved illustration in Student welcome or service discovery where it helps,
using the actual approved asset path; sensitive tasks and the layouts above do not depend on it.
