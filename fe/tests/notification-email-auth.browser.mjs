// Synthetic API fixtures only. Backend tests separately verify real session and record access.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointment, user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, navigate, settleFetches, finish } = await createBrowserHarness("notification-email-auth");
const id = "12345678-1234-4234-8234-123456789abc";
const destination = `/portal/appointments/${id}`;
const record = { ...appointment, id };
const failure = { error: { code: "not_authenticated", message: "Sign in required." } };

function world({ authenticated = false, mfa = false, denied = false, mandatorySetup = false } = {}) {
  const state = { authenticated, recordReads: 0, loginCalls: 0, mfaCalls: 0, setupComplete: false };
  const handler = async ({ pathname, method, reply }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(state.authenticated ? {
        authenticated: true, user: user("STUDENT"),
        session: { id: "synthetic-session", expires_at: "2099-10-07T00:00:00Z", is_current: true },
      } : failure, state.authenticated ? 200 : 401);
      return true;
    }
    if (pathname === "/api/v1/auth/login" && method === "POST") {
      state.loginCalls++;
      if (mandatorySetup && !state.setupComplete) {
        await reply({ error: { code: "mfa_setup_required", message: "Authenticator setup required." } }, 403);
        return true;
      }
      if (!mfa) state.authenticated = true;
      await reply({ authenticated: !mfa, mfa_required: mfa, mfa_methods: mfa ? ["totp"] : [],
        challenge_expires_at: mfa ? "2099-10-07T00:00:00Z" : null });
      return true;
    }
    if (pathname === "/api/v1/auth/mfa/totp/bootstrap/setup" && method === "POST") {
      await reply({ provisioning_uri: "otpauth://totp/Synthetic?secret=JBSWY3DPEHPK3PXP&issuer=Synthetic" });
      return true;
    }
    if (pathname === "/api/v1/auth/mfa/totp/bootstrap/confirm" && method === "POST") {
      state.setupComplete = true;
      await reply({ recovery_codes: ["SYNTHETIC-ONE", "SYNTHETIC-TWO"] });
      return true;
    }
    if (pathname === "/api/v1/auth/mfa/verify" && method === "POST") {
      state.mfaCalls++;
      if (state.rejectMfa) {
        await reply({ error: { code: "mfa_failed", message: "Expired challenge." } }, 400);
        return true;
      }
      state.authenticated = true;
      await reply({ authenticated: true, mfa_required: false, mfa_methods: [] });
      return true;
    }
    if (pathname === `/api/v1/appointments/${id}`) {
      state.recordReads++;
      await reply(denied ? { error: { code: "appointment_not_found", message: "Unavailable." } } : record, denied ? 404 : 200);
      return true;
    }
    if (pathname.startsWith(`/api/v1/appointments/${id}/`)) {
      await reply({ items: [] });
      return true;
    }
    return false;
  };
  return { state, handler };
}

async function signIn(page) {
  await page.getByLabel("Email", { exact: true }).fill("synthetic@example.test");
  await page.getByLabel("Password", { exact: true }).fill("synthetic-test-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

for (const mode of ["signed in", "password", "MFA", "denied after login"]) {
  const fixture = world({ authenticated: mode === "signed in", mfa: mode === "MFA", denied: mode === "denied after login" });
  await check(`email destination: ${mode}`, destination, { role: "STUDENT", handler: fixture.handler }, async page => {
    if (mode !== "signed in") {
      await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
      assert.equal(new URL(page.url()).searchParams.get("next"), destination);
      assert.equal(fixture.state.recordReads, 0);
      await hidden(page.getByText(record.reference_code, { exact: true }));
      await signIn(page);
      if (mode === "MFA") {
        await shown(page.getByRole("heading", { name: "Verify your identity", exact: true }));
        assert.equal(fixture.state.recordReads, 0);
        await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
        await page.getByRole("button", { name: "Verify", exact: true }).click();
      }
    }
    if (mode === "denied after login") {
      await shown(page.getByRole("heading", { name: "Appointment not available", exact: true }));
      await hidden(page.getByText(record.reference_code, { exact: true }));
      await hidden(page.getByText(record.student.display_name, { exact: true }));
    } else {
      await shown(page.getByText(record.reference_code, { exact: true }));
    }
    assert.equal(new URL(page.url()).pathname, destination);
    assert.equal(fixture.state.mfaCalls, mode === "MFA" ? 1 : 0);
  });
}

{
  const fixture = world({ authenticated: true });
  await check("expired session restores the original email destination after sign in", destination,
    { role: "STUDENT", handler: fixture.handler }, async page => {
      await shown(page.getByText(record.reference_code, { exact: true }));
      fixture.state.authenticated = false;
      await settleFetches(page);
      await page.reload();
      await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
      assert.equal(new URL(page.url()).searchParams.get("next"), destination);
      await hidden(page.getByText(record.reference_code, { exact: true }));
      await signIn(page);
      await shown(page.getByText(record.reference_code, { exact: true }));
      assert.equal(new URL(page.url()).pathname, destination);
    });
}

{
  const fixture = world({ mfa: true, mandatorySetup: true });
  await check("mandatory authenticator setup preserves destination through fresh login and MFA", destination,
    { role: "STUDENT", handler: fixture.handler }, async page => {
      await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
      await signIn(page);
      await shown(page.getByRole("heading", { name: "Set up an authenticator app", exact: true }));
      await page.getByRole("button", { name: "Start authenticator setup", exact: true }).click();
      await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
      await page.getByRole("button", { name: "Confirm authenticator", exact: true }).click();
      await shown(page.getByRole("heading", { name: "Save your recovery codes", exact: true }));
      assert.equal(fixture.state.recordReads, 0);
      await page.getByLabel("I have saved my recovery codes.", { exact: true }).check();
      await page.getByRole("button", { name: "Return to sign in", exact: true }).click();
      await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
      assert.equal(new URL(page.url()).searchParams.get("next"), destination);
      await signIn(page);
      await shown(page.getByRole("heading", { name: "Verify your identity", exact: true }));
      await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
      await page.getByRole("button", { name: "Verify", exact: true }).click();
      await shown(page.getByText(record.reference_code, { exact: true }));
      assert.equal(new URL(page.url()).pathname, destination);
      assert.equal(fixture.state.loginCalls, 2);
      assert.equal(fixture.state.mfaCalls, 1);
    });
}

for (const next of ["https://evil.test", "//evil.test", "%2f%2fevil.test", "/login?next=/login"]) {
  const fixture = world();
  await check("unsafe login next remains local: " + next, `/login?next=${encodeURIComponent(next)}`,
    { role: "STUDENT", handler: fixture.handler }, async page => {
      await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
      await signIn(page);
      await page.waitForURL(url => url.pathname === "/portal");
      assert.equal(new URL(page.url()).hostname, "localhost");
      assert.equal(fixture.state.recordReads, 0);
    });
}

for (const mandatorySetup of [false, true]) {
  const fixture = world({ mfa: true, mandatorySetup });
  await check(`reload ${mandatorySetup ? "mandatory setup" : "MFA"} restarts with the email destination`, destination,
    { role: "STUDENT", handler: fixture.handler }, async page => {
      await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
      await signIn(page);
      await shown(page.getByRole("heading", { name: mandatorySetup ? "Set up an authenticator app" : "Verify your identity", exact: true }));
      if (mandatorySetup) {
        await page.getByRole("button", { name: "Start authenticator setup", exact: true }).click();
        await shown(page.getByLabel("Authenticator code", { exact: true }));
      }
      await settleFetches(page);
      await page.reload();
      await shown(page.getByRole("heading", { name: "Restart sign in", exact: true }));
      assert.equal(fixture.state.recordReads, 0);
      await page.getByRole("link", { name: "Return to sign in", exact: true }).click();
      await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
      assert.equal(new URL(page.url()).searchParams.get("next"), destination);
      // A new password challenge is required; reload never restores credentials or MFA state.
      assert.equal(fixture.state.loginCalls, 1);
      assert.equal(fixture.state.mfaCalls, 0);
      await signIn(page);
      if (!mandatorySetup) {
        await shown(page.getByRole("heading", { name: "Verify your identity", exact: true }));
        await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
        await page.getByRole("button", { name: "Verify", exact: true }).click();
        await shown(page.getByText(record.reference_code, { exact: true }));
      } else {
        await shown(page.getByRole("heading", { name: "Set up an authenticator app", exact: true }));
        await page.getByRole("button", { name: "Start authenticator setup", exact: true }).click();
        await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
        await page.getByRole("button", { name: "Confirm authenticator", exact: true }).click();
        await page.getByLabel("I have saved my recovery codes.", { exact: true }).check();
        await page.getByRole("button", { name: "Return to sign in", exact: true }).click();
        await signIn(page);
        await shown(page.getByRole("heading", { name: "Verify your identity", exact: true }));
        await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
        await page.getByRole("button", { name: "Verify", exact: true }).click();
        await shown(page.getByText(record.reference_code, { exact: true }));
      }
    });
}

{
  const fixture = world({ mfa: true });
  fixture.state.rejectMfa = true;
  await check("expired MFA denies resource; original email link supports deliberate restart", destination,
    { role: "STUDENT", handler: fixture.handler }, async page => {
      await signIn(page);
      await shown(page.getByRole("heading", { name: "Verify your identity", exact: true }));
      await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
      await page.getByRole("button", { name: "Verify", exact: true }).click();
      await shown(page.getByRole("alert"));
      assert.equal(fixture.state.recordReads, 0);
      fixture.state.rejectMfa = false;
      await navigate(page, destination);
      await signIn(page);
      await shown(page.getByRole("heading", { name: "Verify your identity", exact: true }));
      await page.getByLabel("Authenticator code", { exact: true }).fill("123456");
      await page.getByRole("button", { name: "Verify", exact: true }).click();
      await shown(page.getByText(record.reference_code, { exact: true }));
    });
}

for (const path of ["verify", "setup-authenticator"]) {
  for (const next of ["https://evil.test", "//evil.test", "/portal/%2e%2e/login"]) {
    await check(`reloaded ${path} sanitizes return ${next}`, `/login/${path}?next=${encodeURIComponent(next)}`,
      { role: "STUDENT", handler: world().handler }, async page => {
        await shown(page.getByRole("heading", { name: "Restart sign in", exact: true }));
        const restart = page.getByRole("link", { name: "Return to sign in", exact: true });
        assert.equal(new URL(await restart.getAttribute("href"), page.url()).searchParams.get("next"), "/portal");
      });
  }
}

for (const mandatorySetup of [false, true]) {
  const fixture = world({ mfa: true, mandatorySetup });
  await check(`Back during ${mandatorySetup ? "required setup" : "MFA"} permits only deliberate fresh login`, "/",
    { role: "STUDENT", handler: fixture.handler }, async page => {
      await navigate(page, destination);
      await signIn(page);
      await shown(page.getByRole("heading", { name: mandatorySetup ? "Set up an authenticator app" : "Verify your identity", exact: true }));
      await settleFetches(page);
      await page.goBack();
      await page.waitForURL(url => url.pathname === "/");
      assert.equal(fixture.state.recordReads, 0);
      await navigate(page, destination);
      await signIn(page);
      await shown(page.getByRole("heading", { name: mandatorySetup ? "Set up an authenticator app" : "Verify your identity", exact: true }));
      assert.equal(fixture.state.loginCalls, 2);
      assert.equal(fixture.state.recordReads, 0);
    });
}

await finish();
