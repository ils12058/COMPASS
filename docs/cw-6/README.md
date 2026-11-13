# CW-6: Counselor About and Messages context

**Date:** 14 November 2026 · Philippine Time  
**Branch:** `codex/counseling-cw6-about-messages`, stacked on `codex/counseling-cw4-closure` ([#366](https://github.com/ils12058/COMPASS/pull/366), open when this branch was cut)  
**Specification:** [Counseling workflow plan](../counseling-workflow-plan.md), ABOUT-01 to ABOUT-03, MSG-01, MSG-02, UX-06 and the section 13 About/Messages acceptance scenarios.  
**Builds on:** [CW-1](../cw-1/README.md) to [CW-4](../cw-4/README.md); the Messages work it preserves is recorded in [GMSG-6/7](../gmsg-6-7/README.md).  
**Status:** Implemented and verified locally: backend, canonical contract, frontend validation and unit tests, the affected mocked browser suites in Chromium and WebKit, and real Django + Next journeys in both engines with a database oracle. No migration, so no upgrade rehearsal was needed. This stacked feature branch has no hosted CI run; nothing is merged or deployed.

## What people see

**About** answers one question: where in the Guidance Office is this Counselor assigned? It opens in a dialog and shows the Counselor's name, optional photo and current College assignments grouped by Campus. A College the unique Head handles only because no valid Counselor is assigned to it is marked **“Covered while no Counselor is assigned”**. It is never shown as a direct assignment. With no assignment recorded, About says so plainly. A short line says the list shows office assignments, not who handles a particular case.

About appears in four places, always as a separate button beside the choice, never inside its label:

| Where | Who | What stays unchanged |
|---|---|---|
| Booking, beside each offered Counselor | Students | The selected Counselor; nothing is booked. |
| New message, beside each Counseling recipient | Students | The selected recipient; nothing is sent. |
| A Student's Counseling conversation header | Students | The conversation and its draft. |
| Transfer and coverage preparation, beside the chosen receiving Counselor | Counselors and office staff | The chosen receiver and the prepared request. |

**Messages context.** A Counseling conversation now shows its Counselor's photo and its linked Appointment: reference, date and time, and current status. The Service name appears only when it differs from Counseling. Several conversations with the same Counselor are told apart in the directory by “Appointment <date> · <status>”. The Student's new-message recipient choices carry the same reference, date and status. Office conversations keep the Guidance Office identity and have no Appointment line.

When the reader may no longer see the linked Appointment, for example a Counselor who was reassigned away from it, the conversation stays theirs. The header then says **“Appointment details aren't available to you.”** The new provider is not added to the old conversation.

## Rules enforced

- **One shared summary (ABOUT-01).** About uses the existing operational responsibility resolver, the same calculation as default routing and handled workload. Only active Colleges on active Campuses count. Assignments to inactive or non-Counselor accounts fall back to the unique Head. With no Head, or with more than one, no fallback is claimed.
- **No administration payload (ABOUT-02).** The response contains the Counselor's ID, display name, photo URL and photo time, and the Campuses with their Colleges and assignment basis. It has no email, role, designation, supervision, capability, assignment author or timestamp. It is never cached (`Cache-Control: no-store, private`), and every opening asks again.
- **Who can open it.** A Student holding a booking or Messages self capability can open About only for a Counselor offered to them: one eligible in current booking, or one from their own Appointments or Counseling conversations. Guidance staff need a capability for a surface that hosts About: Messages, Appointment management, assigned Counseling, or continuity view/request. Faculty and other roles receive 403. An unknown, inactive or non-Counselor ID, or a Counselor not offered to that Student, receives the same 404 `counselor_about_unavailable`.
- **Focused scope (ABOUT-03).** No biography, qualification, specialty, availability or profile-editing form was added. About is not case responsibility; the case workspace keeps naming the primary Counselor.
- **Rechecked Appointment context (MSG-01).** `relationship_appointment` is computed on every read, never from the historical link. It is shown to the Appointment's own Student while they hold `appointments.view_self` or `appointments.manage_self`, to its current provider, and to staff who may manage that Appointment now. Otherwise it is `null`.
- **Preserved Messages behavior (MSG-02, UX-06).** Thread membership, Seen receipts, typing, office identity, composer, contextual panels and the active E-Counseling call are unchanged. No participant is added and no history is shared.

## Backend and API

| Operation | Change |
|---|---|
| `GET /api/v1/organization/counselors/{counselor_id}/about` (`organizationGetCounselorAbout`) | New. `CounselorAboutResponse` = `counselor` (`id`, `display_name`, `profile_photo_url`, `profile_photo_updated_at`), `campuses[]` (`id`, `code`, `name`, `colleges[]` of `id`, `code`, `name`, `basis` = `ASSIGNED` or `HEAD_FALLBACK`), `checked_at`. Errors 401, 403 `permission_denied`, 404 `counselor_about_unavailable`. |
| Guidance Messages thread (`GuidanceThreadResponse`) | `counselor` is now `GuidanceCounselorPerson` (adds the two photo fields). New `relationship_appointment: GuidanceAppointmentSummary | null` (`id`, `reference_code`, `service_name`, `starts_at`, `ends_at`, `status`). |
| `GET /api/v1/guidance-messages/recipient-options` | Each Counseling relationship adds `reference_code`, `service_name`, `status`; its `counselor` carries the photo fields. |

Code: [counselor_about.py](../../be/compass/organization/counselor_about.py), the About endpoint in [organization/api.py](../../be/compass/organization/api.py), `appointment_summary_visible` in [guidance_messages/policy.py](../../be/compass/guidance_messages/policy.py), and the thread projection in [guidance_messages/api.py](../../be/compass/guidance_messages/api.py). All changes are additive response fields and one read-only operation.

## Migration and deployment

No model, migration, setting, keyring or management command changed. Deployment needs only the ordinary backend and frontend release. The frontend relies on the new response fields, so the backend must be deployed first or together.

## Frontend

- [counselor-about-dialog.tsx](../../fe/src/features/counselor-about/counselor-about-dialog.tsx): `CounselorAboutButton`, a plain `type="button"` Dialog trigger. Loading, empty, final refusal (403/404, no Retry, backend wording never shown) and retryable failure states. `staleTime: 0`, `gcTime: 0`, refetch on mount and window focus. Focus returns to the button.
- [counselor-about-presentation.ts](../../fe/src/features/counselor-about/counselor-about-presentation.ts): Campus/College rows, the fallback note and error wording.
- Booking ([booking-counselor-choice.tsx](../../fe/src/features/appointments/booking-counselor-choice.tsx)), new message ([guidance-new-message.tsx](../../fe/src/features/guidance-messages/guidance-new-message.tsx)), conversation header ([guidance-conversation.tsx](../../fe/src/features/guidance-messages/guidance-conversation.tsx)), directory ([guidance-thread-directory.tsx](../../fe/src/features/guidance-messages/guidance-thread-directory.tsx)), identity avatar, and transfer/coverage preparation.

## Verification

All runs were on 14 November 2026 against this branch, with a production test build (`NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1`) served by `next start`, as in CI.

| Check | Result |
|---|---|
| New backend tests ([test_cw6_counselor_about.py](../../be/tests/test_cw6_counselor_about.py)): content, Head fallback, ambiguous Heads, inactive College/Campus, empty summary, Student offering rule, staff and refused roles, capability boundary, anonymous; Messages photo, rechecked Appointment summary, reassignment, current status, Office thread, recipient options | 26 passed |
| Existing Messages (all 14 files), organization, catalog, Appointments and management-scope tests, with the thread key-set pins updated for the new field | 225 + 240 passed |
| OpenAPI contract test and `export_openapi --check` | 49 passed; contract current |
| `pnpm validate` (generate, lint, typecheck, build) | Passed; 5 earlier lint warnings in CW-4 test files, no errors |
| `pnpm test` | 1,298 / 1,298, including the new [counselor-about.test.mjs](../../fe/tests/counselor-about.test.mjs) |
| New mocked suite [counselor-about.browser.mjs](../../fe/tests/counselor-about.browser.mjs) | 9/9 in Chromium and WebKit |
| Affected mocked suites: guidance-messages (42), -layout (18), -contextual (29), -staff-operations (28), appointment-picker (26), user-copy (42), task-guides (76), counseling-continuity (17), counseling-coverage (9), case-coverage (41), counseling-closure (21), ecounseling-safety-access (28), ux15-consolidation (61) | All pass in both engines |
| ux-p1 | 15/16 in both engines. “Appointment desktop contextual rail and Messages dock” also fails on the unchanged CW-4 build, so it is inherited, not caused by CW-6. |
| Real Django + Next journeys (local script kept outside the repository) on a fresh `compass_cw6_browser_20261114_a` | 6/6 in Chromium and 6/6 in WebKit: booking About with real assignment and Head fallback; three conversations with one Counselor told apart; recipient About; reassigned Counselor sees no Appointment and the new provider gets 404; transfer preparation About; API boundaries (student 404 for non-Counselor, Faculty 403, office sees fallback, `no-store`). |
| Database oracle | Appointments, Colleges, Campuses, responsibilities, cases and threads byte-identical before and after; About wrote no audit or rows; the reassigned thread stayed with its original Counselor. |

Repairs made during verification:

1. The real backend showed that two Appointments at the same time look identical in the conversation list. Each row now leads with the Appointment reference.
2. Two existing assertions recorded the earlier absence of About in booking and of Appointment context in Messages. They were updated to the new contract.
3. The booking choice's keyboard ring moved to the element that now also holds the About button.

The first real-backend attempt failed only on that read-only list check. The oracle confirmed no source row changed, so the same database was reused.

## Known limitations and gaps

- About lists organization assignments only. It does not say which Counselor is responsible for a particular Student's case, by design (ABOUT-03).
- Staff conversation headers do not offer About: staff see the Student as the conversation's identity. Counselor-to-Counselor direct conversations are unchanged.
- The contextual Messages panel on Appointment and E-Counseling pages shows the photo through the shared identity avatar but has no About button; that page already names the Appointment.
- Institutional UAT and hosted CI on this exact stack are not claimed.

## Handoff to CW-7

CW-7 should include About and Messages context in the combined cross-role verification:

- Student booking and new-message About;
- a reassigned Appointment's conversation from both Counselors' side;
- the Head fallback view with a real catalog.

Keep About read-only and no-store. Do not add a participant to old Student conversations.
