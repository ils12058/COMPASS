// NS-1: Counselor-proposed sessions, case Call Slips and Follow-up shortcuts on the actual pages
// with synthetic canonical responses. Nothing here reaches a real API.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user as baseUser } from "./support/ui-hierarchy-fixtures.mjs";
import { counselor, detail, followup, ids, student } from "./support/counseling-cases-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("next-session-proposals");

const uuid = (n) => `d1000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const P = { proposal: uuid(1), option1: uuid(2), option2: uuid(3), thread: uuid(4), appointment: uuid(5), slip: uuid(6) };
const ROOT = "/api/v1/counseling/session-proposals";
const casePage = `/portal/counseling/cases/${ids.case}`;
const proposePage = `${casePage}/propose-session`;
const studentPage = `/portal/appointments/proposals/${P.proposal}`;
const person = (who) => ({ id: who.id, display_name: who.display_name, profile_photo_url: null, profile_photo_updated_at: null });
const option = (id, position, starts_at, delivery_mode = "IN_PERSON") => ({ id, position, delivery_mode, starts_at, ends_at: starts_at.replace("T02:", "T03:") });
const counselorAccount = { ...baseUser(), id: ids.counselor, capabilities: [...baseUser().capabilities, "guidance_followups.view", "guidance_followups.manage", "guidance_messages.view", "guidance_messages.manage"] };
const studentAccount = { ...baseUser("STUDENT"), id: ids.student, capabilities: ["appointments.view_self", "appointments.manage_self", "call_slips.view_self"] };
const session = (account) => ({ user: account, session: { id: "ns1-synthetic", expires_at: "2099-01-01T00:00:00Z", is_current: true } });
const fail = (reply, code, status = 409, details) => reply({ error: { code, message: "Synthetic backend wording must not be shown", ...(details ? { details } : {}) } }, status);

function staffProposal(changes = {}) {
  return {
    id: P.proposal, case: { id: ids.case, reference_code: "CASE-2026-000001" }, student: { ...person(student), institutional_id: student.institutional_id },
    proposed_by: person(counselor), purpose: "FOLLOW_UP_SESSION", state: "PENDING",
    options: [option(P.option1, 1, "2099-01-12T02:00:00Z"), option(P.option2, 2, "2099-01-13T02:00:00Z", "ONLINE")],
    accepted_option_id: null, appointment: null, call_slip_requested: true, call_slip: null, can_issue_call_slip: false, can_withdraw: true,
    follow_up_id: null, expires_at: "2099-01-12T02:00:00Z", created_at: "2026-11-14T01:00:00Z", decided_at: null, version: 1, ...changes,
  };
}
function studentProposal(changes = {}) {
  const staff = staffProposal();
  const shared = ["id", "purpose", "state", "options", "accepted_option_id", "appointment", "expires_at", "created_at", "decided_at", "version"];
  return { ...Object.fromEntries(shared.map((key) => [key, staff[key]])), counselor: staff.proposed_by, can_respond: true, ...changes };
}
const accepted = { id: P.appointment, reference_code: "APT-2099-000777", status: "SCHEDULED", delivery_mode: "IN_PERSON", starts_at: "2099-01-12T02:00:00Z", ends_at: "2099-01-12T03:00:00Z" };

function world({ caseChanges = {}, proposals = [], followupChanges = {}, proposeMode = "success", acceptMode = "success", studentItem = studentProposal(), studentStatus = 200, account = counselorAccount } = {}) {
  const action = followup({ shortcuts: { message_thread_id: P.thread, can_issue_call_slip: true, call_slip_case_id: ids.case, propose_session_case_id: ids.case, completion_prompt: null }, ...followupChanges });
  const state = {
    detail: detail({ next_actions: [action], next_action: action, session_proposals: proposals, can_propose_session: true, call_slips: [], message_thread_id: P.thread, can_issue_call_slip: true, ...caseChanges }),
    followup: action, student: studentItem, writes: [],
  };
  const handler = async ({ reply, pathname, method, request, url }) => {
    if (pathname === "/api/v1/auth/session") return await reply(session(account)), true;
    if (method !== "GET") state.writes.push({ method, pathname, body: request.postData() ? JSON.parse(request.postData()) : null });
    if (pathname === `/api/v1/counseling/cases/${ids.case}` && method === "GET") return await reply(state.detail), true;
    if (pathname === `/api/v1/guidance-followups/${ids.action}` && method === "GET") return await reply(state.followup), true;
    if (pathname === `${ROOT}/context`) {
      assert.equal(url.searchParams.get("case_id"), ids.case);
      return await reply({ case: { id: ids.case, reference_code: "CASE-2026-000001" }, case_version: state.detail.version, student: { ...person(student), institutional_id: student.institutional_id }, authority: "OWNER", open_proposal: state.detail.session_proposals.find((row) => row.state === "PENDING") ?? null, duration_minutes: 60, delivery_modes: ["IN_PERSON", "ONLINE"] }), true;
    }
    if (pathname === `${ROOT}/slots`) {
      const date = url.searchParams.get("date");
      return await reply({ date, timezone: "Asia/Manila", duration_minutes: 60, items: [{ starts_at: `${date}T09:00:00+08:00`, ends_at: `${date}T10:00:00+08:00` }, { starts_at: `${date}T10:00:00+08:00`, ends_at: `${date}T11:00:00+08:00` }] }), true;
    }
    if (pathname === ROOT && method === "POST") {
      if (proposeMode === "taken") return await fail(reply, "session_proposal_time_unavailable", 409, { option: 1, reason: "conflict" }), true;
      const created = staffProposal();
      state.detail = { ...state.detail, session_proposals: [created], version: state.detail.version + 1 };
      return await reply(created, 201), true;
    }
    if (pathname === `${ROOT}/${P.proposal}/withdraw` && method === "POST") {
      state.detail = { ...state.detail, session_proposals: [staffProposal({ state: "WITHDRAWN", can_withdraw: false, decided_at: "2026-11-14T02:00:00Z", version: 2 })] };
      return await reply(state.detail.session_proposals[0]), true;
    }
    if (pathname === `${ROOT}/me/${P.proposal}` && method === "GET") {
      if (studentStatus !== 200) return await fail(reply, "session_proposal_not_found", studentStatus), true;
      return await reply(state.student), true;
    }
    if (pathname === `${ROOT}/me/${P.proposal}/accept`) {
      if (acceptMode === "taken") {
        state.student = studentProposal({ version: 1 });
        return await fail(reply, "session_proposal_time_unavailable", 409, { option: null, reason: "conflict" }), true;
      }
      state.student = studentProposal({ state: "ACCEPTED", can_respond: false, accepted_option_id: P.option1, appointment: accepted, version: 2 });
      return await reply(state.student), true;
    }
    if (pathname === `${ROOT}/me/${P.proposal}/decline`) {
      state.student = studentProposal({ state: "DECLINED", can_respond: false, version: 2 });
      return await reply(state.student), true;
    }
    if (pathname === "/api/v1/call-slips" && method === "POST") {
      return await reply({ id: P.slip }, 201), true;
    }
    if (pathname === "/api/v1/student-actions") {
      return await reply({ items: [{ id: `session-proposal-response:${P.proposal}`, kind: "SESSION_PROPOSAL_RESPONSE", priority: "ACTION_REQUIRED", source_id: P.proposal, due_at: "2099-01-12T02:00:00Z", waiting_since: "2026-11-14T01:00:00Z", conversation_kind: null, pending_count: null }], page: 1, page_size: 20, has_next: false, generated_at: new Date().toISOString() }), true;
    }
    return false;
  };
  return { state, handler };
}

const panel = (page) => page.locator('[aria-labelledby="case-session-proposals-heading"]');
const nextActions = (page) => page.locator('[aria-labelledby="case-next-actions-heading"]');

{
  const w = world();
  await check("case shows proposals and next-action shortcuts without acting", casePage, { handler: w.handler }, async (page) => {
    await shown(page.getByRole("heading", { name: "Session proposals", exact: true }));
    await shown(panel(page).getByText("No sessions have been proposed in this case.", { exact: true }));
    const group = nextActions(page).getByRole("group", { name: /^Reach the Student for/ });
    await shown(group);
    assert.match(await group.getByRole("link", { name: "Message student" }).getAttribute("href"), new RegExp(`^/portal/messages/${P.thread}\\?return_to=`));
    const slip = new URL(await group.getByRole("link", { name: "Issue Call Slip" }).getAttribute("href"), "https://x.invalid");
    assert.equal(slip.searchParams.get("case_id"), ids.case);
    assert.match(await group.getByRole("link", { name: "Propose session" }).getAttribute("href"), new RegExp(`follow_up_id=${ids.action}`));
    assert.deepEqual(w.state.writes, [], "Opening the case writes nothing");
  });
}

{
  const w = world();
  await check("propose two times with a Call Slip request and return to the case", proposePage + `?return_to=${encodeURIComponent(casePage)}`, { handler: w.handler }, async (page) => {
    await shown(page.getByRole("heading", { name: "Propose session", exact: true }));
    await page.getByLabel("Session purpose").selectOption("FOLLOW_UP_SESSION");
    const first = page.getByRole("group", { name: "Time 1" });
    await first.getByLabel("Delivery", { exact: true }).selectOption("IN_PERSON");
    await first.getByLabel("Date", { exact: true }).fill("2099-01-12");
    await first.getByLabel("Time", { exact: true }).locator("option", { hasText: /9:00/ }).waitFor({ state: "attached" });
    await first.getByLabel("Time", { exact: true }).selectOption({ index: 1 });
    await page.getByRole("button", { name: "Add another time" }).click();
    const second = page.getByRole("group", { name: "Time 2" });
    await second.getByLabel("Delivery", { exact: true }).selectOption("ONLINE");
    await second.getByLabel("Date", { exact: true }).fill("2099-01-13");
    await second.getByLabel("Time", { exact: true }).locator("option", { hasText: /10:00/ }).waitFor({ state: "attached" });
    await second.getByLabel("Time", { exact: true }).selectOption({ index: 2 });
    await shown(page.getByText("The Student still gives E-Counseling consent before the session.", { exact: false }));
    await page.getByRole("checkbox", { name: /Also issue a Call Slip/ }).check();
    await page.getByRole("button", { name: "Review proposal" }).click();
    await shown(page.getByRole("alertdialog", { name: `Send this proposal to ${student.display_name}?` }));
    // The same dialog moves to its outcome, so it is found by role once confirmed.
    const dialog = page.getByRole("alertdialog");
    await dialog.getByRole("button", { name: "Send proposal" }).click();
    await shown(dialog.getByText("Proposal sent", { exact: true }));
    const post = w.state.writes.find((row) => row.pathname === ROOT);
    assert.equal(post.body.case_id, ids.case);
    assert.equal(post.body.options.length, 2);
    assert.deepEqual(post.body.options.map((row) => row.delivery_mode), ["IN_PERSON", "ONLINE"]);
    assert.equal(post.body.call_slip_requested, true);
    assert.equal(post.body.expected_case_version, 4);
    assert.equal(post.body.follow_up_id, null);
    await dialog.getByRole("button", { name: "Back to case" }).click();
    await page.waitForURL((url) => url.pathname === casePage);
    await shown(panel(page).getByText(/Follow-up session · Waiting for the Student/));
  });
}

{
  const w = world({ proposeMode: "taken" });
  await check("a time taken before sending is named and nothing is sent twice", proposePage, { handler: w.handler, mobile: true }, async (page) => {
    await page.getByLabel("Session purpose").selectOption("CHECK_IN");
    const first = page.getByRole("group", { name: "Time 1" });
    await first.getByLabel("Delivery", { exact: true }).selectOption("IN_PERSON");
    await first.getByLabel("Date", { exact: true }).fill("2099-01-12");
    await first.getByLabel("Time", { exact: true }).locator("option", { hasText: /9:00/ }).waitFor({ state: "attached" });
    await first.getByLabel("Time", { exact: true }).selectOption({ index: 1 });
    await page.getByRole("button", { name: "Review proposal" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Send proposal" }).click();
    await shown(page.getByText("Time 1 is no longer available. Choose another time.", { exact: true }));
    await shown(page.getByText("This time is no longer available. Choose another.", { exact: true }));
    assert.equal(await page.getByText("Synthetic backend wording", { exact: false }).count(), 0);
    assert.equal(w.state.writes.filter((row) => row.pathname === ROOT).length, 1);
    await noHorizontalOverflow(page);
    await screenshot(page, "propose-conflict-phone");
  });
}

{
  const w = world({ proposals: [staffProposal()] });
  await check("an open proposal blocks another and can be withdrawn", casePage, { handler: w.handler }, async (page) => {
    await shown(panel(page).getByText(/Waiting for the Student/));
    assert.equal(await panel(page).getByRole("link", { name: "Propose session" }).count(), 0, "No second proposal while one is open");
    await shown(panel(page).getByText("Call Slip to issue after an In person time is accepted", { exact: true }));
    await panel(page).getByRole("button", { name: /^Withdraw the proposal sent/ }).click();
    const dialog = page.getByRole("alertdialog", { name: "Withdraw this session proposal?" });
    await dialog.getByRole("button", { name: "Withdraw proposal" }).click();
    await hidden(dialog);
    await shown(panel(page).getByText(/Follow-up session · Withdrawn/));
    assert.deepEqual(w.state.writes.map((row) => row.body), [{ expected_version: 1 }]);
  });
}

{
  const acceptedProposal = staffProposal({ state: "ACCEPTED", accepted_option_id: P.option1, appointment: accepted, can_issue_call_slip: true, can_withdraw: false, decided_at: "2026-11-14T03:00:00Z", version: 2 });
  const w = world({ proposals: [acceptedProposal] });
  await check("an accepted In person session offers Issue Call Slip, issued only by hand", casePage, { handler: w.handler }, async (page) => {
    const link = panel(page).getByRole("link", { name: "Issue Call Slip" });
    await shown(link);
    const href = new URL(await link.getAttribute("href"), "https://x.invalid");
    assert.equal(href.searchParams.get("appointment_id"), P.appointment);
    assert.equal(href.searchParams.get("report_at"), accepted.starts_at);
    await link.click();
    await page.waitForURL((url) => url.pathname === "/portal/call-slips/new");
    await shown(page.getByText(/Linked to case CASE-2026-000001 and its In person Appointment/));
    assert.equal(await page.getByText("Historical / back-entry", { exact: true }).count(), 0, "A case Call Slip is always live");
    await page.getByLabel("Course / Year").fill("BSIT / 2");
    await page.getByRole("button", { name: "Review issuance" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Issue Call Slip" }).click();
    await page.waitForURL((url) => url.pathname === `/portal/call-slips/${P.slip}`);
    const post = w.state.writes.find((row) => row.pathname === "/api/v1/call-slips");
    assert.equal(post.body.counseling_case_id, ids.case);
    assert.equal(post.body.appointment_id, P.appointment);
    assert.equal(post.body.notify_student, true);
    assert.equal(post.body.student_id, student.id);
    assert.equal(new URL(page.url()).searchParams.get("return_to"), casePage.split("?")[0] + "");
  });
}

{
  const w = world({ followupChanges: { shortcuts: { message_thread_id: null, can_issue_call_slip: true, call_slip_case_id: ids.case, propose_session_case_id: ids.case, completion_prompt: { reason: "SESSION_ACCEPTED", appointment_id: P.appointment, appointment_reference: "APT-2099-000777" } } } });
  await check("Follow-up shortcuts and the completion prompt never complete the task", `/portal/follow-ups/${ids.action}`, { handler: w.handler }, async (page) => {
    const region = page.locator('[aria-labelledby="followup-shortcuts-heading"]');
    await shown(region.getByText("Complete this follow-up?", { exact: true }));
    assert.equal(await region.getByRole("link", { name: "Message student" }).count(), 0, "Hidden when no conversation exists");
    await shown(region.getByRole("link", { name: "Issue Call Slip" }));
    await shown(region.getByRole("link", { name: "Propose session" }));
    await region.getByRole("button", { name: "Mark complete" }).click();
    await shown(page.getByLabel("Completion outcome"));
    assert.deepEqual(w.state.writes, [], "The prompt only opens the reader's own completion form");
  });
}

{
  const w = world({ account: studentAccount });
  await check("Student accepts one time at phone width and sees the booked Appointment", studentPage, { handler: w.handler, viewport: { width: 390, height: 780 } }, async (page) => {
    await shown(page.getByRole("heading", { name: "Proposed session", exact: true }));
    await shown(page.getByText("Waiting for your answer", { exact: true }));
    assert.equal(await page.getByText(/CASE-2026|case/i).count(), 0, "The Student sees no case details");
    const accept = page.getByRole("button", { name: "Accept time" });
    assert.equal(await accept.isDisabled(), true);
    await page.getByRole("radio").first().check();
    await accept.click();
    const dialog = page.getByRole("alertdialog", { name: "Book this session?" });
    await dialog.getByRole("button", { name: "Accept and book" }).click();
    await shown(page.getByText(/Appointment APT-2099-000777 is booked/));
    await shown(page.getByRole("link", { name: "Open Appointment" }));
    assert.deepEqual(w.state.writes.map((row) => row.body), [{ option_id: P.option1, expected_version: 1 }]);
    await noHorizontalOverflow(page);
    await screenshot(page, "student-accepted-phone");
  });
}

{
  const w = world({ account: studentAccount, acceptMode: "taken" });
  await check("a taken time books nothing and the Student can decline instead", studentPage, { handler: w.handler }, async (page) => {
    await page.getByRole("radio").first().check();
    await page.getByRole("button", { name: "Accept time" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Accept and book" }).click();
    await shown(page.getByText("That time is no longer available. Choose another time.", { exact: true }));
    assert.equal(await page.getByText("Synthetic backend wording", { exact: false }).count(), 0);
    await page.getByRole("button", { name: "Decline" }).click();
    await page.getByRole("alertdialog", { name: "Decline this proposal?" }).getByRole("button", { name: "Decline proposal" }).click();
    await shown(page.getByText("You declined this proposal. No Appointment was booked.", { exact: true }));
    await shown(page.getByRole("link", { name: "Book an Appointment" }));
  });
}

{
  const w = world({ account: studentAccount, studentStatus: 404 });
  await check("another Student's proposal is not available and offers no retry", studentPage, { handler: w.handler }, async (page) => {
    await shown(page.getByText("This proposed session isn't available to you.", { exact: true }));
    assert.equal(await page.getByRole("button", { name: "Retry" }).count(), 0);
  });
}

{
  const w = world({ account: studentAccount });
  await check("Student actions lead to the respond page", "/portal/actions", { handler: w.handler }, async (page) => {
    const link = page.getByRole("link", { name: "Choose a session time" });
    await shown(link);
    assert.equal(await link.getAttribute("href"), studentPage);
  });
}

{
  const w = world({ account: studentAccount });
  await check("a Student cannot open the Counselor propose page", proposePage, { handler: w.handler }, async (page) => {
    await shown(page.getByText("You don't have access to Counseling.", { exact: true }));
    assert.equal(w.state.writes.length, 0);
  });
}

await finish();
