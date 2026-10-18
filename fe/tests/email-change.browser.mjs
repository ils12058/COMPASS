import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, finish, noHorizontalOverflow, shown } = await createBrowserHarness("email-change");
const requestId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const challengeId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const pendingStatus = () => ({
  request: {
    status: "pending",
    request_id: requestId,
    challenge_id: challengeId,
    destination_email: "new-address@example.test",
    expires_at: "2099-01-01T00:00:00Z",
    confirmed_at: null,
  },
});

function fixtures({ mfa = false } = {}) {
  const state = {
    emailChange: pendingStatus(),
    mfa: { enabled: mfa, recent: false },
    confirmations: [],
    stepUps: [],
  };
  return {
    state,
    options: {
      device: "phone",
      overrides: {
        "/api/v1/auth/session": {
          user: { ...user("STUDENT"), email: "old-address@example.test" },
          session: { id: "synthetic-owner-session", expires_at: "2099-01-01T00:00:00Z", is_current: true },
        },
      },
      handler: async ({ pathname, method, request, reply }) => {
        if (pathname === "/api/v1/auth/email-change/status" && method === "GET") {
          await reply(state.emailChange);
          return true;
        }
        if (pathname === "/api/v1/auth/mfa/status" && method === "GET") {
          await reply(state.mfa);
          return true;
        }
        if (pathname === "/api/v1/auth/mfa/totp/verify" && method === "POST") {
          state.stepUps.push(JSON.parse(request.postData()));
          state.mfa = { enabled: true, recent: true };
          await reply({ verified: true, recent: true });
          return true;
        }
        if (pathname === "/api/v1/auth/email-change/confirm" && method === "POST") {
          state.confirmations.push(JSON.parse(request.postData()));
          if (JSON.parse(request.postData()).code !== "123456") {
            await reply({ error: { code: "invalid_email_change_request", message: "Verification unavailable." } }, 422);
            return true;
          }
          state.emailChange.request.status = "confirmed";
          state.emailChange.request.challenge_id = null;
          state.emailChange.request.confirmed_at = "2026-10-18T00:00:00Z";
          await reply({ changed: true, reauthentication_required: true });
          return true;
        }
        return false;
      },
    },
  };
}

{
  const f = fixtures();
  await check("owner rediscovers admin request after refresh and verifies new mailbox on phone", "/portal/account/security", f.options, async (page, browser) => {
    await shown(page.getByText("Verify your new sign-in email", { exact: true }));
    await shown(page.getByRole("link", { name: "Verify email", exact: true }));
    await page.reload({ waitUntil: "domcontentloaded" });
    await shown(page.getByRole("link", { name: "Verify email", exact: true }));
    await page.getByRole("link", { name: "Verify email", exact: true }).click();
    await page.getByRole("heading", { name: "Verify your new email", exact: true }).waitFor();
    await shown(page.getByText("new-address@example.test", { exact: true }));
    await shown(page.getByLabel("Code from new email", { exact: true }));
    assert.equal(await page.getByText("Verify your current email", { exact: true }).count(), 0);
    await noHorizontalOverflow(page);

    await page.getByLabel("Code from new email", { exact: true }).fill("000000");
    const verifyButton = page.getByRole("button", { name: "Verify email", exact: true });
    const rejected = page.waitForResponse((response) => response.url().endsWith("/api/v1/auth/email-change/confirm") && response.status() === 422);
    await verifyButton.click();
    await rejected;
    await shown(page.getByText("The verification details could not be confirmed. Check the code or start again.", { exact: true }));
    assert.equal(f.state.confirmations[0].request_id, requestId);
    assert.equal(f.state.confirmations[0].challenge_id, challengeId);
    assert.equal(f.state.confirmations[0].code, "000000");

    await page.getByLabel("Code from new email", { exact: true }).fill("123456");
    const accepted = page.waitForResponse((response) => response.url().endsWith("/api/v1/auth/email-change/confirm") && response.status() === 200);
    await page.getByRole("button", { name: "Verify email", exact: true }).click();
    await accepted;
    await page.waitForURL("**/login?email_changed=1");
    assert.equal(f.state.confirmations.length, 2);
    assert.equal(f.state.confirmations[1].code, "123456");
    assert.equal(browser.requests.some(({ pathname, method }) => pathname === "/api/v1/auth/email-change/request" && method === "POST"), false);
  });
}

{
  const f = fixtures({ mfa: true });
  await check("owner must complete TOTP step-up before admin-request confirmation", "/portal/account/security/email", f.options, async (page) => {
    await page.getByLabel("Code from new email", { exact: true }).fill("123456");
    await page.getByRole("button", { name: "Verify email", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await shown(dialog);
    assert.equal(f.state.confirmations.length, 0);
    await dialog.getByLabel("Authenticator code", { exact: true }).fill("987654");
    await dialog.getByRole("button", { name: "Verify", exact: true }).click();
    await dialog.waitFor({ state: "hidden" });
    assert.deepEqual(f.state.stepUps, [{ code: "987654" }]);
    const accepted = page.waitForResponse((response) => response.url().endsWith("/api/v1/auth/email-change/confirm") && response.status() === 200);
    await page.getByRole("button", { name: "Verify email", exact: true }).click();
    await accepted;
    await page.waitForURL("**/login?email_changed=1");
    assert.equal(f.state.confirmations.length, 1);
    assert.equal(f.state.confirmations[0].code, "123456");
  });
}

{
  const f = fixtures();
  f.state.emailChange.request.status = "expired";
  f.state.emailChange.request.challenge_id = null;
  await check("expired email request offers a safe self-service restart", "/portal/account/security/email", f.options, async (page) => {
    await shown(page.getByText("This email change is no longer active. Start a new request to try again."));
    await shown(page.getByRole("heading", { name: "Verify your current email", exact: true }));
    await page.getByRole("button", { name: "Send current-email code", exact: true }).waitFor();
  });
}

{
  const f = fixtures();
  f.state.emailChange = { request: null };
  await check("different account cannot discover another user's pending email change", "/portal/account/security/email", f.options, async (page, browser) => {
    await shown(page.getByRole("heading", { name: "Verify your current email", exact: true }));
    assert.equal(await page.getByLabel("Code from new email", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("button", { name: "Verify email", exact: true }).count(), 0);
    assert.equal(browser.requests.some(({ pathname, method }) => pathname === "/api/v1/auth/email-change/confirm" && method === "POST"), false);
  });
}

{
  const accountId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const state = {
    request: null,
    confirmationPosts: [],
    account: {
      id: accountId,
      institutional_id: "SYNTHETIC-ACCOUNT-1",
      first_name: "Synthetic",
      middle_name: "",
      last_name: "Account",
      suffix: "",
      full_name: "Synthetic Account",
      role: "STUDENT",
      student_lifecycle_status: "FORMER",
      designations: [],
      is_active: true,
      password_configured: true,
      email_verified: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-10-01T00:00:00Z",
      email_verified_at: "2026-01-01T00:00:00Z",
      mfa_enabled: false,
      email: "admin-managed-old@example.test",
    },
  };
  const adminUser = {
    ...user("IT_ADMIN"),
    id: "synthetic-admin",
    role: "IT_ADMIN",
    capabilities: ["accounts.manage"],
  };
  await check("IT Admin sees staged and completed status without changing email before verification", `/portal/accounts/${accountId}`, {
    overrides: {
      "/api/v1/auth/session": { user: adminUser, session: { id: "synthetic-admin-session", expires_at: "2099-01-01T00:00:00Z", is_current: true } },
      [`/api/v1/accounts/${accountId}`]: state.account,
    },
    handler: async ({ pathname, method, request, reply }) => {
      if (pathname === `/api/v1/accounts/${accountId}/email-change` && method === "GET") {
        await reply({ request: state.request });
        return true;
      }
      if (pathname === `/api/v1/accounts/${accountId}/email-change` && method === "POST") {
        const body = JSON.parse(request.postData());
        state.confirmationPosts.push(body);
        state.request = {
          status: "pending",
          request_id: requestId,
          destination_email: body.new_email,
          expires_at: "2099-01-01T00:00:00Z",
          confirmed_at: null,
        };
        await reply({ request_id: requestId, challenge_id: challengeId, expires_at: state.request.expires_at });
        return true;
      }
      return false;
    },
  }, async (page, browser) => {
    await page.getByRole("button", { name: "Change sign-in email", exact: true }).click();
    await page.getByLabel("New email", { exact: true }).fill("admin-managed-new@example.test");
    const staged = page.waitForResponse((response) => response.url().endsWith(`/api/v1/accounts/${accountId}/email-change`) && response.request().method() === "POST" && response.status() === 200);
    await page.getByRole("button", { name: "Send verification", exact: true }).click();
    await staged;
    await shown(page.getByText("Verification pending", { exact: true }));
    await shown(page.getByText("admin-managed-new@example.test", { exact: true }));
    await shown(page.getByText("admin-managed-old@example.test", { exact: true }).first());
    assert.equal(state.confirmationPosts.length, 1);
    assert.equal(state.confirmationPosts[0].new_email, "admin-managed-new@example.test");
    assert.equal("code" in state.confirmationPosts[0], false);
    assert.equal(browser.requests.some(({ pathname }) => pathname === "/api/v1/auth/email-change/confirm"), false);

    state.request = { ...state.request, status: "confirmed", confirmed_at: "2026-10-18T00:00:00Z" };
    state.account.email = "admin-managed-new@example.test";
    await page.reload({ waitUntil: "domcontentloaded" });
    await shown(page.getByText("Email verified", { exact: true }).first());
    await shown(page.getByText("admin-managed-new@example.test", { exact: true }).first());
  });
}

await finish();
