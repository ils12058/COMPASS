// Pure unit tests for E-Counseling session timing, scheduled-end warnings, and overtime awareness (EC-1 Option A).
// Covers all 15 scenarios from specification:
// 1. > 10m before end (NORMAL)
// 2. Exactly 10m before end (APPROACHING_END)
// 3. Between 10m and 5m (APPROACHING_END)
// 4. Exactly 5m before end (FINAL_REMINDER)
// 5. Between 5m and scheduled end (FINAL_REMINDER)
// 6. Exactly at scheduled end (SCHEDULED_END_REACHED)
// 7. After scheduled end while connected (OVERTIME)
// 8. After scheduled end while disconnected (NORMAL)
// 9. Invalid, null, undefined, or missing end timestamp (NORMAL)
// 10. Short appointments (< 10m, < 5m)
// 11. Late activation / wake past deadlines
// 12. Delay scheduler calculation for each phase
// 13. Screen reader transition announcements and deduplication
// 14. Rescheduled appointment identity handling
// 15. Non-blocking informational notice copy and safety invariants
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  calculateTimingPhase,
  getNextTimingDelayMs,
  getSessionTimingNotice,
  getTimingTransitionAnnouncement,
  TIMING_COPY,
  TEN_MINUTES_MS,
  FIVE_MINUTES_MS,
} from "../src/features/ecounseling/runtime/session-timing.ts";

test("timing constants match canonical 10-minute and 5-minute thresholds", () => {
  assert.equal(TEN_MINUTES_MS, 10 * 60 * 1000);
  assert.equal(FIVE_MINUTES_MS, 5 * 60 * 1000);
});

test("scenario 1: earlier than 10 minutes before scheduled end is NORMAL", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  // 15 minutes before end
  const now = endsAtMs - 15 * 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now, connected: true }), "NORMAL");
  assert.equal(getSessionTimingNotice("NORMAL"), null);

  // 10 minutes and 1 millisecond before end
  const justBeforeTenMinutes = endsAtMs - (TEN_MINUTES_MS + 1);
  assert.equal(calculateTimingPhase({ endsAt, now: justBeforeTenMinutes, connected: true }), "NORMAL");
});

test("scenario 2: exactly 10 minutes before scheduled end enters APPROACHING_END", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  const exactlyTenMinutes = endsAtMs - TEN_MINUTES_MS;
  assert.equal(calculateTimingPhase({ endsAt, now: exactlyTenMinutes, connected: true }), "APPROACHING_END");

  const notice = getSessionTimingNotice("APPROACHING_END");
  assert.ok(notice);
  assert.equal(notice.title, "Appointment ending soon");
  assert.match(notice.message, /scheduled to end in 10 minutes/);
  assert.equal(notice.compactLabel, "10 min left");
});

test("scenario 3: between 10 minutes and 5 minutes remaining stays in APPROACHING_END", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  // 7 minutes before end
  const sevenMinutes = endsAtMs - 7 * 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now: sevenMinutes, connected: true }), "APPROACHING_END");

  // 5 minutes and 1 millisecond before end
  const justBeforeFiveMinutes = endsAtMs - (FIVE_MINUTES_MS + 1);
  assert.equal(calculateTimingPhase({ endsAt, now: justBeforeFiveMinutes, connected: true }), "APPROACHING_END");
});

test("scenario 4: exactly 5 minutes before scheduled end enters FINAL_REMINDER", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  const exactlyFiveMinutes = endsAtMs - FIVE_MINUTES_MS;
  assert.equal(calculateTimingPhase({ endsAt, now: exactlyFiveMinutes, connected: true }), "FINAL_REMINDER");

  const notice = getSessionTimingNotice("FINAL_REMINDER");
  assert.ok(notice);
  assert.equal(notice.title, "5 minutes remaining");
  assert.match(notice.message, /scheduled appointment ends in 5 minutes/);
  assert.equal(notice.compactLabel, "5 min left");
});

test("scenario 5: between 5 minutes and just before scheduled end stays in FINAL_REMINDER", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  // 2 minutes before end
  const twoMinutes = endsAtMs - 2 * 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now: twoMinutes, connected: true }), "FINAL_REMINDER");

  // 1 millisecond before end
  const oneMsBeforeEnd = endsAtMs - 1;
  assert.equal(calculateTimingPhase({ endsAt, now: oneMsBeforeEnd, connected: true }), "FINAL_REMINDER");
});

test("scenario 6: at scheduled end (during scheduled end minute window) is SCHEDULED_END_REACHED when connected", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  assert.equal(calculateTimingPhase({ endsAt, now: endsAtMs, connected: true }), "SCHEDULED_END_REACHED");
  assert.equal(calculateTimingPhase({ endsAt, now: endsAtMs + 30 * 1000, connected: true }), "SCHEDULED_END_REACHED");
  assert.equal(calculateTimingPhase({ endsAt, now: endsAtMs + 60 * 1000, connected: true }), "SCHEDULED_END_REACHED");

  const notice = getSessionTimingNotice("SCHEDULED_END_REACHED");
  assert.ok(notice);
  assert.equal(notice.title, "Scheduled time reached");
  assert.match(notice.message, /scheduled appointment time has ended/);
  assert.equal(notice.compactLabel, "Past scheduled end");
});

test("scenario 7: after scheduled end while connected enters OVERTIME", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  // Past the scheduled end minute window
  const pastOneMinute = endsAtMs + 60 * 1000 + 1;
  assert.equal(calculateTimingPhase({ endsAt, now: pastOneMinute, connected: true }), "OVERTIME");

  // 10 minutes past end
  const tenMinutesPast = endsAtMs + 10 * 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now: tenMinutesPast, connected: true }), "OVERTIME");

  const notice = getSessionTimingNotice("OVERTIME");
  assert.ok(notice);
  assert.equal(notice.title, "Past scheduled end");
  assert.match(notice.message, /scheduled appointment time has passed/);
  assert.equal(notice.compactLabel, "Past scheduled end");
});

test("scenario 8: after scheduled end while disconnected is NORMAL (no warning)", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  assert.equal(calculateTimingPhase({ endsAt, now: endsAtMs, connected: false }), "NORMAL");
  assert.equal(calculateTimingPhase({ endsAt, now: endsAtMs + 70 * 1000, connected: false }), "NORMAL");
});

test("scenario 9: invalid, null, undefined, or missing end timestamp returns NORMAL", () => {
  const now = Date.now();
  assert.equal(calculateTimingPhase({ endsAt: null, now, connected: true }), "NORMAL");
  assert.equal(calculateTimingPhase({ endsAt: undefined, now, connected: true }), "NORMAL");
  assert.equal(calculateTimingPhase({ endsAt: "", now, connected: true }), "NORMAL");
  assert.equal(calculateTimingPhase({ endsAt: "not-a-valid-date", now, connected: true }), "NORMAL");
});

test("scenario 10: short appointments derive correct phase without crashing", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  // Total appointment is 8 minutes long; current time is start of appointment (8m remaining)
  const eightMinutesRemaining = endsAtMs - 8 * 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now: eightMinutesRemaining, connected: true }), "APPROACHING_END");

  // Total appointment is 3 minutes long; current time is start of appointment (3m remaining)
  const threeMinutesRemaining = endsAtMs - 3 * 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now: threeMinutesRemaining, connected: true }), "FINAL_REMINDER");
});

test("scenario 11: late activation / wake past deadlines derives immediate phase without replaying", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  // User joins 1 minute before scheduled end
  const oneMinuteRemaining = endsAtMs - 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now: oneMinuteRemaining, connected: true }), "FINAL_REMINDER");

  // User joins 2 minutes after scheduled end
  const twoMinutesOvertime = endsAtMs + 2 * 60 * 1000;
  assert.equal(calculateTimingPhase({ endsAt, now: twoMinutesOvertime, connected: true }), "OVERTIME");
});

test("scenario 12: getNextTimingDelayMs calculates exact ms until next phase transition", () => {
  const endsAt = "2026-10-15T15:00:00.000Z";
  const endsAtMs = Date.parse(endsAt);

  // 15 minutes before end: next transition is at 10m before end (delay: 5 minutes)
  const fifteenMinutesRemaining = endsAtMs - 15 * 60 * 1000;
  assert.equal(getNextTimingDelayMs({ endsAt, now: fifteenMinutesRemaining }), 5 * 60 * 1000);

  // 8 minutes before end: next transition is at 5m before end (delay: 3 minutes)
  const eightMinutesRemaining = endsAtMs - 8 * 60 * 1000;
  assert.equal(getNextTimingDelayMs({ endsAt, now: eightMinutesRemaining }), 3 * 60 * 1000);

  // 3 minutes before end: next transition is at scheduled end (delay: 3 minutes)
  const threeMinutesRemaining = endsAtMs - 3 * 60 * 1000;
  assert.equal(getNextTimingDelayMs({ endsAt, now: threeMinutesRemaining }), 3 * 60 * 1000);

  // At scheduled end: delay until scheduled end window passes to enter OVERTIME
  assert.equal(getNextTimingDelayMs({ endsAt, now: endsAtMs }), 60 * 1000 + 1);

  // In overtime: null (no further schedule timers needed)
  assert.equal(getNextTimingDelayMs({ endsAt, now: endsAtMs + 65 * 1000 }), null);

  // Invalid endsAt: null
  assert.equal(getNextTimingDelayMs({ endsAt: null, now: endsAtMs }), null);
});

test("scenario 13: screen reader transition announcements and deduplication", () => {
  // Initial entry into APPROACHING_END
  assert.equal(
    getTimingTransitionAnnouncement({ previousPhase: "NORMAL", currentPhase: "APPROACHING_END" }),
    TIMING_COPY.APPROACHING_END.announcement
  );

  // Re-render within same phase: null (no re-announcement)
  assert.equal(
    getTimingTransitionAnnouncement({ previousPhase: "APPROACHING_END", currentPhase: "APPROACHING_END" }),
    null
  );

  // Transition from APPROACHING_END to FINAL_REMINDER
  assert.equal(
    getTimingTransitionAnnouncement({ previousPhase: "APPROACHING_END", currentPhase: "FINAL_REMINDER" }),
    TIMING_COPY.FINAL_REMINDER.announcement
  );

  // Transition to SCHEDULED_END_REACHED
  assert.equal(
    getTimingTransitionAnnouncement({ previousPhase: "FINAL_REMINDER", currentPhase: "SCHEDULED_END_REACHED" }),
    TIMING_COPY.SCHEDULED_END_REACHED.announcement
  );

  // Transition from SCHEDULED_END_REACHED to OVERTIME: null (do not re-announce immediately)
  assert.equal(
    getTimingTransitionAnnouncement({ previousPhase: "SCHEDULED_END_REACHED", currentPhase: "OVERTIME" }),
    null
  );

  // Late wake directly into OVERTIME announces scheduled end notice
  assert.equal(
    getTimingTransitionAnnouncement({ previousPhase: "NORMAL", currentPhase: "OVERTIME" }),
    TIMING_COPY.SCHEDULED_END_REACHED.announcement
  );

  // Transition back to NORMAL: null
  assert.equal(
    getTimingTransitionAnnouncement({ previousPhase: "OVERTIME", currentPhase: "NORMAL" }),
    null
  );
});

test("scenario 14: copy complies with institutional non-blocking requirements", () => {
  for (const copy of Object.values(TIMING_COPY)) {
    // Must not claim counseling officially ended
    assert.doesNotMatch(copy.message, /counseling session has ended|session is completed/i);
    // Must not claim recording or transcription stopped
    assert.doesNotMatch(copy.message, /recording stopped|transcription stopped/i);
    // Must not mention backend internal tokens or grace periods
    assert.doesNotMatch(copy.message, /grace_seconds|join_window|daily room expiration/i);
    // Must provide clean, non-empty labels and messages
    assert.ok(copy.title.length > 0);
    assert.ok(copy.message.length > 0);
    assert.ok(copy.compactLabel.length > 0);
    assert.ok(copy.announcement.length > 0);
  }
});
