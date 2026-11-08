# GMSG-6 and GMSG-7 — Seen receipts and typing indicators

Delivered together as one change, because both travel between the same two sides of a
conversation and share the same recipient rule. GMSG-8 (unified workspace, purpose filters,
full regression and UAT) was skipped by owner decision on 2026-11-08; the broad gates it carried
have **not** run.

Nothing here is GCO-, DPO- or UCN-approved. Every behavior below that depends on an open decision
uses the GMSG-0 engineering default and is labeled provisional.

## Conversation sides

Receipts and typing always cross from one side to the other, never between staff on the Office
side (`policy.counterpart_recipient_ids`).

| Kind | Side A | Side B |
|---|---|---|
| `OFFICE` | the Student (requester) | every currently authorized Office reader |
| `FACULTY_INQUIRY` | the Faculty requester | authorized intake staff |
| `REFERRAL_COORDINATION` | the Faculty submitter | staff in the Referral's current scope (the referred Student is never a participant) |
| `COUNSELING` | the Student | the Appointment Counselor |
| `COUNSELOR_DIRECT` | one Counselor | the other Counselor |
| `COUNSELOR_CASE_COORDINATION` | one Counselor of the grant | the other (still dormant: no case-communication provider is configured) |

## GMSG-6 — Seen

- **Source:** existing read cursors only. A cursor moves only through `PATCH …/read`. The portal
  calls that only while the conversation is open in a visible tab with its newest Message in view
  (`useMarkThreadRead`). Loading the directory, the thread or its history never creates a cursor
  (tested). Historical cursors were produced the same way, so legacy threads show an honest Seen,
  or nothing.
- **Contract:** `GuidanceThreadResponse` gains `seen_sequence` (int ≥ 0, or null) and
  `seen_scope` (`PERSON` | `OFFICE`, or null). Null means this reader is shown no receipt for this
  conversation. Neither field identifies who read or when.
- **Rules** (`services.thread_receipt`):
  - Pairs see the other person's cursor.
  - A requester sees **"Seen by Guidance Office"**: the furthest cursor of any Office reader.
    This is D-GMSG-03 option (b), provisional; GCO may still choose handler-only semantics. Because
    each such cursor came from an authorized read, Office Seen does not revert when a reader loses
    access or handling changes (tested).
  - Office staff see the Student's own cursor in `OFFICE` threads only. For Faculty inquiry and
    Referral coordination it is withheld (D-GMSG-04, provisional).
- **Monotonicity (D-GMSG-26):** the cursor advances with a conditional
  `UPDATE … WHERE last_read_sequence < :new` under the existing thread lock. A row already past the
  requested sequence is never moved back (tested with a stale in-memory row).
- **Push:** a read publishes the existing `messages.thread_changed` hint to the counterpart side,
  but only when the receipt they are shown actually changes:
  - a pair read covered the other person's Messages, or
  - an Office read passed the furthest Office cursor over the requester's Messages, or
  - a Student read covered Office Messages.

  Otherwise only the reader's own sessions refresh, as before.
- **No audit** of reads (proposal §20.7 warns against routine seen telemetry).
- **UI:** "Seen" or "Seen by Guidance Office" appears under the reader's latest Message, only when
  that Message is the newest in the conversation and the other side's cursor reached it. A reply
  from the other side replaces it. Nothing ever says "Delivered" or "Not seen".

## GMSG-7 — Typing

- **Transport (D-GMSG-24):** `POST /api/v1/guidance-messages/threads/{id}/typing` returns 204 with
  no body. It authorizes with the same `require_thread(manage=True)` as sending. Resolved threads
  and voided Referrals give the same 409 refusal as a send would.
- **Hint:** the new registry entry `messages.typing_changed {thread_id}`, which carries exactly one
  opaque UUID: no sender, no draft and no duration. It is mirrored in `realtime-protocol.ts`. There
  is still no client→server WebSocket frame.
- **Recipients:** the counterpart side only, recomputed from current authorization at send time.
- **Throttle (D-GMSG-13/28, provisional):** the existing Redis limiter allows one hint per reader
  per thread every 3 s. The portal signals at most every 3.5 s, and only while the draft is
  changing and not blank. When the limiter refuses or is unavailable, nothing is published and the
  request still succeeds, because typing is advisory.
- **Nothing is stored:** no typing row, no draft, no audit event, and the thread's `updated_at` is
  untouched (tested).
- **Receiver:** shows "… is typing…" for 8 s after the last hint. It hides at once when a newer
  Message arrives from the other side or the conversation is no longer open. The polite status
  region changes only when typing starts or stops, never on each hint. The dots animate only
  without reduced motion. Labels come from the reader's side ("Guidance Office is typing…",
  "Maria Santos is typing…"). Case coordination says "The other Counselor is typing…".

## Validation run (targeted only)

- Backend: `tests/test_guidance_messages_receipts.py` (12) and
  `tests/test_guidance_messages_typing.py` (21) pass. Every `tests/test_guidance_messages*.py`,
  `test_realtime_service.py`, `test_openapi_contract.py` and `test_case_communication.py` was run:
  485 passed and 4 failed. All 4 were golden expectations this slice deliberately changes:
  - the thread key set now includes `seen_sequence` and `seen_scope`;
  - a Student's read now also refreshes the counterpart side's sockets.

  Both tests were updated (the realtime one is renamed `…read_receipt_freshness`), and their files
  pass (58).
- Contract: `export_openapi` regenerated `contracts/openapi.json`, and `pnpm api:generate`
  regenerated the client.
- Frontend: `tsc --noEmit` passes, ESLint on `src/features/guidance-messages` and
  `src/features/realtime` passes, and `tests/guidance-messages.test.mjs` passes (45).
- **Not run:** the backend full suite, `pnpm test` as a whole, browser regressions on Chromium and
  WebKit, and UAT. These were deferred by owner decision; run them before any staging deploy.

## CI bundle repair

The `guidance-messages` bundle in `.github/scripts/backend_ci.py` now lists every messages test
file, including `_case`, `_direct`, `_faculty`, `_kinds`, `_migration` and `_referral`, which
GMSG-1..5 had left unregistered. Without them `prepare` would fail. Five other unregistered files
from earlier slices remain:

- `test_case_communication.py`
- `test_counseling_documentation_review.py`
- `test_counseling_finish.py`
- `test_counseling_finish_concurrency.py`
- `test_fup3a_faculty_referral_journey.py`

`backend_ci.py verify` still fails until they are added to their own bundles.
