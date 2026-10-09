// Shared harness for the browser regressions. Runs against a local Next server; every API read and
// write is answered with synthetic fixtures, and E-Counseling calls use the fake Call Object, so no
// account, Daily room, credential, recording, notification or institutional record is touched.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium, webkit } from "playwright";

import { fakeDailyInitScript } from "./fake-daily.mjs";
import { appointmentId, serviceId, appointment, service, workspace, consents, user, slip } from "./ui-hierarchy-fixtures.mjs";

export const viewports = {
  desktop: { viewport: { width: 1440, height: 1000 } },
  laptop: { viewport: { width: 1280, height: 800 } },
  tablet: { viewport: { width: 1024, height: 1000 } },
  phone: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
  narrowPhone: { viewport: { width: 320, height: 640 }, isMobile: true, hasTouch: true },
};

export async function createBrowserHarness(suite) {
  const baseURL = process.env.COMPASS_UI_BASE_URL ?? "http://localhost:3107";
  assert.ok(["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL).hostname), "Use a local Next server");
  const artifacts = process.env.COMPASS_UI_ARTIFACTS ? join(process.env.COMPASS_UI_ARTIFACTS, suite) : join(tmpdir(), `compass-${suite}`);
  await mkdir(artifacts, { recursive: true });
  const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
  assert.ok(["chromium", "webkit"].includes(engine), "Use a supported browser engine");
  const browser = await (engine === "webkit" ? webkit : chromium).launch({
    headless: true,
    ...(engine === "chromium" ? { args: ["--autoplay-policy=no-user-gesture-required"] } : {}),
    ...(engine === "chromium" && process.env.COMPASS_UI_BROWSER_CHANNEL ? { channel: process.env.COMPASS_UI_BROWSER_CHANNEL } : {}),
  });
  const emptyPage = { items: [], page: 1, page_size: 20, has_next: false };
  const failures = [];
  const results = [];

  async function openPage(path, {
    role = "COUNSELOR",
    mobile = false,
    tablet = false,
    device,
    viewport,
    studentContext = false,
    mediaStatus = "NOT_STARTED",
    decision = "APPROVED",
    disabledVideo = false,
    overrides = {},
    fakeDaily = null,
    initScripts = [],
  } = {}) {
    const contextOptions = device ? viewports[device] : mobile ? viewports.phone : tablet ? viewports.tablet : viewports.desktop;
    const context = // Service-worker fetches bypass Playwright routing. These synthetic suites must never
    // let the PWA worker send an unmocked API request (especially in WebKit).
    await browser.newContext({ serviceWorkers: "block", ...contextOptions, ...(viewport ? { viewport } : {}) });
    const page = await context.newPage();
    page.setDefaultTimeout(12_000);
    const errors = [];
    const requests = [];
    page.on("pageerror", (error) => errors.push(error.message));
    if (fakeDaily) await page.addInitScript({ content: fakeDailyInitScript(fakeDaily === true ? {} : fakeDaily) });
    for (const script of initScripts) await page.addInitScript({ content: script });
    await context.route(/\/api\/v1(?:\/|\?)/, async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const pathname = url.pathname;
      const method = request.method();
      requests.push({ pathname, method, search: url.search, body: request.postData() });
      const reply = (body, status = 200) => route.fulfill({ status, contentType: "application/json", headers: { date: new Date().toUTCString() }, body: JSON.stringify(body) });
      const override = overrides[`${method} ${pathname}`] ?? overrides[pathname];
      if (override) {
        if (typeof override === "function") return override({ route, reply, request, url });
        return reply(override);
      }
      if (pathname === "/api/v1/auth/session") return reply({ user: user(role), session: { id: "test-session", expires_at: "2099-10-07T00:00:00Z", is_current: true } });
      if (pathname === "/api/v1/auth/csrf") return reply({ csrf_token: "synthetic-csrf-token" });
      if (pathname === "/api/v1/me/profile") return reply({ full_name: "Example User", photo: null });
      if (pathname === "/api/v1/platform/status") return reply({ status: "operational", starts_at: null, ends_at: null, message: null });
      if (pathname === "/api/v1/notifications/unread-count") return reply({ unread_count: 0 });
      if (pathname === "/api/v1/notifications/push/config") return reply({ enabled: false, vapid_public_key: null });
      if (pathname === "/api/v1/privacy/my-notices") return reply(emptyPage);
      if (/\/e-counseling\/(?:me\/)?appointments\/[^/]+\/consents$/.test(pathname)) return reply({ items: consents(decision) });
      if (/\/e-counseling\/(?:me\/)?appointments\/[^/]+$/.test(pathname)) {
        const data = workspace(mediaStatus);
        data.counseling_context_available = studentContext;
        if (disabledVideo) data.provider_readiness = { ...data.provider_readiness, daily_enabled: false, join_allowed: false, join_state: "PROVIDER_DISABLED" };
        return reply(data);
      }
      if (pathname === `/api/v1/appointments/${appointmentId}`) return reply(appointment);
      if (pathname === `/api/v1/appointments/${appointmentId}/history`) return reply({ items: [] });
      if (pathname === `/api/v1/appointments/${appointmentId}/reassignment-candidates`) return reply({ items: [{ id: "other-counselor", display_name: "Ana Cruz" }] });
      if (pathname === `/api/v1/appointments/${appointmentId}/reschedule-slots`) return reply({ items: [{ starts_at: `${url.searchParams.get("date")}T04:00:00Z`, ends_at: `${url.searchParams.get("date")}T05:00:00Z` }], timezone: "Asia/Manila" });
      if (pathname === "/api/v1/appointments") return reply({ ...emptyPage, items: [appointment], ordering: url.searchParams.get("ordering") ?? "EARLIEST_START" });
      if (pathname === "/api/v1/appointments/booking/services") return reply({ items: [service] });
      if (pathname === "/api/v1/appointments/booking/counselors") return reply({ items: [appointment.provider] });
      if (pathname === `/api/v1/services/${serviceId}`) return reply(service);
      if (pathname === `/api/v1/services/${serviceId}/providers`) return reply({ provider_coverage: "ALL_COUNSELORS", counselors: [{ ...appointment.provider, is_active: true }] });
      if (pathname === "/api/v1/services" || pathname === "/api/v1/services/provider-candidates") return reply({ ...emptyPage, items: pathname.endsWith("provider-candidates") ? [appointment.provider] : [service] });
      if (pathname === `/api/v1/counseling/context/APPOINTMENT/${appointmentId}`) return reply({
        source_type: "APPOINTMENT", source_id: appointmentId, entry_mode: "APPOINTMENT", delivery_mode: "ONLINE",
        valid_from: "2026-01-01T00:00:00Z", valid_until: "2099-01-01T00:00:00Z",
        student: { ...appointment.student, campus: null, college: null, program: null, year_level: 4 },
        matching_encounter: null, routine_interview: null, available_sections: ["OVERVIEW"],
      });
      if (pathname === "/api/v1/institutional-forms") return reply({ items: [{ id: "family", key: "CALL_SLIP", title: "Call Slip", revision_required: true, configuration_state: "MISSING_REQUIRED_REVISION" }] });
      if (/\/institutional-forms\/[^/]+\/revisions$/.test(pathname)) return reply({ items: [{ id: "revision", family_key: "CALL_SLIP", internal_schema_version: 1, official_code: "TEST-CS", official_revision: "1", status: "ACTIVE", supported: false }] });
      if (pathname.startsWith("/api/v1/organization/")) return reply(emptyPage);
      if (pathname === `/api/v1/call-slips/${slip.id}` || pathname === `/api/v1/call-slips/me/${slip.id}`) return reply({ ...slip, updated_at: slip.created_at });
      if (pathname === "/api/v1/platform/health") return reply({ status: "ok", summary: "Dependencies checked", timestamp: new Date().toISOString(), checks: [{ code: "database", label: "Database", status: "ok", summary: "Database is reachable" }] });
      if (method !== "GET") return reply({ error: { code: "synthetic_failure", message: "Synthetic mutation rejected" } }, 500);
      return reply({ error: { code: "synthetic_unavailable", message: "No fixture for this optional read" } }, 404);
    });
    await page.goto(`${baseURL}${path}`, { waitUntil: "domcontentloaded" });
    return { page, context, errors, requests };
  }

  async function check(name, path, options, run) {
    if (process.env.COMPASS_UI_CHECK && !new RegExp(process.env.COMPASS_UI_CHECK).test(name)) return;
    let fixture;
    try {
      fixture = await openPage(path, options);
      await run(fixture.page, fixture);
      assert.deepEqual(fixture.errors, [], "No browser runtime errors");
      results.push({ name, passed: true });
      console.log(`PASS ${name}`);
    } catch (error) {
      failures.push(name);
      results.push({ name, passed: false, message: error.message, errors: fixture?.errors, requests: fixture?.requests });
      console.error(`FAIL ${name}: ${error.message}`);
      await fixture?.page.screenshot({ path: join(artifacts, `${name}-failure.png`), fullPage: true }).catch(() => {});
    } finally {
      await fixture?.context.close();
    }
  }

  async function finish() {
    await browser.close();
    await writeFile(join(artifacts, "results.json"), `${JSON.stringify({ baseURL, engine, results }, null, 2)}\n`);
    console.log(`${results.length - failures.length}/${results.length} browser checks passed; artifacts: ${artifacts}`);
    if (failures.length) process.exitCode = 1;
  }

  return {
    baseURL,
    artifacts,
    check,
    finish,
    async shown(locator) { await locator.waitFor({ state: "visible" }); },
    async hidden(locator) { await locator.waitFor({ state: "hidden" }); },
    async screenshot(page, name) { await page.screenshot({ path: join(artifacts, `${name}.png`), fullPage: true }); },
    async noHorizontalOverflow(page) {
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), true, "Page fits its viewport");
    },
  };
}
