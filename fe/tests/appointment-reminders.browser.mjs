import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user, appointment, appointmentId } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("appointment-reminders");
for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"]) {
  const submissions = [];
  const row = { appointment_id: appointmentId, reference_code: appointment.reference_code,
    student_name: appointment.student.display_name, eligible: true, reason: "ELIGIBLE", issued_at: null };
  const handler = async ({ pathname, request, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(user(role))); return true; }
    if (pathname === "/api/v1/appointments/reminders/preview") { await reply({ items: [row] }); return true; }
    if (pathname === "/api/v1/appointments/reminders/send") {
      submissions.push(JSON.parse(request.postData()));
      if (submissions.length === 1) await reply({ error: { code: "unavailable", message: "Synthetic uncertain response" } }, 503);
      else await reply({ items: [{ ...row, accepted: true, reason: "QUEUED" }], accepted: 1, skipped: 0 });
      return true;
    }
    return false;
  };
  await check(`${role} previews and retries the same logical request`, `/portal/appointments/${appointmentId}`, { handler, mobile: role !== "COUNSELOR" }, async page => {
    const trigger = page.getByRole("button", { name: "Send reminder", exact: true });
    await shown(trigger); await trigger.click();
    const dialog = page.getByRole("alertdialog"); await shown(dialog);
    await shown(dialog.getByText(appointment.student.display_name, { exact: true }));
    assert.equal(submissions.length, 0);
    await dialog.getByRole("button", { name: "Send 1 reminder", exact: true }).click();
    await shown(dialog.getByRole("alert"));
    await dialog.getByRole("button", { name: "Send 1 reminder", exact: true }).click();
    await shown(dialog.getByRole("heading", { name: "Reminder requests received", exact: true }));
    assert.equal(submissions.length, 2); assert.deepEqual(submissions[0], submissions[1]);
    assert.ok(submissions[0].request_key); await noHorizontalOverflow(page); await screenshot(page, role);
    await dialog.getByRole("button", { name: "Done", exact: true }).click(); await hidden(dialog);
  });
}
await check("Student never sees staff reminder controls", `/portal/appointments/${appointmentId}`, { role: "STUDENT" }, async page => {
  await hidden(page.getByRole("button", { name: "Send reminder", exact: true }));
});
await finish();
