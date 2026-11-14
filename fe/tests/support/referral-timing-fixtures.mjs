// Synthetic CW-5 responses. Legacy detail fixtures use an explicit absent supplement.
export const timingVersion = "2026-11-13T02:00:00.123456+00:00";

export function emptyReferralTiming(referralId, changes = {}) {
  return {
    referral_id: referralId, timing_status: "NOT_PROVIDED", reported: null,
    verifications: [], latest_verification_id: null, referral_updated_at: timingVersion,
    referral_closed: false, can_verify: false, ...changes,
  };
}

export function manilaDay(now = new Date()) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Manila", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(now);
}

export function civilDays(day, offset) {
  const value = new Date(`${day}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + offset);
  return value.toISOString().slice(0, 10);
}

export function reportedTimingFixture(changes = {}) {
  return {
    id: "c5000000-0000-4000-8000-000000000001", answer_kind: "KNOWN",
    windows: [
      { information_type: "STUDENT_AVAILABLE", pattern: "SPECIFIC_DATE", date: "2026-01-01", weekday: null, valid_until: null, start_time: "09:00:00", end_time: "10:00:00", expired: true },
      { information_type: "CLASS_RELEASE", pattern: "RECURRING_WEEKDAY", date: null, weekday: "SATURDAY", valid_until: "2026-01-31", start_time: "13:00:00", end_time: "14:00:00", expired: true },
    ],
    note: "Synthetic reported scheduling constraints", submission_channel: "FACULTY_PORTAL",
    author_id: "c5000000-0000-4000-8000-000000000002", author_name: "Synthetic Faculty",
    created_at: "2026-01-01T00:00:00Z", ...changes,
  };
}
