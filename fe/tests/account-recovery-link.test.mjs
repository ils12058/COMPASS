import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { RecoveryLinkView, unavailableLinkMessage } from "../src/features/auth/password/recovery-link-view.tsx";
import { passwordPolicyMessages } from "../src/features/auth/utils/errors.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";

function render(state, props = {}) {
  return renderToStaticMarkup(createElement(RecoveryLinkView, { state, ...props }));
}
const details = { valid: true, masked_email: "n***@example.edu", email_change: true };

test("valid assisted link shows the masked destination, both password inputs, and consequences", () => {
  const html = render({ kind: "valid", details });
  assert.match(html, /n\*\*\*@example.edu/);
  assert.match(html, /sign-in email will change/);
  assert.equal((html.match(/type="password"/g) ?? []).length, 2);
  assert.match(html, /for="recovery-password"/);
  assert.match(html, /for="recovery-confirm"/);
  assert.match(html, /signed out everywhere/);
  assert.match(html, /authenticator stays in place/);
  assert.match(html, /Update password/);
});

test("self-service link offers the same password form without promising an email change", () => {
  const html = render({ kind: "valid", details: { ...details, email_change: false } });
  assert.match(html, /Account email:/);
  assert.doesNotMatch(html, /email will change/);
});

test("unavailable state conceals whether a link was invalid, expired, or already used", () => {
  const html = render({ kind: "unavailable" });
  assert.ok(html.includes(unavailableLinkMessage));
  assert.match(html, /role="alert"/);
  assert.doesNotMatch(html, /type="password"|n\*\*\*|Update password/);
  assert.doesNotMatch(html, /expired|already used|token/);
});

test("backend password-policy issues are rendered at the new-password field and preserve entry", () => {
  const error = new CompassApiError({ status: 422, body: { error: { code: "password_policy_failed",
    details: [{ loc: ["new_password"], message: "This password is too short.", type: "password_too_short" }] } },
    headers: {}, method: "POST", url: "/api/v1/auth/account-recovery/confirm" });
  const html = render({ kind: "valid", details }, { newPassword: "short", confirmPassword: "short",
    error: "Review the password requirements below.", policyMessages: passwordPolicyMessages(error) });
  assert.match(html, /This password is too short\./);
  assert.match(html, /aria-describedby="recovery-policy"/);
  assert.match(html, /aria-invalid="true"/);
  assert.match(html, /value="short"/);
});

test("pending password update keeps the form stable and disables repeated submission", () => {
  const html = render({ kind: "valid", details }, { pending: true });
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Updating password/);
});

test("confirmed assisted recovery explains email/password update and retained authenticator", () => {
  const html = render({ kind: "success", emailChange: true });
  assert.match(html, /sign-in email was changed/);
  assert.match(html, /All existing sign-ins were ended/);
  assert.match(html, /still need it/);
  assert.match(html, /href="\/login"/);
  assert.doesNotMatch(html, /type="password"/);
});

test("confirmed self-service update does not claim the email changed", () => {
  const html = render({ kind: "success", emailChange: false });
  assert.match(html, /password was updated/);
  assert.doesNotMatch(html, /email was changed/);
});

test("checking state is busy and exposes no account data", () => {
  const html = render({ kind: "loading" });
  assert.match(html, /aria-busy="true"/);
  assert.match(html, /Checking your recovery link/);
  assert.doesNotMatch(html, /example.edu|type="password"/);
});

test("transient verification errors offer Retry without password inputs", () => {
  const html = render({ kind: "error", message: "Too many attempts. Try again later." });
  assert.match(html, /Too many attempts/);
  assert.match(html, /Retry/);
  assert.doesNotMatch(html, /type="password"/);
});
