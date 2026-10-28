import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { loginPathForPortal, safePortalDestination } from "../src/features/auth/utils/redirect.ts";
import { assertBrowserSuiteInCI } from "./support/browser-registration.mjs";

// Backend test independently checks these rows against the authoritative closed Python builder.
const routes = JSON.parse(readFileSync(new URL("./support/notification-route-contract.json", import.meta.url)));
for (const row of routes) {
  test(`email/in-app route parity ${row.target_type} ${row.target_id ?? "fallback"}`, () => {
    const destination = notificationDestination({ ...row, is_current: true }, "account-a");
    assert.equal(destination?.href ?? null, row.route);
    if (row.route) {
      const login = new URL(loginPathForPortal(row.route), "https://portal.example");
      assert.equal(safePortalDestination(login.searchParams.get("next")), row.route);
    }
  });
}

test("Account Security remains recipient-scoped and operational email-excluded", () => {
  assert.equal(notificationDestination({ target_type: "ACCOUNT_SECURITY", target_id: "account-a" }, "account-a").href, "/portal/account/security");
  assert.equal(notificationDestination({ target_type: "ACCOUNT_SECURITY", target_id: "account-b" }, "account-a"), null);
  assert.equal(notificationDestination({ target_type: "UNSUPPORTED", target_id: "https://evil.test" }, "account-a"), null);
});

test("cross-channel browser journeys are discovered for both CI engines", () => {
  assertBrowserSuiteInCI("notification-cross-channel.browser.mjs");
});

test("superseded Group Session history navigates with current-event wording", () => {
  const target = notificationDestination({ target_type: "GROUP_SESSION", target_id: "12345678-1234-4234-8234-123456789abc", is_current: false }, "account-a");
  assert.equal(target.label, "Review current event");
  assert.equal(target.href, "/portal/group-sessions/12345678-1234-4234-8234-123456789abc");
});
