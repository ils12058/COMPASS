// Actual Next UI; all accounts, records, mutations and PDF responses are synthetic.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user, slip } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("call-slip-permissions");
const path = `/portal/call-slips/${slip.id}`;
function world(role, capabilities, lifecycle = "ACTIVE", { uncertain = false, foreignOwner = false } = {}) {
  let item = { ...slip, state: lifecycle, updated_at: slip.created_at, void_reason: "Synthetic withdrawn record" };
  const base = role === "STUDENT" ? "/api/v1/call-slips/me" : "/api/v1/call-slips";
  const mutations = [];
  let reads = 0;
  const handler = async ({ pathname, method, request, reply, route }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(sessionFor({ ...user(role), capabilities })); return true;
    }
    if (pathname === `${base}/${slip.id}`) {
      reads++;
      await reply(foreignOwner ? { error: { code: "call_slip_not_found", message: "Call Slip not found." } } : item, foreignOwner ? 404 : 200); return true;
    }
    if (pathname === `${base}/${slip.id}/pdf`) {
      await route.fulfill({ status: 200, contentType: "application/pdf", headers: { "content-disposition": 'attachment; filename="synthetic-call-slip.pdf"' }, body: "%PDF-1.4\n% Synthetic download fixture\n%%EOF" }); return true;
    }
    if (method !== "GET" && pathname.startsWith(`/api/v1/call-slips/${slip.id}/`)) {
      mutations.push({ pathname, body: JSON.parse(request.postData() ?? "{}") });
      item = pathname.endsWith("/void") ? { ...item, state: "VOIDED", void_reason: "Synthetic withdrawal" } : { ...item, state: "COMPLETED", interview_ended_at: mutations.at(-1).body.interview_ended_at };
      await reply(uncertain ? { error: { code: "synthetic_uncertain", message: "Synthetic response lost" } } : item, uncertain ? 503 : 200); return true;
    }
    return false;
  };
  return { handler, mutations, get reads() { return reads; } };
}
async function noManagement(page) {
  for (const label of ["Record interview end", "Operational actions"]) await hidden(page.getByRole("heading", { name: label, exact: true }));
  await hidden(page.getByRole("button", { name: "Void Call Slip", exact: true }));
  await hidden(page.getByRole("button", { name: "Review interview end", exact: true }));
  assert.equal(await page.getByRole("alertdialog").count(), 0);
}
async function readable(page) {
  await shown(page.getByRole("heading", { name: "Permit details", exact: true }));
  for (const text of ["Maria Santos", "BSIT / 4", "Guidance Office", "TEST-CS", "Revision 1"]) await shown(page.getByRole("main").getByText(text, { exact: true }).first());
  const download = page.getByRole("button", { name: "Download Call Slip", exact: true });
  await download.focus();
  assert.ok(await download.evaluate((node) => node === document.activeElement));
  const received = page.waitForEvent("download");
  await page.keyboard.press("Enter");
  assert.equal((await received).suggestedFilename(), "synthetic-call-slip.pdf");
}

for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT"]) {
  for (const state of ["ACTIVE", "COMPLETED", "VOIDED"]) {
    const fixture = world(role, [role === "STUDENT" ? "call_slips.view_self" : "call_slips.view"], state);
    await check(`${role} view-only ${state} keeps details and PDF`, path, { handler: fixture.handler, mobile: role === "GUIDANCE_SERVICES_STAFF" }, async (page, { requests }) => {
      await readable(page); await noManagement(page); await noHorizontalOverflow(page);
      assert.equal(fixture.mutations.length, 0);
      const expected = role === "STUDENT" ? `/api/v1/call-slips/me/${slip.id}/pdf` : `/api/v1/call-slips/${slip.id}/pdf`;
      assert.ok(requests.some((r) => r.pathname === expected));
      if (role === "STUDENT" && state === "VOIDED") await shown(page.getByText("This Call Slip is no longer active.", { exact: true }));
      if (state === "ACTIVE") await screenshot(page, `${role}-view-only`);
    });
  }
}
for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"]) {
  for (const state of ["COMPLETED", "VOIDED"]) {
    const fixture = world(role, ["call_slips.view", "call_slips.manage"], state);
    await check(`${role} manager cannot transition ${state}`, path, { handler: fixture.handler }, async (page) => {
      await readable(page); await noManagement(page); assert.equal(fixture.mutations.length, 0);
    });
  }
  for (const action of ["interview-ended", "void"]) {
    for (const uncertain of [false, true]) {
      const fixture = world(role, ["call_slips.view", "call_slips.manage"], "ACTIVE", { uncertain });
      await check(`${role} ${action} confirmation and ${uncertain ? "uncertain recovery" : "confirmed refresh"}`, path, { handler: fixture.handler }, async (page) => {
        await shown(page.getByRole("heading", { name: "Operational actions", exact: true }));
        let trigger;
        if (action === "interview-ended") {
          await page.getByLabel("Interview ended", { exact: true }).fill("2026-01-01T10:00");
          trigger = page.getByRole("button", { name: "Review interview end", exact: true });
        } else trigger = page.getByRole("button", { name: "Void Call Slip", exact: true });
        await trigger.focus(); await page.keyboard.press("Enter");
        const dialog = page.getByRole("alertdialog"); await shown(dialog);
        assert.equal(fixture.mutations.length, 0, "Review is not submission");
        await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
        assert.ok(await trigger.evaluate((node) => node === document.activeElement), "Cancel restores opener focus");
        await trigger.click(); await shown(dialog);
        const confirm = dialog.getByRole("button", { name: action === "void" ? "Void Call Slip" : "Record interview end", exact: true });
        if (action === "void") {
          assert.equal(await confirm.isDisabled(), true, "Reason is required");
          await dialog.getByLabel("Void reason", { exact: true }).fill("Synthetic withdrawal");
        }
        const before = fixture.reads;
        await confirm.click(); await hidden(dialog);
        await shown(page.getByRole("main").getByText(action === "void" ? "Voided" : "Completed", { exact: true }).first());
        assert.equal(fixture.mutations.length, 1, "Never replay uncertain writes");
        assert.ok(fixture.reads > before, "Current detail is reconciled");
        assert.ok(fixture.mutations[0].pathname.endsWith(`/${action}`));
        assert.deepEqual(fixture.mutations[0].body, action === "void" ? { reason: "Synthetic withdrawal" } : { interview_ended_at: "2026-01-01T02:00:00.000Z" });
        await noManagement(page);
      });
    }
  }
}
for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT"]) {
  const fixture = world(role, ["call_slips.manage", "unrelated.view"]);
  await check(`${role} direct URL without viewing capability makes no detail request`, path, { handler: fixture.handler }, async (page) => {
    await shown(page.getByRole("heading", { name: "Call Slips unavailable", exact: true }));
    await noManagement(page); assert.equal(fixture.reads, 0);
    await hidden(page.getByRole("button", { name: "Download Call Slip", exact: true }));
  });
}
{
  const fixture = world("STUDENT", ["call_slips.view_self"], "ACTIVE", { foreignOwner: true });
  await check("Student cannot view another owner's record", path, { handler: fixture.handler }, async (page) => {
    await shown(page.getByText("Call Slip not found.", { exact: true }));
    await noManagement(page); await hidden(page.getByRole("button", { name: "Download Call Slip", exact: true }));
  });
}
await finish();
