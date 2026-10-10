import assert from "node:assert/strict";
import { test } from "node:test";

import { CompassApiError } from "../src/lib/api/errors.ts";
import { appointmentErrorMessage } from "../src/features/appointments/appointments-shared.tsx";
import { counselingErrorMessage, expiredContextEncounterMessage } from "../src/features/counseling/counseling-shared.tsx";
import { goodMoralErrorMessage } from "../src/features/good-moral/good-moral-shared.tsx";
import { reportErrorMessage } from "../src/features/reports/reports-shared.tsx";
import { availabilityErrorMessage } from "../src/features/availability/availability-shared.tsx";
import { servicesErrorMessage } from "../src/features/services/services-shared.tsx";
import { feedbackErrorMessage } from "../src/features/feedback/feedback-shared.tsx";
import { resourceErrorMessage } from "../src/features/resources/resource-errors.ts";
import { announcementErrorMessage } from "../src/features/announcements/announcement-errors.ts";
import { privacyErrorMessage } from "../src/features/privacy-governance/privacy-governance-errors.ts";
import { shouldShowOverviewAttention } from "../src/features/portal/home/overview-work.ts";

function apiError(code, message) {
  return new CompassApiError({
    status: 409,
    body: { error: { code, message } },
    headers: {},
    method: "POST",
    url: "/api/v1/test",
  });
}

test("attention section needs work, loading, or a stale-data notice", () => {
  assert.equal(shouldShowOverviewAttention(0, false, 0), false);
  assert.equal(shouldShowOverviewAttention(1, false, 0), true);
  assert.equal(shouldShowOverviewAttention(0, true, 0), true);
  assert.equal(shouldShowOverviewAttention(0, false, 1), true);
});

test("expired counseling context mentions an encounter only when one is known", () => {
  assert.equal(expiredContextEncounterMessage(false), null);
  assert.match(expiredContextEncounterMessage(true), /recorded encounter remains available/);
});

test("unknown backend messages stay out of product errors", () => {
  const raw = "institutional_id and delivery_mode failed at replay boundary";
  const error = apiError("unrecognized_conflict", raw);
  const fallback = "The request could not be completed. Refresh and try again.";
  for (const mapError of [
    appointmentErrorMessage,
    counselingErrorMessage,
    goodMoralErrorMessage,
    reportErrorMessage,
    availabilityErrorMessage,
    servicesErrorMessage,
    feedbackErrorMessage,
    resourceErrorMessage,
    announcementErrorMessage,
  ]) {
    assert.equal(mapError(error, fallback), fallback);
  }
});

test("a known appointment conflict keeps a useful next step", () => {
  const message = appointmentErrorMessage(
    apiError("appointment_time_conflict", "delivery_mode database conflict"),
    "Booking failed.",
  );
  assert.match(message, /Choose another available time/);
  assert.doesNotMatch(message, /delivery_mode/);
});

test("prototype property names cannot become product error copy", () => {
  const fallback = "Review the form and try again.";
  assert.equal(appointmentErrorMessage(apiError("constructor", "raw"), fallback), fallback);
  assert.equal(resourceErrorMessage(apiError("invalid_resource_input", "__proto__"), fallback), fallback);
  assert.equal(announcementErrorMessage(apiError("invalid_announcement_input", "__proto__"), fallback), fallback);
  assert.equal(
    privacyErrorMessage(apiError("invalid_privacy_governance_input", "__proto__"), fallback),
    "Some privacy record details were not accepted. Review them and try again.",
  );
});
