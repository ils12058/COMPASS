// Synthetic fixtures only: captures the same role and viewport combinations before and after.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import { counselorWorld } from "./support/ux15-counselor-home-fixtures.mjs";
import { gssWorld } from "./support/ux15-gss-home-fixtures.mjs";

const h = await createBrowserHarness("simplify-2a-home");
const phase = process.env.COMPASS_HOME_PHASE === "before" ? "before" : "after";
const cases = [
  ["student", () => homeWorld(), "overview-attention-heading"],
  ["counselor", () => counselorWorld(), "counselor-work-heading"],
  ["head", () => counselorWorld({ head: true, capabilities: [
    "appointments.view_self", "appointments.manage", "reports.view", "organization.manage",
    "availability.manage", "services.manage", "services.catalog.view", "guidance_messages.view",
    "routine_interviews.view_assigned", "counseling.view_assigned", "guidance_followups.view",
  ] }), "head-guidance-oversight-heading"],
  ["gss", () => gssWorld(), "gss-work-heading"],
  ["it", () => homeWorld({ role: "IT_ADMIN" }), "overview-summary-heading"],
];
const geometry = [];
for (const [role, makeState, heading] of cases) {
  for (const width of [320, 390, 1024, 1440]) {
    const state = makeState();
    await h.check(`${role}-${width}`, "/portal", state.options({ viewport: { width, height: 1000 } }), async (page, { requests }) => {
      await h.shown(page.locator(`#${heading}`));
      await h.shown(page.getByText("Guidance Office schedule for October", { exact: true }));
      if (role === "student") await h.shown(page.getByRole("link", { name: "Book appointment", exact: true }));
      if (role === "head") await h.shown(page.locator('section[aria-labelledby="head-guidance-oversight-heading"]').getByRole("link", { name: /Reports/ }));
      if (role === "gss") await h.shown(page.locator("#gss-operations-heading"));
      if (role === "it") await h.shown(page.getByText("2 failed", { exact: true }));
      await page.evaluate(() => document.fonts.ready);
      await h.noHorizontalOverflow(page);
      if (phase === "after") {
        const primary = role === "student" || role === "it" ? "overview-attention-heading" : role === "gss" ? "gss-work-heading" : "counselor-work-heading";
        assert.equal(await page.locator("main h2").first().getAttribute("id"), primary, "Primary work comes first in reading order");
        const links = page.locator(`section[aria-labelledby="${primary}"] a`);
        for (const link of await links.all()) {
          const box = await link.boundingBox();
          assert.ok(box && box.height >= 43, "Primary work links retain a touch-friendly target");
        }
        const summary = page.locator('section[aria-labelledby="overview-announcements-heading"]');
        assert.ok(await summary.getByRole("link", { name: "All announcements", exact: true }).isVisible(), "Announcements retain a discoverable destination");
      }
      assert.equal(requests.filter((r) => r.method !== "GET").length, 0);
      const measures = await page.evaluate(() => {
        const main = document.querySelector("main");
        const nodes = [...main.querySelectorAll("section[aria-labelledby]")];
        const regions = nodes.map((node) => {
          const rect = node.getBoundingClientRect();
          return { id: node.getAttribute("aria-labelledby"), top: rect.top, width: rect.width, height: rect.height, border: getComputedStyle(node).borderTopWidth };
        });
        return { document: document.documentElement.scrollWidth, regions };
      });
      geometry.push({ role, width, ...measures });
      await h.screenshot(page, `${phase}-${role}-${width}`);
    });
  }
}
await writeFile(join(h.artifacts, `${phase}-geometry.json`), JSON.stringify(geometry, null, 2));
await h.finish();
