# GMSG-0 — Journeys, surfaces and copy truthfulness

Current rows are **Verified** at `de690220`. Proposed rows are design positions from Proposal #10 §18
(lines 8512–8548) and are **not implemented**; they are labelled **Proposed** everywhere.

## 1. Current journeys (what exists today)

### J-1 Student → Guidance Office (**Existing**)
Student opens `/portal/messages` (workspace gate `guidance-messages-workspace.tsx:57-62`) → sees their
own threads (`policy.py:47`) → **New message** writes into the single open Office thread, or creates
it (`guidance-new-message.tsx:96-184` → `POST /office-thread`, `api.py:460-466` →
`services.open_office_thread:216`). Copy states the merge behavior honestly: "If you already have an
open conversation with the Guidance Office, this message is added to it."
(`guidance-new-message.tsx:184`). Staff can start it for a workload Student
(`guidance-new-message.tsx:207-268`, `POST /students/{id}/office-thread` `api.py:479-485`).

### J-2 Student ↔ Appointment Counselor, and the contextual panel (**Existing**)
`GET /appointments/{id}/context` (`api.py:519-525`, `services.appointment_context:328-360`) returns
`{thread, can_start}` and never a body (`GuidanceAppointmentContext` docstring `api.py:125-129`). The
ADR-103 panel docks beside the Appointment/Counseling/E-Counseling surface
(`guidance-contextual-messages.tsx:54-59`) and reuses the shared conversation surface and composer;
the draft lives above the panel so closing keeps it. Students pick recipients only from
`recipient_options` (Appointments, `services.py:478-501`); staff pick Students only from
`eligible_students` (`services.py:470-475`) — **Verified: neither path reads the Accounts directory**
(`guidance-new-message.tsx:209-210`).

### J-3 Staff operational work (**Existing**)
Directory with per-thread unread and reply-needed (`work.py:19-66`, `services._directory:80-99`),
Office handler assignment (candidates `GET …/eligible-handlers` `api.py:635-641`; assign
`PATCH …/handler` `api.py:665-671`; UI `guidance-handler-assignment.tsx:26-28,111-143,247`),
resolve/reopen behind a consequential confirmation
(`guidance-conversation-surface.tsx:189-247`), and shared templates on their own route outside the
chat layout (`templates/page.tsx:10`, `guidance-message-templates-page.tsx:37-40`, capability
`guidance_messages.templates.manage`).

### J-4 Read + freshness (**Existing**)
Mark-read fires only from the open, visible, at-latest conversation
(`guidance-conversation-data.ts:129-152`; `enabled`/`canWrite`/`atLatest` chain
`guidance-conversation-surface.tsx:69-76` + `guidance-message-list.tsx:128-134` 48px rule). Realtime
hint `messages.thread_changed` reconciles directory and, only when named, the open thread
(`guidance-messages-freshness.ts:115-128,169`); polling 8s when the socket is not live, 60s when it
is (`:20-21`); a new `generation` reconciles the workspace; hidden/offline tabs do not poll.

### Gaps in the current experience (Verified absences)
1. No receipt of any kind: no "Sent", "Seen" or "Delivered" is rendered anywhere
   (grep over the feature dir; only a local cache `Set` named `seen` at
   `guidance-messages-cache.ts:50-55`).
2. No typing indicator — and the transport cannot carry one (`protocol.py:46-54`,
   `realtime_service/app.py:334-348`).
3. Reply-needed hides unassigned open Office threads (`work.py:32`) — a real work-loss gap today.
4. A Faculty account sees no Messages at all (`guidance-messages-access.ts:28-29`).
5. No message notification, badge outside the workspace, or deep link (`current-state.md` §9).
6. No per-purpose filtering in the directory — only two kinds exist
   (`models.py:11-13`), so proposal §18.1's filter set has nothing to filter on yet.

## 2. Proposed journeys (**Proposed** — nothing below is implemented)

| # | Journey | Entry | Backend contract it would need | Nearest existing precedent |
|---|---|---|---|---|
| P-1 | Faculty general inquiry | Faculty → Messages → New → "Ask the Guidance Office a question." | requester-typed thread + approved GCO intake routing | `open_office_thread` refuse-when-unroutable (`services.py:255-262`) |
| P-2 | Faculty Referral coordination | My Referrals detail → "Message the Guidance Office about this referral." | thread bound to `Referral.id`, submitter revalidation | `_own_queryset` predicate (`faculty_services.py:307-313`) |
| P-3 | Counselor direct | Messages → New → Counselor → bounded peer picker | pair columns + canonical-pair unique index + peer capability | `eligible_handlers` bounded-name search (`services.py:439-467`) |
| P-4 | Case coordination | Authorized case context → "Coordinate on this authorized case." | grant-bound thread + a real "authorized now" predicate | 404-on-invalid pattern (`continuity_access.py:59-65`) |
| P-5 | Institutional endpoint view | Staff directory with purpose labels + filters | kind-scoped list query and handler rules | `authorized_threads` (`policy.py:43-52`) |
| P-6 | Seen | "Seen" on a direct peer's read of my message; "Seen by Guidance Office" on institutional viewing | counterpart cursor; possibly a durable office watermark | `mark_read` cursor (`services.py:363-376`) |
| P-7 | Typing | "Guidance Office is typing…", "[Name] is typing…" | new registered event + a client→server signal that does not exist | closed registry (`protocol.py:46-54`) |

Blocked journey: **P-4 cannot be scheduled** until a communication scope exists on the continuity
grant (`continuity_models.py:1,34-41`) and D-GMSG-08 is approved — see `access-matrix.md` §5.

## 3. Copy inventory

### 3.1 Current strings that assume a Student counterpart (all Verified)

| Location | String | Problem if non-Student kinds land |
|---|---|---|
| `guidance-messages-presentation.ts:50` | `personName(thread.student, "Student")` | Titles a Faculty/peer thread "Student" |
| `guidance-messages-presentation.ts:9-10,14` | comment + `GUIDANCE_OFFICE_LABEL = "Guidance Office"` | The office label is reusable; the binary framing ("a Student addresses the office, staff see the Student") is not |
| `guidance-conversation-surface.tsx:216` | `personName(thread.student, "The Student")` | Resolve dialog names a nonexistent participant |
| `guidance-conversation-surface.tsx:265` | "{student} will not be able to send messages here…" | Wrong counterparty in the consequence sentence |
| `guidance-new-message.tsx:234,249,268` | label "Student", "Students could not be loaded.", "Choose a Student to write to." | Staff-only Student picker; Faculty/peer flows need their own |
| `guidance-new-message.tsx:256` | "This message goes to the Guidance Office conversation for {name}." | Cannot describe a Referral-scoped or peer thread |
| `guidance-messages-errors.ts:7` | `GuidanceSendContext = "thread" \| "student-office" \| "student-counseling" \| "staff-office"` | The error taxonomy itself is Student-shaped |
| `guidance-messages-errors.ts:34` | "This Student is no longer in your workload…" | Misstates a Faculty/peer failure |
| `guidance-thread-directory.tsx:90-96` | staff/student empty states ("No Guidance conversations are available in your current workload.") | Acceptable, but must stay honest for purposes with zero access |
| `fe/src/lib/api/generated/model/GuidanceThreadResponse.ts:25` | `student: GuidancePerson` required | Contract-level Student assumption (generated; only changeable via `contracts/openapi.json`) |

Neutral and reusable today: `guidance-messages-access.ts:3-6` (comment already says designations add
nothing), `guidance-thread-directory.tsx:31-33` (never shows message text),
`guidance-messages-errors.ts:5` (backend text never shown raw), `guidance-message-list.tsx:32-33`
(plain text, no HTML/Markdown), `guidance-messages-cache.ts:16-18` (no body from a hint),
`guidance-appointment-context.ts:27-29`.

### 3.2 Assessment of the proposal's seven §18.6 strings (lines 8536–8542)

| Proposed string | Verdict | Reason |
|---|---|---|
| "Ask the Guidance Office a question." | **Acceptable (Proposed)** | Names the endpoint and the act; no outcome implied |
| "Message the Guidance Office about this referral." | **Acceptable** | Must be offered only when `submitted_by == actor` (`faculty_services.py:307-313`), else it implies access that does not exist |
| "Message a Counselor." | **Acceptable** | Accurate for `COUNSELOR_DIRECT`; the composer notice pushing case topics to Case Coordination is still required (proposal line 8328) |
| "Coordinate on this authorized case." | **Conditional** | The word "authorized" is only truthful once a grant with a communication scope exists — today it would be a false claim (`continuity_models.py:34-41`). Do not ship before GMSG-5's authority lands |
| "Seen by Guidance Office" | **Conditional** | Only after a genuine authorized office read (D-GMSG-03/04); today no office watermark exists (`models.py:146-162`) and `mark_read` audits nothing (`services.py:363-376`), so it would be unprovable |
| "This conversation is no longer available for new messages." | **Acceptable** | Matches the real 409 states (`services.py:175-176`, `api.py:206-208`) and does not claim deletion |
| "Your case coordination access has ended." | **Conditional** | True only when a grant actually ended; must not be reused for a plain 404 concealment (`policy.py:55-69`) or it leaks why access stopped |

### 3.3 Copy rules this audit adopts (from the slice brief §7 and proposal §15/§17)

1. **Sent** = the server committed the encrypted message with a stable sequence/ID
   (`services.py:178-188`). **Seen** = the authorized counterpart, or the designated institutional
   endpoint, actually viewed it through the mark-read path (`api.py:586-596` +
   `guidance-conversation-data.ts:129-152`). Nothing else may be called Seen.
2. **No "Delivered"** language at all: the transport is best-effort and content-free with no
   device acknowledgment (`realtime/publish.py:1-11,31-40`), and no message email/push exists.
3. Never imply Referral acknowledgment, clinical resolution, or 24/7 monitoring — the current
   resolve copy already complies (`guidance-conversation-surface.tsx:216-265` speaks only of message
   sending) and any escalation Help must be GCO-approved (proposal §13.5 line 8392).
4. Office labels must not expose an individual staff identity to the requester. **Verified tension:**
   `api.py:247` already returns `assigned_to` to every authorized reader including the Student; the FE
   does not render it (`guidance-messages-presentation.ts:50` titles the thread "Guidance Office" for
   Students), so the leak is contract-level only — decide in D-GMSG-22 before Faculty kinds reuse it.
5. Keep internal jargon off screen ("thread family", "ciphertext", "scope resolver", "row lock") —
   already the convention (`guidance-messages-presentation.ts:9-10`,
   `guidance-messages-errors.ts:5`).
6. **Verified finding:** `guidance-messages-errors.ts:28` maps a 429 to
   "Too many messages were sent in a short time…", but the Messages API declares
   `ERRORS = (401, 403, 404, 409, 422, 503)` (`api.py:285`) and never rate-limits — 429 is produced
   only by `referrals/faculty_api.py:110` / `faculty_services.py:180-198`. **Proposed** kinds may not
   keep that sentence until a limiter is wired; proposal §20.6 (line 8606) wants limits.

## 4. Accessibility, responsive and state expectations (**Proposed** baseline)

Per proposal §18.7 (lines 8546-8548) and the permanent FE rules (`fe/AGENTS.md` §42, §67): keyboard
operation and visible focus; screen-reader-accessible participant and purpose names; reliable
auto-scroll that does not steal focus; loading/empty/error/retry states distinguished (a "loading"
directory must never read as empty); message pagination preserving reading position
(`guidance-message-list.tsx`, `guidance-conversation-surface.tsx:38-42` already do this); honest
sending feedback for unconfirmed sends (`guidance-message-composer.tsx:49`). Typing must be announced
sparingly — throttled, never on every heartbeat — and any animated dots must honor reduced motion.
Institutional endpoint and one-person counterpart must be visually distinguishable so nobody assumes a
private individual mailbox.

## 5. Explicitly out of the surface, now and in the proposal

**Verified absent today** (grep `typing|is typing|Seen|Delivered|presence|last seen|attachment|file|
image|media|group chat` over `fe/src/features/guidance-messages/`; only a Lucide `FileText` icon and a
local `seen` cache Set match): attachments, uploads, media, images, voice, recordings, group chat,
member rosters, invite controls, online presence, last-seen, read-performance dashboards, keystroke
capture, persistent draft history, searchable plaintext.

**Must stay absent** — proposal §27 lines 8886-8888 and the composer rule at line 8532 forbid adding
them, and `fe/AGENTS.md` §2/§18 forbid inventing the visual affordances (no attachment icons, upload
drop targets or recording buttons) that would imply them.
