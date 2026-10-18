// Browser screenshots and narrow-width checks for OPS-1A. The route components render with
// synthetic React Query data; only the compiled stylesheet is read from a local Next server.
import "./support/register-tsx.mjs";

import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { chromium, webkit } from "playwright";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { user as baseUser, service } from "./support/ui-hierarchy-fixtures.mjs";

const baseline = process.env.COMPASS_UI_EXPECT_BASELINE === "1";
const stage = baseline ? "before" : "after";
const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
const artifacts = join(process.env.COMPASS_UI_ARTIFACTS ?? join(tmpdir(), "compass-availability-governance"), stage);
const baseURL = process.env.COMPASS_UI_BASE_URL ?? "http://localhost:3107";
assert.ok(["chromium", "webkit"].includes(engine), "Use chromium or webkit");
assert.ok(["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL).hostname), "Use a local Next server");
await mkdir(artifacts, { recursive: true });

const [availability, services, pages, session, safety, pageWidth] = await Promise.all([
  import("../src/lib/api/generated/availability/availability.ts"),
  import("../src/lib/api/generated/services/services.ts"),
  import("../src/features/availability/availability-pages.tsx"),
  import("../src/features/portal/components/portal-session.tsx"),
  import("../src/features/form-safety/unsaved-changes-provider.tsx"),
  import("../src/components/ui/page-width.ts"),
]);
const { AvailabilityGate, AvailabilityNavigation } = await import("../src/features/availability/availability-shared.tsx");

const providerId = "counselor-ops-1a";
const provider = {
  id: providerId,
  full_name: "Maria Reyes",
  email: "maria.reyes@example.test",
  role: "COUNSELOR",
  is_active: true,
};
const windows = [
  { id: "mon-am", weekday: "MONDAY", start_time: "09:00:00", end_time: "12:00:00", mode_scope: "ALL" },
  { id: "wed-pm", weekday: "WEDNESDAY", start_time: "13:00:00", end_time: "16:00:00", mode_scope: "ALL" },
  { id: "fri-online", weekday: "FRIDAY", start_time: "09:00:00", end_time: "12:00:00", mode_scope: "ONLINE" },
];
const exception = {
  id: "exception-ops-1a",
  starts_at: "2026-11-03T01:00:00Z",
  ends_at: "2026-11-03T03:00:00Z",
  mode_scope: "ALL",
  reason: "Synthetic planning block",
  created_at: "2026-10-17T02:00:00Z",
  created_by: "fixture",
};
const response = (data) => ({ data, status: 200, headers: {} });

function renderWorkspace(pathname, role, page) {
  const admin = role === "IT_ADMIN";
  const user = {
    ...baseUser(role),
    id: admin ? "ops-admin" : providerId,
    capabilities: admin
      ? ["availability.view", "availability.manage"]
      : ["availability.view", "availability.manage_self"],
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  const value = {
    user,
    session: { id: "ops-1a-visual-fixture", expires_at: "2099-10-07T00:00:00Z", is_current: true },
  };
  const add = (key, data) => client.setQueryData(key, response(data));

  add(availability.getAvailabilityGetMyWeeklyQueryKey(), { provider_id: providerId, windows });
  add(availability.getAvailabilityListMyExceptionsQueryKey(), { provider_id: providerId, items: [exception] });
  add(availability.getAvailabilityGetOfficeWeeklyQueryKey(), { windows });
  add(availability.getAvailabilityListOfficeExceptionsQueryKey(), { items: [exception] });
  add(availability.getAvailabilityListProvidersQueryKey({ page: 1, page_size: 20 }), {
    items: [provider], page: 1, page_size: 20, has_next: false,
  });
  add(availability.getAvailabilityGetProviderQueryKey(providerId), provider);
  add(availability.getAvailabilityGetProviderWeeklyQueryKey(providerId), { provider_id: providerId, windows });
  add(availability.getAvailabilityListProviderExceptionsQueryKey(providerId), { provider_id: providerId, items: [exception] });
  add(services.getServicesListQueryKey({ page: 1, page_size: 50 }), {
    items: [service], page: 1, page_size: 50, has_next: false,
  });

  const route = h(
    "main",
    { id: "main-content", tabIndex: -1, className: "mx-auto max-w-[96rem] px-4 py-5 sm:px-6 lg:px-8 lg:py-6" },
    h(
      "div",
      { className: pageWidth.pageSheetWidth },
      h(AvailabilityGate, null, h(AvailabilityNavigation), page),
    ),
  );
  const tree = h(
    QueryClientProvider,
    { client },
    h(
      session.PortalSessionProvider,
      { value },
      h(safety.UnsavedChangesProvider, null, route),
    ),
  );
  return renderToStaticMarkup(withNextRouter(tree, { pathname }));
}

async function stylesheetURL() {
  const response = await fetch(new URL("/portal/availability/me", baseURL), { signal: AbortSignal.timeout(30_000) });
  assert.ok(response.ok, `Local Next server returned ${response.status}`);
  const html = await response.text();
  const href = /href="([^"]+\.css[^"]*)"/.exec(html)?.[1];
  assert.ok(href, "A compiled local stylesheet is available");
  const stylesheet = await fetch(new URL(href, baseURL), { signal: AbortSignal.timeout(30_000) });
  assert.ok(stylesheet.ok, `Local stylesheet returned ${stylesheet.status}`);
  return stylesheet.text();
}

const css = await stylesheetURL();
const browser = await (engine === "webkit" ? webkit : chromium).launch({ headless: true });
const checks = [];

async function capture({ name, pathname, role, page, width = 1440, height = 1000, expected }) {
  const context = await browser.newContext({ viewport: { width, height } });
  const browserPage = await context.newPage();
  const runtimeErrors = [];
  browserPage.on("pageerror", (error) => runtimeErrors.push(error.message));
  const markup = renderWorkspace(pathname, role, page);
  await browserPage.setContent(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"><base href="${baseURL}/"><style>${css}</style><title>COMPASS Availability</title></head><body>${markup}</body></html>`,
    { waitUntil: "networkidle" },
  );
  await browserPage.evaluate(() => document.fonts.ready);
  const text = await browserPage.locator("body").innerText();
  for (const phrase of expected) assert.ok(text.includes(phrase), `${name} includes “${phrase}”`);
  const dimensions = await browserPage.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  assert.ok(dimensions.scroll <= dimensions.client + 1, `${name} has no horizontal overflow at ${width}px`);
  if (!baseline && width <= 360 && page.type === pages.MyAvailabilityPage) {
    const saveButton = await browserPage.getByRole("button", { name: "Save weekly schedule" }).boundingBox();
    const saveNote = await browserPage.getByText(/Saving replaces all weekly hours shown above/).boundingBox();
    assert.ok(saveButton && saveNote, `${name} shows the save action and its safeguard note`);
    assert.ok(
      saveNote.width >= saveButton.width - 1,
      `${name} gives the safeguard note the full available width (${JSON.stringify({ saveButton, saveNote })})`,
    );
    assert.ok(saveNote.y >= saveButton.y + saveButton.height, `${name} places the safeguard note below the button`);
  }
  assert.deepEqual(runtimeErrors, [], `${name} has no browser runtime errors`);
  await browserPage.screenshot({ path: join(artifacts, `${name}.png`), fullPage: true });
  checks.push({ name, width, passed: true });
  await context.close();
}

const expectations = baseline
  ? {
      my: ["My availability", "Weekly schedule"],
      office: ["Office availability", "Office"],
      directory: ["Counselor availability", "Counselors"],
      detail: ["Maria Reyes", "Weekly schedule"],
    }
  : {
      my: ["My availability", "Your weekly hours", "Set your weekly hours and unavailable dates."],
      office: ["Office hours", "Office weekly hours", "Set Office hours and closure dates."],
      directory: ["Counselor schedules", "Find a counselor to manage their availability."],
      detail: ["Counselor schedule for", "Maria Reyes", "Counselor weekly hours"],
    };

await capture({
  name: `${stage}-my-availability-desktop`, pathname: "/portal/availability/me", role: "COUNSELOR",
  page: h(pages.MyAvailabilityPage), expected: expectations.my,
});
await capture({
  name: `${stage}-office-hours-desktop`, pathname: "/portal/availability/office", role: "IT_ADMIN",
  page: h(pages.OfficeAvailabilityPage), expected: expectations.office,
});
await capture({
  name: `${stage}-counselor-schedules-desktop`, pathname: "/portal/availability/providers", role: "IT_ADMIN",
  page: h(pages.ProviderAvailabilityPage), expected: expectations.directory,
});
await capture({
  name: `${stage}-counselor-detail-desktop`, pathname: `/portal/availability/providers/${providerId}`, role: "IT_ADMIN",
  page: h(pages.ProviderAvailabilityDetailPage, { providerId }), expected: expectations.detail,
});
if (!baseline) {
  await capture({
    name: "after-my-availability-narrow-phone", pathname: "/portal/availability/me", role: "COUNSELOR",
    page: h(pages.MyAvailabilityPage), width: 320, height: 640, expected: expectations.my,
  });
}

await browser.close();
await writeFile(join(artifacts, "results.json"), `${JSON.stringify({ stage, engine, baseURL, checks }, null, 2)}\n`);
console.log(`${checks.length}/${checks.length} ${stage} browser captures passed; artifacts: ${artifacts}`);
