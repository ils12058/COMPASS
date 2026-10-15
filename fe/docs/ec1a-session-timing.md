# E-Counseling Scheduled-End Warnings & Overtime Awareness (EC-1 Option A)

## 1. Overview & Objective

This document outlines the frontend implementation of **EC-1 Option A (Informational Warnings Only)** for COMPASS E-Counseling sessions.

The objective is to provide timely, respectful awareness to both Students and Counselors as scheduled appointment boundaries approach and pass, without disrupting active counseling conversations or interfering with media governance.

### Core Principle: Informational Only
- **Scheduled appointment end does not equal call termination or counseling completion.**
- The system **never** automatically disconnects, leaves, revokes tokens, ejects participants, stops governed media recording/transcription, or marks an Appointment or Counseling Encounter as completed.
- All ending, extension, and recording cessation actions remain deliberate human decisions.

---

## 2. Presentation Phases & Authoritative Schedule

The source of truth for scheduled appointment duration is `Appointment.starts_at` and `Appointment.ends_at` provided by the authorized workspace API (`/api/v1/e-counseling/(me/)appointments/:id`).

| Timing | Phase | UI Notice Title | Compact Label | Behavior & Semantics |
|---|---|---|---|---|
| Earlier than 10 minutes before `ends_at` | `NORMAL` | *(None)* | *(None)* | Standard active call stage and dock. No warnings displayed. |
| 10 to > 5 minutes remaining | `APPROACHING_END` | "Appointment ending soon" | `10 min left` | Non-blocking initial advance warning. Informs participants to prepare to wrap up and coordinate next steps. |
| 5 minutes to scheduled end | `FINAL_REMINDER` | "5 minutes remaining" | `5 min left` | Non-blocking follow-up reminder. |
| At scheduled end (scheduled end window) | `SCHEDULED_END_REACHED` | "Scheduled time reached" | `Past scheduled end` | Notifies that scheduled appointment time has ended. Coordinates next steps if discussion is still ongoing. |
| After scheduled end while connected | `OVERTIME` | "Past scheduled end" | `Past scheduled end` | Persistent, restrained overtime indicator while the call remains connected. |

---

## 3. Single Persistent Runtime Ownership

In accordance with ADR-094 (Persistent E-Counseling Runtime and Global Call Continuity), scheduled-end warning logic is centrally owned by `ActiveECounselingRuntimeProvider` in `fe/src/features/ecounseling/runtime/active-call-runtime.tsx`.

1. **Pure Session Timing Engine (`session-timing.ts`)**:
   - Accepts canonical `endsAt`, current `now` timestamp, and `connected` status.
   - Computes deterministic `SessionTimingPhase`, `SessionTimingNotice`, delay until next transition (`getNextTimingDelayMs`), and screen reader announcement (`getTimingTransitionAnnouncement`).
   - Free of React, Daily, or DOM dependencies; fully unit-tested across all edge cases.

2. **Single Runtime Timer**:
   - `ActiveECounselingRuntimeProvider` maintains a single lightweight dynamic timer for the next phase transition.
   - Recomputes on `visibilitychange`, `focus`, and `online` events to ensure resilience against device sleep, tab suspension, and clock jumps.
   - React 19-compliant state derivation avoids cascading renders or `ref`-in-render violations.

3. **Shared Context Projection (`active-call-context.ts`)**:
   - Exposes `timing: ActiveECounselingTiming` through `useActiveECounselingCall()`.
   - Both full `CallStage` and `GlobalCallDock` consume the exact same canonical state.

---

## 4. UI Presentation Design & Accessibility

### Full Call Stage (`CallStage`)
- Displayed in the top overlay near participant connection status.
- Designed as a restrained, non-blocking status pill with a subtle `Clock` icon and amber/warning accent.
- Does not obstruct video streams, participant indicators, or governed capture controls (Record / Transcript).
- No audible alerts, modals, forced acknowledgments, or jarring countdown tickers.

### Global Call Dock (`GlobalCallDock`)
- **Collapsed Presentation**: Features a compact label (`10 min left`, `5 min left`, `Past scheduled end`) directly in the dock header row.
- **Strict Height Constraint**: Preserves the single-row collapsed height (< 80px), passing all layout boundary assertions across desktop, laptop, tablet, and mobile viewports.
- **Expanded Presentation**: Displays the full explanatory notice box with heading and supportive copy above active call controls.

### Accessibility (a11y)
- **Live-Region Announcements**: A single polite live-region (`<p aria-live="polite" className="sr-only">`) is rendered at the portal runtime root.
- **Announcement Deduplication**: Screen readers receive a single announcement upon phase transitions (`NORMAL` -> `APPROACHING_END` -> `FINAL_REMINDER` -> `SCHEDULED_END_REACHED`). Transitioning from `SCHEDULED_END_REACHED` to `OVERTIME` does not trigger redundant announcements, avoiding audio clutter during active dialogue.

---

## 5. Safety Invariants & Governance

1. **Decoupled from Daily Lifecycle**:
   - Reaching `ends_at` or overtime never invokes `session.leave()` or `session.dispose()`.
   - Daily room tokens and room expirations remain unchanged.
2. **Decoupled from Media Capture**:
   - Timing transitions never trigger backend capture cessation (`/recording/stop` or `/transcription/stop`).
   - Active recording and transcription indicators remain visible and governed.
3. **Decoupled from Record Status**:
   - No backend mutations to `Appointment.status` or `CounselingEncounter` are made based on timing warnings.
4. **Rescheduling & Clock Drift**:
   - When an appointment is rescheduled before room binding, `ActiveECounselingRuntimeProvider` dynamically tracks the updated `ends_at` from the workspace query and resets timing keys.

---

## 6. GCO Review Items

The following copy and interval thresholds are prepared for institutional Guidance and Counseling Office (GCO) review:

1. **Wording Adjustments**:
   - 10-minute warning: *"Your appointment is scheduled to end in 10 minutes. Please prepare to wrap up and coordinate any next steps."*
   - 5-minute reminder: *"Your scheduled appointment ends in 5 minutes."*
   - At-end notice: *"The scheduled appointment time has ended. If your discussion is still ongoing, please coordinate the next steps."*
   - Overtime label: *"Past scheduled end"* (helper text: *"The scheduled appointment time has passed."*)
2. **Timing Intervals**:
   - Proposed 10-minute and 5-minute thresholds.
   - Proposed 60-second transition window for `SCHEDULED_END_REACHED` before persistent `OVERTIME` awareness.
3. **Institutional Overtime Policy**:
   - COMPASS currently permits sessions to continue past scheduled time if participants remain connected. Any future policy regarding hard boundaries will require independent administrative and institutional review.
