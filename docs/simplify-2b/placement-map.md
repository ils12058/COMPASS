# SIMPLIFY-2C illustration handoff

SIMPLIFY-2A is merged at `843e96eb`. This map uses its actual Home sections; 2B changes no
role-based Home files. The ten feature concepts were checked against implemented routes,
`portal-workspaces.ts`, the public Quick Access service list and the role Home destination helpers.
These are candidates for a focused 2C change, not instructions to place every image.

All filenames below live in `fe/public/illustrations/`. Sizes are CSS pixels; preserve the square
canvas except the 2:1 character group. **Every current or proposed use below is decorative**:
nearby text must carry the meaning, use `alt=""`, never add focus/tab stops or remove text.
No asset independently conveys availability, eligibility, progress, issuance, clinical benefit or
permission. Informative use would need a separate content/accessibility review.

Prefer one useful accent per Home page, after urgent work, and at most one per selected section.
Do not replace Lucide icons in destination links or action controls. Keep current authorization
and lifecycle checks. Hide an optional accent rather than crowding text or controls on narrow
screens. Choose an asset only when the benefit in the last column applies.

| Asset | Feature / target page or component | Size | Priority | Why it could help / boundary |
| --- | --- | --- | --- | --- |
| `appointment-calendar-3d.png` | Student Home `StudentHome` → “Guidance services”, or introduction in `AppointmentBookingPage` at `/portal/appointments/book` | 96–160 | P1, choose one | Orients readers toward scheduling; never inside appointment rows, the attention queue, date controls or unavailable/error states. |
| `service-catalog-3d.png` | GSS `OfficeDestinations` → “Continue in your workspaces”, or Head `HeadGuidanceDestinations` → “Authorized oversight” | 80–112 | P2, permission dependent | Helps staff recognize the service collection only when their existing destinations include `/portal/services`. Do not grant Student catalog access or decorate the catalog table/editor. |
| `guidance-messages-3d.png` | `GuidanceMessagesWorkspace` at `/portal/messages`: non-sensitive welcome panel before opening a conversation; alternative Student Home discovery accent | 96–160 | P1, choose one | Explains the conversation space. Omit when message content is shown; never put artwork beside private message bodies, names in rows, unread counts or failures. |
| `individual-inventory-3d.png` | Student Home → “Guidance services”, or `InventoryHome` at `/portal/inventory` before opening the questionnaire | 96–160 | P1, choose one | Gives the form introduction a clear document cue. Do not decorate answers, saved records, assessment results or form controls. |
| `counseling-3d.png` | Pre-record service introduction in `AppointmentBookingPage` when the real `COUNSELING` service is selected | 192–224 | P2, intro only | The two-chair composition can explain a conversation with a counselor. Never use in `CounselingEntryPage`, session summaries, encounters, case coverage, E-Counseling calls or clinical outcomes. |
| `guidance-followups-3d.png` | Counselor `CounselorDestinations` → “Continue in your workspace” when its Follow-Ups destination is available | 80–112 | P2, optional welcome | Orients staff toward ongoing follow-up work. Keep the static checklist outside actual task counts, progress, the `FollowupsList` table, case details and consequential actions. |
| `good-moral-3d.png` | `GoodMoralRequestPage` at `/portal/good-moral/request`: request introduction | 112–160 | P1 | Explains the document being requested. The blank toy certificate is not an official form, seal, signature or issuance/approval signal. Exclude receipts, release/issuance controls, PDF output and request-detail statuses. |
| `exit-interview-3d.png` | `ExitInterviewStudentHome` at `/portal/exit-interviews`: eligible introduction before opening an interview | 112–160 | P2 | A calm transition cue; no emergency/expulsion meaning. Keep existing opportunity eligibility authoritative; omit from completed interview answers or decisions. |
| `graduate-tracer-3d.png` | `GraduateTracerStudentWorkspace` at `/portal/graduate-tracer`: graduate survey introduction; alternative Graduate Student Home discovery accent | 112–160 | P1, lifecycle dependent | Identifies the alumni journey. No employment, completion or eligibility claim; do not decorate saved survey responses or staff reports. |
| `announcements-3d.png` | Public `PublicPageHeader` at `/announcements`: possible future alternative to its character | 96 | P3, alternative only | Can identify public notices if a later design review prefers the object. Never show it alongside the existing pointing-up character or add one to every announcement card/detail. |
| `gco-characters.png` | Current public landing `PublicHero` | 240 / 272 / 304 wide | Current | Welcomes the public; preserve the group order, all four full figures and 2:1 ratio. No lower-landing repeats. |
| `gco-character-point-up.png` | Current `PublicPageHeader` at `/announcements` | 96 high; hidden below 640 | Current | Supports the title band; no new placements in 2B. |
| `gco-character-point-right.png` | Current `PublicPageHeader` at `/resources` | 96 high; hidden below 640 | Current | Supports the resource orientation; no new placements in 2B. |
| `gco-character-wave.png` | No current consumer; optional future public `/login` introduction only if useful | 96–128 | Hold | Existing greeting pose already covers welcome needs. Do not add a pose or a portal mascot without a concrete approved placement. |

**Deferred subjects:** Routine Interviews and Reports are implemented. A second clipboard would
overlap Inventory/Follow-Ups, and the current Routine Interview/Counseling paths lead into sensitive
work. Reports currently covers scoped Student Profile and Graduate Tracer reporting; there is no
planned non-sensitive introductory placement that justifies another generic chart/document asset.
No new character poses are needed for the current public placements or these object candidates.

Do not add artwork to confidential records, sensitive case details, assessment results, security
settings, dense administrative tables, error/blocked states or consequential confirmation dialogs.
Keep rendering failure graceful: content and actions must remain complete if an image is absent.
This Markdown map is the handoff; no asset registry service or new navigation/configuration layer
is introduced.
