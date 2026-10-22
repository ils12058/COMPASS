import assert from "node:assert/strict";
import test from "node:test";

import { getGssHomeDestinations, getGssManagedAppointmentParams, presentGssOperations, presentGssWork } from "../src/features/portal/home/gss-home-presentation.ts";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import { gssHomeWork } from "./support/ux15-gss-home-fixtures.mjs";

const operations = (overrides = {}) => ({
  generated_at: "2026-10-22T01:30:00Z",
  backlog: {
    guidance_messages: { count: 0, oldest_waiting_since: null },
    routine_evaluations: null,
    good_moral_preparation: { count: 3, oldest_waiting_since: "2026-10-20T09:00:00+08:00" },
    good_moral_issuance: { count: 1, oldest_waiting_since: "2026-10-21T09:00:00+08:00" },
    call_slips_due: { count: 0, oldest_due_at: null },
    ...overrides,
  },
  schedule: {
    upcoming_self_appointments_count: null,
    upcoming_managed_appointments_count: 6,
    active_call_slips_count: 5,
  },
});

test("GSS managed schedule uses the supported bounded, Manila-date Appointment filters", () => {
  assert.deepEqual(getGssManagedAppointmentParams("2026-10-22"), {
    status: "SCHEDULED",
    from_date: "2026-10-22",
    to_date: "2026-10-22",
    ordering: "EARLIEST_START",
    page: 1,
    page_size: 5,
  });
});

test("GSS operations keep zero distinct from null and label Counselor issuance as context", () => {
  const user = homeWorld({ role: "GUIDANCE_SERVICES_STAFF" }).account;
  const metrics = presentGssOperations(operations(), user);
  assert.deepEqual(metrics.map(({ key, count }) => [key, count]), [
    ["messages", 0],
    ["good-moral-preparation", 3],
    ["good-moral-issuance", 1],
    ["call-slips", 0],
  ]);
  assert.equal(metrics.some((metric) => metric.key === "routine-evaluations"), false);
  assert.equal(metrics.find((metric) => metric.key === "good-moral-issuance")?.label, "Good Moral requests awaiting Counselor issuance");
  assert.equal(metrics.find((metric) => metric.key === "good-moral-issuance")?.href, undefined);

  const unavailable = presentGssOperations(operations({
    guidance_messages: null,
    good_moral_preparation: null,
    good_moral_issuance: null,
    call_slips_due: null,
  }), user);
  assert.deepEqual(unavailable, []);
});

test("GSS work copy never turns Counselor issuance or evaluations into GSS actions", () => {
  const user = homeWorld({ role: "GUIDANCE_SERVICES_STAFF" }).account;
  const issuance = presentGssWork(gssHomeWork.find((item) => item.kind === "GOOD_MORAL_PREPARATION") && {
    ...gssHomeWork[2],
    kind: "GOOD_MORAL_ISSUANCE",
  }, user, "2026-10-22T01:30:00Z");
  assert.equal(issuance?.title, "Good Moral request awaiting Counselor issuance");
  assert.equal(issuance?.actionLabel, "View request");
  assert.equal(issuance?.href.endsWith(gssHomeWork[2].source_id), true);

  const evaluation = presentGssWork({ ...gssHomeWork[0], kind: "ROUTINE_EVALUATION" }, user, "2026-10-22T01:30:00Z");
  assert.equal(evaluation, null);
});

test("GSS continuation links are selected only from existing authorized workspaces", () => {
  const restricted = homeWorld({ role: "GUIDANCE_SERVICES_STAFF", capabilities: [] }).account;
  const restrictedLinks = getGssHomeDestinations(restricted);
  assert.deepEqual(restrictedLinks.map((link) => link.href), ["/portal/operations"]);

  const user = homeWorld({ role: "GUIDANCE_SERVICES_STAFF" }).account;
  const referralAuthorizedUser = { ...user, capabilities: [...user.capabilities, "referrals.view"] };
  const destinations = getGssHomeDestinations(referralAuthorizedUser);
  assert.ok(destinations.length <= 6);
  assert.ok(destinations.some((link) => link.href === "/portal/operations"));
  assert.ok(destinations.some((link) => link.href === "/portal/referrals"));
  assert.deepEqual(new Set(destinations.map((link) => link.href)).size, destinations.length);
});
