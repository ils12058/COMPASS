import assert from "node:assert/strict";
import { user } from "./ui-hierarchy-fixtures.mjs";
import { casesFixture, counselor, detail, ids } from "./counseling-cases-fixtures.mjs";

export const continuityAPI = "/api/v1/counseling/continuity";
export const transferId = "c3000000-0000-4000-8000-000000000001";
export const receiver = { id: ids.otherCounselor, display_name: "Synthetic Receiving Counselor" };
export const head = { id: "c3000000-0000-4000-8000-000000000002", display_name: "Synthetic Guidance Head" };
export const office = { id: "c3000000-0000-4000-8000-000000000003", display_name: "Synthetic Office Assistant" };
export const transferPath = `/portal/counseling/transfers/${transferId}`;
export const preparePath = `/portal/counseling/cases/${ids.case}/transfer`;
export function continuityAccount(person = counselor, role = "COUNSELOR") {
  const base = user(role);
  return { ...base, id: person.id, first_name: person.display_name, last_name: "", designations: person.id === head.id ? ["HEAD_GUIDANCE_COUNSELOR"] : [], capabilities: [...base.capabilities, "counseling.continuity.view", "counseling.continuity.request", "counseling.continuity.approve", "counseling.continuity.revoke", "counseling.continuity.read_selected", "counseling.handoff.manage_own", "counseling.handoff.read_received", "guidance_followups.view", "guidance_followups.manage"] };
}
export function continuityFixture(options = {}) {
  const account = options.account ?? continuityAccount();
  const caseData = detail();
  const caseIdentity = Object.fromEntries(["id", "reference_code", "student", "primary_counselor", "status", "version"].map(key => [key, caseData[key]]));
  const state = {
    account, operations: [], held: null, denied: false, stale: false,
    context: { case: caseIdentity, office_prepared: account.id !== counselor.id, receiver_options: [
      { person: receiver, authorization_route: "INDEPENDENT_HEAD", blocked_reason: null },
      { person: head, authorization_route: account.id === counselor.id ? "OWNER_TO_HEAD" : null, blocked_reason: account.id === counselor.id ? null : "No independent approver is available." },
    ], tasks: [ { task_id: ids.action, version: 1, category: "COUNSELING", source_kind: null, due_at: "2099-01-07T02:00:00Z", assignee: counselor, title: account.id === counselor.id ? "Protected synthetic action" : null, allowed_dispositions: ["TRANSFER", "RESOLVE_FIRST"], record_accessible: account.id === counselor.id } ], appointments: [ { link_id: ids.appointmentLink, appointment_id: ids.nextAppointment, reference_code: "APT-CW3-0001", starts_at: "2099-01-08T01:00:00Z", ends_at: "2099-01-08T02:00:00Z", status: "SCHEDULED", provider: counselor, record_accessible: account.id === counselor.id } ] },
    item: { id: transferId, reference_code: "TRF-CASE-2026-000001-001", state: "PREPARED", version: 1, case: caseIdentity, receiving_counselor: receiver, outgoing_counselor: counselor, prepared_by: counselor, office_prepared: false, reason: "SERVICE_RESPONSIBILITY_CHANGE", office_preparation_reason: null, waiting_for: null, review_expires_at: null, independent_authorization: true, authorization_route: null, needs_new_arrangement: false, authorized_by: null, authorized_at: null, decided_by: null, decided_at: null, decision_reason: null, student_communication: "NO", student_informed_at: null, communication_recorded_by: counselor, communication_deferral_reason: null, communication_task_id: null, communication_responsible: null, tasks: [], appointments: [], history: [] },
    ...options.state,
  };
  Object.assign(state.item, options.item ?? {});
  function projection() {
    const i = state.item;
    const preparer = account.id === i.prepared_by.id;
    const receiving = account.id === i.receiving_counselor.id;
    const pending = ["PREPARED", "AUTHORIZED"].includes(i.state);
    const reviewer = account.id === head.id && !receiving && !preparer && i.state === "PREPARED" && i.waiting_for;
    const narrow = pending && (preparer || reviewer || (receiving && i.state === "AUTHORIZED"));
    return { ...i, tasks: narrow ? i.tasks.map(task => ({ ...task, title: preparer && !i.office_prepared ? task.title : null, successor_title: null, record_accessible: preparer && !i.office_prepared })) : [], appointments: narrow ? i.appointments.map(a => ({ ...a, record_accessible: preparer && !i.office_prepared })) : [], review_accessible: receiving && i.state === "AUTHORIZED", can_edit: preparer && pending, can_submit: preparer && i.state === "PREPARED" && !i.waiting_for, can_authorize: Boolean(reviewer), can_accept: receiving && i.state === "AUTHORIZED", can_decline: Boolean(reviewer) || (receiving && i.state === "AUTHORIZED"), can_cancel: preparer && pending, can_open_case: i.case.primary_counselor.id === account.id };
  }
  function panel() { return { transfers: [projection()], responsibility: [{ counselor: state.item.case.primary_counselor, started_at: caseData.opened_at, ended_at: null, transfer_id: null, derived_opening: true }], history: state.item.history, can_transfer: true }; }
  const cases = casesFixture({ account, detail: { ...caseData, continuity: panel() } });
  state.handler = async input => {
    const { pathname, method, request, reply, url } = input;
    if (!pathname.startsWith(continuityAPI)) {
      cases.detail = { ...cases.detail, primary_counselor: state.item.case.primary_counselor, continuity: panel() };
      return cases.handler(input);
    }
    state.operations.push({ pathname, method, ...(method !== "GET" ? { body: JSON.parse(request.postData()) } : {}) });
    if (state.held) await state.held;
    if (state.denied) { await reply({ error: { code: "case_continuity_arrangement_not_found", message: "Private diagnostic" } }, 404); return true; }
    if (pathname.endsWith("/office-cases")) { await reply({ items: [caseIdentity], page: 1, page_size: 20, has_next: false }); return true; }
    if (pathname.endsWith("/transfer-context")) {
      const reason = url.searchParams.get("reason");
      const tasks = state.context.tasks.map(task => ({ ...task, allowed_dispositions: reason === "IMPARTIALITY_CONCERN" ? task.allowed_dispositions.filter(value => value !== "RETAIN") : task.allowed_dispositions }));
      await reply({ ...state.context, tasks }); return true;
    }
    if (method === "GET") { await reply(projection()); return true; }
    const body = JSON.parse(request.postData());
    if (pathname.endsWith("/transfers") || method === "PUT") {
      state.item = { ...state.item, receiving_counselor: body.receiving_counselor_id === head.id ? head : receiver, reason: body.reason, office_prepared: state.context.office_prepared, office_preparation_reason: body.office_preparation_reason ?? null, prepared_by: { id: account.id, display_name: account.first_name }, state: "PREPARED", waiting_for: null, student_communication: body.student_communication, communication_deferral_reason: body.communication_deferral_reason ?? null, communication_recorded_by: { id: account.id, display_name: account.first_name }, communication_responsible: body.student_communication === "DEFERRED" ? counselor : null, tasks: body.tasks.map(plan => ({ ...state.context.tasks.find(task => task.task_id === plan.task_id), ...plan, successor_due_at: null, successor_title: null })), appointments: body.appointments.map(plan => ({ ...state.context.appointments.find(a => a.link_id === plan.link_id), ...plan, retention_reason: plan.retention_reason ?? null })) };
      await reply(projection(), 201); return true;
    }
    if (state.stale) { state.item.version++; state.item.state = "CANCELLED"; state.item.needs_new_arrangement = true; state.item.decision_reason = "REQUEST_WITHDRAWN"; await reply({ error: { code: "case_continuity_changed", message: "Private diagnostic" } }, 409); return true; }
    assert.equal(body.expected_version, state.item.version);
    const action = pathname.split("/").at(-1);
    state.item.version++;
    if (action === "submit") {
      const direct = state.item.receiving_counselor.id === head.id && account.id === counselor.id;
      state.item.state = direct ? "AUTHORIZED" : "PREPARED";
      state.item.waiting_for = direct ? head.display_name : "Head approval";
      if (direct) { state.item.authorization_route = "OWNER_TO_HEAD"; state.item.independent_authorization = false; state.item.review_expires_at = "2099-01-15T00:00:00Z"; }
    } else if (action === "authorize") {
      state.item.state = "AUTHORIZED"; state.item.waiting_for = receiver.display_name; state.item.authorized_by = head; state.item.authorized_at = "2026-11-13T02:00:00Z"; state.item.authorization_route = "INDEPENDENT_HEAD"; state.item.review_expires_at = "2099-01-15T00:00:00Z";
    } else if (action === "accept") { state.item.state = "ACCEPTED"; state.item.case = { ...state.item.case, primary_counselor: state.item.receiving_counselor }; state.item.waiting_for = null; }
    else { assert.ok(body.reason); state.item.state = action === "decline" ? "DECLINED" : "CANCELLED"; state.item.decision_reason = body.reason; state.item.needs_new_arrangement = true; state.item.waiting_for = null; }
    state.item.history.push({ id: `event-${state.item.version}`, transfer_id: transferId, reference_code: state.item.reference_code, kind: action === "submit" ? "submitted" : action === "authorize" ? "authorized" : action === "accept" ? "accepted" : `${action}d`, version: state.item.version, actor: { id: account.id, display_name: account.first_name }, occurred_at: "2026-11-13T02:00:00Z", independent_authorization: state.item.independent_authorization, authorization_route: state.item.authorization_route });
    await reply(projection()); return true;
  };
  state.projection = projection;
  return state;
}
