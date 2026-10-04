// TanStack Query never schedules polling when `window` is undefined (it treats that as a server),
// so this file defines it before loading the library. node:test runs each file in its own process.
import assert from "node:assert/strict";
import { mock, test } from "node:test";

import {
  APPOINTMENT_SLOT_REFRESH_MS,
  appointmentSlotFreshness,
} from "../src/features/appointments/appointment-slot-freshness.ts";

globalThis.window ??= globalThis;
const { QueryClient, QueryObserver } = await import("@tanstack/react-query");

const tick = () => new Promise((resolve) => setImmediate(resolve));

test("an open slot picker rechecks times every 15 seconds while the page is visible", async () => {
  assert.equal(APPOINTMENT_SLOT_REFRESH_MS, 15_000);
  assert.equal(appointmentSlotFreshness.refetchIntervalInBackground, false);
  mock.timers.enable({ apis: ["setInterval", "setTimeout"] });
  try {
    const queryClient = new QueryClient();
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
    mock.timers.tick(0);
    await tick();
    assert.equal(requests, 1);

    mock.timers.tick(APPOINTMENT_SLOT_REFRESH_MS - 1);
    await tick();
    assert.equal(requests, 1, "not before the interval");
    mock.timers.tick(1);
    await tick();
    assert.equal(requests, 2);
    mock.timers.tick(APPOINTMENT_SLOT_REFRESH_MS);
    await tick();
    assert.equal(requests, 3);

    // Closing the picker stops the rechecks.
    unsubscribe();
    mock.timers.tick(APPOINTMENT_SLOT_REFRESH_MS * 2);
    await tick();
    assert.equal(requests, 3);
    queryClient.clear();
  } finally {
    mock.timers.reset();
  }
});
