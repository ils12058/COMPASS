import assert from "node:assert/strict";
import { test } from "node:test";
import { bookingResultIsUncertain, hasActiveRegistrationForSession } from "../src/features/appointments/booking-recovery.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";

const api = status => new CompassApiError({ status, body: {}, headers: {}, method: "POST", url: "/api/v1/test" });

test("only an exact active registration confirms the session", () => {
  const rows = [{ session_id: "other", status: "REGISTERED" }, { session_id: "target", status: "CANCELLED" }];
  assert.equal(hasActiveRegistrationForSession(rows, "target"), false);
  assert.equal(hasActiveRegistrationForSession([...rows, { session_id: "target", status: "REGISTERED" }], "target"), true);
  assert.equal(hasActiveRegistrationForSession([], "target"), false);
});

test("network, timeout and server failure remain uncertain; explicit refusals do not", () => {
  assert.equal(bookingResultIsUncertain(new TypeError("network")), true);
  assert.equal(bookingResultIsUncertain(api(408)), true);
  assert.equal(bookingResultIsUncertain(api(503)), true);
  assert.equal(bookingResultIsUncertain(api(409)), false);
  assert.equal(bookingResultIsUncertain(api(403)), false);
});

test("scheduling cache scope separates account and lifecycle while normalizing capability order", async () => {
  const { studentSchedulingScope } = await import("../src/features/appointments/booking-recovery.ts");
  const student = { id: "one", student_lifecycle_status: "CURRENT", capabilities: ["a", "b"] };
  assert.equal(studentSchedulingScope(student), studentSchedulingScope({ ...student, capabilities: ["b", "a"] }));
  assert.notEqual(studentSchedulingScope(student), studentSchedulingScope({ ...student, id: "two" }));
  assert.notEqual(studentSchedulingScope(student), studentSchedulingScope({ ...student, student_lifecycle_status: "GRADUATED" }));
  assert.notEqual(studentSchedulingScope(student), studentSchedulingScope({ ...student, capabilities: ["a"] }));
});

test("fixed-slot invalidation matches only bookable-slot queries across Services", async () => {
  const { isStudentFixedSlotsQuery } = await import("../src/features/appointments/student-scheduling-invalidation.ts");
  const { getServicesListBookableSlotsQueryKey, getServicesGetQueryKey } = await import("../src/lib/api/generated/services/services.ts");
  assert.equal(isStudentFixedSlotsQuery({ queryKey: getServicesListBookableSlotsQueryKey("service-a") }), true);
  assert.equal(isStudentFixedSlotsQuery({ queryKey: getServicesListBookableSlotsQueryKey("service-b") }), true);
  assert.equal(isStudentFixedSlotsQuery({ queryKey: getServicesGetQueryKey("service-a") }), false);
});
