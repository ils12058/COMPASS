// RA-1 case-session reassignment. Synthetic sessions and fixtures only: no Django is contacted.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointment, appointmentId } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, screenshot, finish } = await createBrowserHarness("ra1-case-reassignment");
const appointmentPath = `/portal/appointments/${appointmentId}`;
const contextPath = `/api/v1/counseling/appointments/${appointmentId}/reassignment`;
const owner = { id: "counselor", display_name: "Maria Reyes", profile_photo_url: null, profile_photo_updated_at: null };
const person = (id, display_name) => ({ id, display_name, profile_photo_url: null, profile_photo_updated_at: null });
const requestId = "e1000000-0000-4000-8000-000000000001";
const request = (fields = {}) => ({
  id: requestId, state: "PENDING", route: "INDEPENDENT_HEAD",
  appointment: { id: appointmentId, reference_code: appointment.reference_code, status: "SCHEDULED", service_name: "Counseling", delivery_mode: "ONLINE", starts_at: appointment.starts_at, ends_at: appointment.ends_at },
  student: person("student", "Maria Santos"), case_reference_code: "CASE-2026-000001", case_owner: owner,
  requested_by: owner, from_provider: owner, to_provider: person("other-counselor", "Ana Cruz"),
  reason: "On leave that day", requested_at: "2026-10-07T00:00:00Z", decided_by: null, decided_at: null, decision_reason: "",
  version: 1, can_approve: false, can_withdraw: true, ...fields,
});

await check("case session: warning, acknowledgement and an approval request instead of a direct move", appointmentPath, {
  overrides: {
    [contextPath]: { case_owner: owner, pending: null },
    [`POST /api/v1/counseling/appointments/${appointmentId}/reassignment-requests`]: async ({ request: sent, reply }) => {
      const body = JSON.parse(sent.postData());
      assert.deepEqual(body, { provider_id: "other-counselor", reason: "On leave that day", acknowledged: true });
      await reply(request(), 201);
    },
  },
}, async (page, { requests }) => {
  await page.getByRole("button", { name: "Reassign", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Reassign Counselor", exact: true });
  await shown(dialog.getByText(/This session is part of Maria Reyes's counseling case\./));
  await dialog.getByLabel("New Counselor", { exact: true }).selectOption("other-counselor");
  await dialog.getByLabel("Reason", { exact: true }).fill("On leave that day");
  const submit = dialog.getByRole("button", { name: "Request reassignment", exact: true });
  assert.equal(await submit.isDisabled(), true, "the acknowledgement comes first");
  await dialog.getByLabel(/I understand the case stays with Maria Reyes/).check();
  await screenshot(page, "case-session-reassign-dialog");
  await submit.click();
  await shown(page.getByText("Reassignment to Ana Cruz is waiting for Head approval. The Appointment stays with Maria Reyes until then.", { exact: true }).first());
  assert.equal(requests.filter((item) => item.method === "POST" && item.pathname.endsWith("/reassign")).length, 0, "never the direct move");
});

await check("a pending request replaces the Reassign button and links to the request", appointmentPath, {
  overrides: { [contextPath]: { case_owner: owner, pending: request() } },
}, async (page) => {
  await shown(page.getByRole("link", { name: "View request", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Reassign", exact: true }).count(), 0);
  assert.equal(await page.getByRole("link", { name: "View request", exact: true }).getAttribute("href"), `/portal/counseling/reassignments/${requestId}`);
});

await check("the receiving Counselor sees whose case the session belongs to", appointmentPath, {
  overrides: { [contextPath]: { case_owner: person("case-owner", "Lea Santos"), pending: null } },
}, async (page) => {
  await shown(page.getByText("Part of Lea Santos's counseling case. Case records stay with Lea Santos.", { exact: true }));
});

await check("Head review: approve with the stated consequence", `/portal/counseling/reassignments/${requestId}`, {
  overrides: {
    [`/api/v1/counseling/appointment-reassignments/${requestId}`]: request({ can_approve: true, can_withdraw: false }),
    [`POST /api/v1/counseling/appointment-reassignments/${requestId}/decision`]: async ({ request: sent, reply }) => {
      assert.deepEqual(JSON.parse(sent.postData()), { action: "approve", expected_version: 1, reason: null });
      await reply(request({ state: "APPROVED", version: 2, can_approve: false, can_withdraw: false, decided_by: person("head", "Head Counselor"), decided_at: "2026-10-07T01:00:00Z" }));
    },
  },
}, async (page) => {
  await shown(page.getByRole("heading", { name: "Session reassignment", exact: true }));
  await shown(page.getByText("Only this session moves. The case, its records and its other sessions stay with Maria Reyes.", { exact: true }));
  await screenshot(page, "head-review");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await shown(dialog.getByText(/moves from Maria Reyes to Ana Cruz/));
  await dialog.getByRole("button", { name: "Approve reassignment", exact: true }).click();
  await shown(page.getByText("Approved. The session is now with Ana Cruz.", { exact: true }));
  await shown(page.getByText("Approved", { exact: true }));
});

await check("Head review: an expired request explains why nothing changed", `/portal/counseling/reassignments/${requestId}`, {
  overrides: {
    [`/api/v1/counseling/appointment-reassignments/${requestId}`]: request({ can_approve: true, can_withdraw: false }),
    [`POST /api/v1/counseling/appointment-reassignments/${requestId}/decision`]: async ({ reply }) =>
      reply({ error: { code: "case_continuity_reassignment_expired", message: "The Appointment or case changed after this request, so it no longer applies. Ask for a new request if the session still needs another Counselor." } }, 409),
  },
}, async (page) => {
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Approve reassignment", exact: true }).click();
  await shown(page.getByText(/so it no longer applies/).first());
});

await finish();
