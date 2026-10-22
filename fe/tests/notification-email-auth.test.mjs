import assert from "node:assert/strict";
import test from "node:test";

import { loginPathForPortal, safePortalDestination } from "../src/features/auth/utils/redirect.ts";
import { assertBrowserSuiteInCI } from "./support/browser-registration.mjs";

const appointment = "/portal/appointments/12345678-1234-4234-8234-123456789abc";

for (const value of [null, undefined, "", "https://evil.test", "//evil.test", "/\\evil.test",
  "javascript:alert(1)", "data:text/html,hello", "file:///etc/passwd", "https://user@evil.test",
  "%2f%2fevil.test", "%252f%252fevil.test", "/%2f%2fevil.test", "/login",
  "/login?next=/login", "/portal/../../login", "/portal/%2e%2e/login", "/portalish/appointments",
  "/portal/../%2f%2fevil.test", "/\t/evil.test",
]) {
  test(`unsafe login destination ${JSON.stringify(value)} falls back to the portal`, () => {
    assert.equal(safePortalDestination(value), "/portal");
  });
}

for (const value of [appointment, "/portal", "/portal/inventory/current",
  "/portal/feedback?opportunity=12345678-1234-4234-8234-123456789abc",
]) {
  test(`approved destination ${value} survives the login round trip`, () => {
    const login = new URL(loginPathForPortal(value), "https://portal.example");
    assert.equal(login.pathname, "/login");
    assert.equal(safePortalDestination(login.searchParams.get("next")), value);
    assert.equal([...login.searchParams.keys()].join(), "next");
  });
}

test("encoded opaque segments are never decoded into a second redirect URL", () => {
  for (const value of ["/portal/%252e%252e/%252f%252fevil.test", "/portal/%2f%2fevil.test"]) {
    const destination = new URL(safePortalDestination(value), "https://portal.example");
    assert.equal(destination.origin, "https://portal.example");
    assert.ok(destination.pathname.startsWith("/portal/"));
  }
});

test("login/MFA browser proof is registered for both CI engines", () => {
  assertBrowserSuiteInCI("notification-email-auth.browser.mjs");
});
