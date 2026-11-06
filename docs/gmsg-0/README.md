# GMSG-0 — Guidance Messages expansion architecture, source/permission and privacy audit

**Status:** documentation-only, read-only audit. No application code, test, migration, seed,
contract, generated client, setting or Git state was changed. Nine documents in this directory are
the whole deliverable.
**Audit base:** `integration/ux15-modernization` at
`de6902200878f1413bea7a5a90166d30be92bdfc` (CENC-4), verified 2026-11-06. `origin/integration/ux15-modernization`
resolves to the same SHA. Working tree: no tracked modification; two pre-existing untracked
directories (`Claude outputs/`, `outputs/paper-screenshots/`).
**Proposal reviewed:** *COMPASS — Guidance Messages Expansion, Faculty Communication, Counselor
Collaboration, and Real-Time Messaging Enhancements* (Proposal #10),
`/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md`,
lines 7959–9012. Its reference baseline is `staging` at `0a843dae20c01984d0fb9aa46d5eef34102ab386`,
2026-10-21 (proposal line 7967), so every current-state claim in it was re-audited here.
**Claim labels:** **Verified** = static `path:line` evidence read at the audit base; **Inferred** =
reasoned from verified code; **Unknown** = evidence or command still required. Proposal text is
never evidence of current behavior.
**Data handling:** no Student PII, credential, key, production/staging record, message body or
ciphertext is reproduced. Only source paths, line numbers, enum codes and field names appear.

## Why this audit exists

Guidance Messages today is a two-kind, Student-centric encrypted chat (Verified
[be/compass/guidance_messages/models.py:11-14](../../be/compass/guidance_messages/models.py#L11-L14)).
Proposal #10 asks it to carry six conversation families, four of which have no Student participant —
and two of which carry confidential Counselor case content. The proposal itself names the failure
mode: storing a referred Student in the mandatory `student` field, or handing out blanket
`guidance_messages.manage`, leaks Faculty–GCO correspondence to the Student named in it (proposal
lines 8074, 8948). The proposal was also written before `FACULTY`, Referral submitter provenance,
continuity grants and SAR placement existed, so its dependency ordering (§4.8, line 8104) is stale.

GMSG-0 answers, from code: what exists, what each proposed kind would require, which dependencies
are real, how the schema can change without disclosing anything, and what GMSG-1 may safely do.
It changes nothing.

The proposal's GMSG-0 row requires a "verified relationship matrix, migration strategy and approved
scope/gates" (proposal line 8664). This package supplies the matrix, the migration strategy and
**engineering-provisional** scope. It does **not** supply GCO/DPO/UCN approval; institutional
approvals are recorded as separate gates in [`decisions.md`](decisions.md).

## Package map

| File | Question answered |
|---|---|
| [`current-state.md`](current-state.md) | Models, constraints, encryption, services, API/DTOs, FE, realtime, notifications, work queues — with counts |
| [`access-matrix.md`](access-matrix.md) | Six kinds × roles × every access surface, positive and negative rules, current vs proposed |
| [`source-lifecycle.md`](source-lifecycle.md) | Referral void/closure, grant expiry/revocation, Appointment reassignment, placement change, deactivation, resolve/reopen |
| [`ux-journeys.md`](ux-journeys.md) | Current journeys and Student-assuming copy, proposed journeys, truthful-copy assessment |
| [`decisions.md`](decisions.md) | D-GMSG-01..18 mapped to proposal §26 plus D-GMSG-19..30 surfaced by this audit |
| [`implementation-plan.md`](implementation-plan.md) | GMSG-1 foundation only (exact files, constraints, tests, rollback) and GMSG-2..8 sequencing |
| [`risks.md`](risks.md) | Risk register with likelihood, impact, mitigation and review trigger |
| [`validation.md`](validation.md) | Method, commands run verbatim, first-run failures, everything deliberately not run, evidence limits |

## Static counts at the audit base

| Item | Count | Evidence |
|---|---|---|
| `GuidanceThread` kinds | 2 (`OFFICE`, `COUNSELING`) | Verified `models.py:11-13` |
| Guidance Messages models | 4 | Verified `models.py:21,118,146,170` |
| Guidance Messages migrations | 1 (`0001_canonical_baseline`) | Verified `be/compass/guidance_messages/migrations/` |
| Thread/message/read-state DB constraints | 9 + 5 template constraints | Verified `models.py:79-115,133-143,157-162,207-227` |
| Encryption binding fields | 4 (thread, message, sequence, sender) | Verified `content.py:40-46` |
| Message body limit / schema version | 4000 / 1 | Verified `content.py:10-11` |
| OpenAPI operations | 21 (`guidanceMessages*`) | Verified `be/compass/guidance_messages/api.py:291-668` |
| Guidance Messages capabilities | 5 | Verified `be/compass/accounts/policy.py:152-172` |
| `services.py` public functions | 14 | Verified `services.py:102,111,126,135,201,214,284,328,363,379,410,439,470,478` |
| Realtime public event types | 5 total; **1** for Guidance Messages | Verified `be/realtime_service/protocol.py:46-54` |
| Notification events / target types / email deep-link routes | 30 / 12 / 9 | Verified `be/compass/notifications/policy.py:42-71,27-38`, `email_links.py:40-51` |
| Notification events for messages | **0** | Verified by grep, see `current-state.md` §9 |
| Backend test functions (`test_guidance_messages*.py`) | 116 across 7 files | Verified `be/tests/test_guidance_messages*.py` |
| FE feature files / route pages / FE test files | 25 / 4 (+1 layout) / 4 | Verified `fe/src/features/guidance-messages/`, `fe/src/app/(portal)/portal/messages/` |
| Canonical roles / designations / capability catalog | 6 / 2 / 95 | Verified `accounts/policy.py:29-76`, `grep -c 'code="'` = 95 capability codes |
| Faculty capability ceiling | 2 (`referrals.submit_self`, `referrals.view_submitted_self`) | Verified `accounts/policy.py:79` |

## Top-10 findings

1. **Verified — the `student` FK is non-nullable and `PROTECT`**, and a partial unique index allows
   exactly one open Office thread per Student. Both are load-bearing for the four proposed
   non-Student kinds. [models.py:27-29](../../be/compass/guidance_messages/models.py#L27-L29),
   `:110-114`.
2. **Verified — the shape constraint is a `CHECK`, not a type system.**
   `gm_thread_family_shape` admits exactly two shapes (`OFFICE` = college, no counselor/appointment;
   `COUNSELING` = counselor + appointment + no handler). No new kind can be inserted without editing
   it. [models.py:80-97](../../be/compass/guidance_messages/models.py#L80-L97).
3. **Verified — `GuidanceThreadResponse` requires `student: GuidancePerson`**, so any non-Student
   thread forces a contract change; the same DTO already returns `assigned_to` (a staff person) to
   every authorized reader, including the Student.
   [api.py:49-63](../../be/compass/guidance_messages/api.py#L49-L63), `:229-253`.
4. **Verified — authorization is role-first, capability-second.** `require_actor` rejects any role
   outside `{STUDENT, COUNSELOR, GUIDANCE_SERVICES_STAFF}` *before* checking the capability, so an
   `UserCapabilityOverride` granted to IT Admin or Institutional Officer cannot open Messages
   (models.py:260-263, accounts/models.py:337).
   [policy.py:31-40](../../be/compass/guidance_messages/policy.py#L31-L40).
5. **Verified — Counseling threads are authorized by persisted participants only, and reassignment
   never transfers them** (`appointment_context` docstring and code).
   [services.py:328-360](../../be/compass/guidance_messages/services.py#L328-L360). Appointment
   reassignment does not consult `GuidanceThread` at all
   ([be/compass/appointments/services.py:1377-1393](../../be/compass/appointments/services.py#L1377-L1393)).
6. **Verified — there is no messaging authority anywhere in the continuity grant.**
   `ContinuitySourceKind` is closed to `ENCOUNTER` and `ROUTINE_EVALUATION`, and the module docstring
   states "Metadata-only professional continuity provenance; no content authority."
   [continuity_models.py:1,34-41](../../be/compass/counseling/continuity_models.py#L34-L41).
   **GMSG-5 has no authority to bind to today and stays blocked.**
7. **Verified — no Guidance Messages notification path exists.** 30 notification events, 12 target
   types and 9 authenticated email deep-link routes, none for messages; `messages.thread_changed`
   appears only in the realtime registry and the Guidance publisher. Proposal §17.4's "optional
   Notification" is entirely unbuilt.
   [notifications/policy.py:27-71](../../be/compass/notifications/policy.py#L27-L71),
   `email_links.py:40-51`.
8. **Verified — reply-needed work hard-codes "last sender is the Student"** and only matches OFFICE
   with `assigned_to_id=actor` or COUNSELING with `counselor_id=actor`, so unassigned open Office
   threads never appear as reply-needed.
   [work.py:30-36](../../be/compass/guidance_messages/work.py#L30-L36).
9. **Verified — mark-read already satisfies the proposal's strictest requirement**: it is an explicit
   `PATCH /threads/{id}/read`, never a GET side effect, monotonic in Python under a thread row lock,
   and the frontend fires it only when the conversation is open, visible and scrolled to the newest
   loaded message.
   [services.py:363-376](../../be/compass/guidance_messages/services.py#L363-L376),
   [api.py:586-596](../../be/compass/guidance_messages/api.py#L586-L596),
   `fe/src/features/guidance-messages/guidance-conversation-data.ts:129-152`.
10. **Verified — the realtime transport cannot carry typing as designed.** The public registry is a
    closed 5-event allowlist with exact field sets and canonical-UUID validation, delivery is
    per-user channel only, and there is no thread/room subscription and no client→server frame
    channel. A typing indicator needs a new registered event *and* an inbound path that does not
    exist. [protocol.py:46-54,141-146,213-231](../../be/realtime_service/protocol.py#L46-L54),
    `be/realtime_service/app.py:260-262,334-348`.

### Drift corrections to the audit brief itself

- Brief said the realtime allowlist is "Guidance Messages has exactly one" at `protocol.py:46-50`;
  the registry is a 5-event closed map spanning `:46-54`. Guidance still has exactly one event
  (`:50`). **Verified.**
- Brief claimed `services.py` exposes "12" services; there are **14** public functions (count table
  above). **Verified.**
- Brief cited `continuity_models.py:44-95` for the grant; the model spans `:44-190` and `original_counselor`
  is **nullable** (`:49`), which the brief omitted. **Verified.**
- Brief §3 assumed `docs/notif-04` claims hold; `docs/notif-04/event-channel-matrix.md:43` documents the
  **pre-rename** event/target `counseling.shared_summary.published` / `COUNSELING_SHARED_SUMMARY` and the
  publisher `counseling/shared_summaries.py:publish_assigned_shared_summary`. Code has
  `counseling.student_session_summary.published` (`notifications/policy.py:62`),
  `STUDENT_SESSION_SUMMARY` (`:31`) and
  `counseling/student_session_summaries.py:118` `publish_assigned_student_session_summary`. The old module
  does not exist as source; the old codes survive only in the cutover migration's legacy-detection
  predicate (`counseling/migrations/0002_student_session_summary_contract.py:23-25`) and its preflight
  command (`:48-50`). **Verified doc-vs-code drift, recorded in `risks.md` R-21.**

## Definition-of-done result

| Requirement | Result |
|---|---|
| All nine files exist under `docs/gmsg-0/` | **Met** — README, current-state, access-matrix, source-lifecycle, ux-journeys, decisions, implementation-plan, risks, validation |
| Every substantive claim labelled with `path:line` | **Met** — Verified/Inferred/Unknown labels throughout; Unknowns listed rather than guessed |
| All six kinds covered in the matrix | **Met** — `access-matrix.md` §2 |
| `D-GMSG-01..18` mapped 1:1 to proposal §26 (lines 8855–8878) | **Met** — plus `D-GMSG-19..30` |
| GMSG-1 plan names exact files | **Met** — `implementation-plan.md` §2 |
| `validation.md` states honestly what was not run | **Met** |
| No code/schema/contract/test change attempted | **Met** — the audit stayed documentation-only; no stop condition forced an edit |
| Nothing committed or pushed | **Met** — changes left uncommitted |
