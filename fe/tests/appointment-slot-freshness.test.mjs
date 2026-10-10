import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { focusManager, onlineManager, QueryClient, QueryObserver } from "@tanstack/react-query";

import {
  appointmentSlotFreshness,
  isSlotTakenError,
  reconcileSlotSelection,
  slotIsOffered,
  SLOT_JUST_TAKEN,
  SLOT_NO_LONGER_AVAILABLE,
} from "../src/features/appointments/appointment-slot-freshness.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { createQueryClient } from "../src/lib/query/query-client.ts";

const tick = () => new Promise((resolve) => setImmediate(resolve));

// A slot query observed the way an open picker observes it, counting requests to the server.
async function observeSlots(queryClient) {
  let requests = 0;
  const observer = new QueryObserver(queryClient, {
    queryKey: ["/api/v1/appointments/booking/slots", { date: "2026-10-12" }],
    queryFn: async () => {
      requests += 1;
      return { data: { items: [] } };
    },
    retry: false,
    ...appointmentSlotFreshness,
  });
  const unsubscribe = observer.subscribe(() => {});
  await tick();
  return { requests: () => requests, unsubscribe };
}

test("returning to the window rechecks the times at once", async () => {
  const queryClient = new QueryClient();
  queryClient.mount();
  const picker = await observeSlots(queryClient);
  const before = picker.requests();
  focusManager.setFocused(false);
  focusManager.setFocused(true);
  await tick();
  assert.equal(picker.requests(), before + 1);
  focusManager.setFocused(undefined);
  picker.unsubscribe();
  queryClient.unmount();
  queryClient.clear();
});

test("a returning connection rechecks the times", async () => {
  const queryClient = new QueryClient();
  queryClient.mount();
  const picker = await observeSlots(queryClient);
  const before = picker.requests();
  onlineManager.setOnline(false);
  onlineManager.setOnline(true);
  await tick();
  assert.equal(picker.requests(), before + 1);
  picker.unsubscribe();
  queryClient.unmount();
  queryClient.clear();
});

test("the portal's general cache policy is unchanged; only the slot queries poll", () => {
  const defaults = createQueryClient().getDefaultOptions().queries;
  assert.equal(defaults.refetchOnWindowFocus, false);
  assert.equal(defaults.refetchInterval, undefined);
  assert.equal(defaults.staleTime, 30_000);
  for (const file of ["appointment-booking-page.tsx", "appointment-detail-page.tsx"]) {
    const source = readFileSync(new URL(`../src/features/appointments/${file}`, import.meta.url), "utf8");
    assert.match(source, /\.\.\.appointmentSlotFreshness/, `${file} applies the slot freshness policy`);
  }
});

test("a chosen time that a recheck no longer offers is dropped", () => {
  const slots = [{ starts_at: "2026-10-12T01:00:00Z" }, { starts_at: "2026-10-12T03:00:00Z" }];
  assert.deepEqual(reconcileSlotSelection("2026-10-12T01:00:00Z", slots), { selected: "2026-10-12T01:00:00Z", lost: false });
  assert.deepEqual(reconcileSlotSelection("2026-10-12T02:00:00Z", slots), { selected: "", lost: true });
  // Nothing chosen, or no list yet: nothing to drop.
  assert.deepEqual(reconcileSlotSelection("", slots), { selected: "", lost: false });
  assert.deepEqual(reconcileSlotSelection("2026-10-12T02:00:00Z", undefined), { selected: "2026-10-12T02:00:00Z", lost: false });
  assert.equal(slotIsOffered(slots, "2026-10-12T03:00:00Z"), true);
  assert.equal(slotIsOffered(slots, ""), false);
});

test("a time taken between the last check and the request is recognised and explained plainly", () => {
  const refusal = (code) =>
    new CompassApiError({ status: 409, body: { error: { code, message: code } }, headers: {}, method: "POST", url: "/api/v1/appointments/me" });
  assert.equal(isSlotTakenError(refusal("appointment_time_unavailable")), true);
  assert.equal(isSlotTakenError(refusal("appointment_time_conflict")), true);
  assert.equal(isSlotTakenError(refusal("appointment_lifecycle_conflict")), false);
  for (const message of [SLOT_JUST_TAKEN, SLOT_NO_LONGER_AVAILABLE]) {
    assert.match(message, /Choose another available time\./);
    assert.doesNotMatch(message, /concurren|refresh|conflict/i);
  }
});

test("booking and rescheduling recheck the chosen time before submitting and recover from a taken time", () => {
  for (const file of ["appointment-booking-page.tsx", "appointment-detail-page.tsx"]) {
    const source = readFileSync(new URL(`../src/features/appointments/${file}`, import.meta.url), "utf8");
    // The recheck happens before the mutation is sent.
    const recheck = source.search(/await (slots|rescheduleSlots)\.refetch\(\)/);
    const mutation = source.search(/(create|reschedule)\.mutateAsync\(/);
    assert.ok(recheck > 0 && recheck < mutation, `${file} rechecks before submitting`);
    // Booking classifies its failure first (appointment-booking-outcome.ts maps a taken time to
    // the time step); rescheduling checks the error directly. Either way the times reload.
    const takenTime = file === "appointment-booking-page.tsx"
      ? /failure\.step === "time"[\s\S]{0,400}slots\.refetch\(\)/
      : /isSlotTakenError\(caught\)[\s\S]{0,400}\.refetch\(\)/;
    assert.match(source, takenTime, `${file} reloads times after a taken time`);
  }
});
