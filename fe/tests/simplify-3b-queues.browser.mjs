import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { messagesAccount, sessionFor } from "./support/guidance-messages-fixtures.mjs";

const h = await createBrowserHarness("simplify-3b-queues");
const phase = process.env.COMPASS_3B_PHASE ?? "after";
const time = "2026-10-10T00:00:00Z";
const id = "a0000000-0000-4000-8000-000000000005";
function fixture(role) {
  const student = role === "STUDENT";
  const account = messagesAccount(role);
  const reads = [];
  return {
    reads,
    handler: async ({ pathname, url, reply }) => {
      if (pathname === "/api/v1/auth/session") { await reply(sessionFor(account)); return true; }
      if (pathname !== (student ? "/api/v1/student-actions" : "/api/v1/work")) return false;
      const page = Number(url.searchParams.get("page") ?? 1);
      reads.push(page);
      const item = student
        ? { id: "inventory:1", kind: "INVENTORY_START", priority: "INCOMPLETE_SELF_SERVICE", source_id: id, conversation_kind: null, pending_count: null, due_at: null, waiting_since: null }
        : { id: "slip:1", kind: "CALL_SLIP_DUE", priority: "TIME_SENSITIVE", source_id: id, student: { id: "synthetic-student", display_name: "Synthetic Student " + "LongName".repeat(12) }, due_at: time, waiting_since: null };
      await reply({ items: page === 1 ? [item] : [], page, page_size: 20, has_next: page === 1, generated_at: time });
      return true;
    },
  };
}
for (const role of ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF"]) {
  for (const width of role === "GUIDANCE_SERVICES_STAFF" ? [390, 1440] : [320, 390, 768, 1024, 1440]) {
    const world = fixture(role);
    await h.check(`${phase}-${role}-${width}`, role === "STUDENT" ? "/portal/actions" : "/portal/work", { handler: world.handler, viewport: { width, height: 900 } }, async (page, { requests }) => {
      const nav = page.getByRole("navigation", { name: role === "STUDENT" ? "My actions pages" : "My work pages" });
      await h.shown(nav.getByText("Page 1", { exact: true }));
      assert.equal(await nav.getByRole("button", { name: "Previous", exact: true }).isDisabled(), true);
      await h.noHorizontalOverflow(page);
      await h.screenshot(page, `${phase}-${role}-${width}`);
      await nav.getByRole("button", { name: "Next", exact: true }).focus();
      await page.keyboard.press("Enter");
      await h.shown(nav.getByText("Page 2", { exact: true }));
      assert.ok(world.reads.includes(2));
      assert.equal(await nav.getByRole("button", { name: "Next", exact: true }).isDisabled(), true);
      await nav.getByRole("button", { name: "Previous", exact: true }).click();
      await h.shown(nav.getByText("Page 1", { exact: true }));
      await page.addStyleTag({ content: "html { font-size: 200%; }" });
      await h.noHorizontalOverflow(page);
      await h.screenshot(page, `${phase}-${role}-${width}-enlarged`);
      assert.equal(requests.filter(r => r.method !== "GET").length, 0);
    });
  }
}
await h.finish();
