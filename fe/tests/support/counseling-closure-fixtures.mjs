import assert from "node:assert/strict";
import { casesFixture, casesAPI, counselor, summary } from "./counseling-cases-fixtures.mjs";
import { continuityAccount } from "./counseling-continuity-fixtures.mjs";

export const closureNote = "Synthetic documented contact attempts remain in the retained case record.";

export function closureFixture(options = {}) {
  const cases = options.cases ?? casesFixture({ account: options.account ?? continuityAccount(), followups: options.followups ?? [], detail: options.detail });
  const state = { cases, operations: [], mode: "success", transfers: [], coverages: [], delegated_task_ids: [], appointments: [], ...options.state };
  const current = () => cases.detail;
  function context() {
    const tasks = cases.followups.filter(task => task.status === "PENDING").map(task => ({ id: task.id, title: task.title, student_id: task.student_id, category: task.category, source_kind: task.source?.kind ?? null, source_id: task.source?.id ?? null, assigned_to_id: task.assigned_to_id, assigned_to_name: task.assigned_to_name, due_at: task.due_at, version: task.version, post_closure_designated_at: task.post_closure_designated_at ?? null, can_designate: true }));
    const blockers = [...(state.transfers.length ? ["TRANSFER"] : []), ...(state.coverages.length ? ["COVERAGE"] : []), ...(state.delegated_task_ids.length ? ["DELEGATED_TASK"] : []), ...(state.appointments.length ? ["APPOINTMENT"] : []), ...(tasks.some(task => !task.post_closure_designated_at) ? ["TASK"] : [])];
    return { case_id: current().id, version: current().version, blockers, can_close: !blockers.length, transfers: state.transfers, coverages: state.coverages, delegated_task_ids: state.delegated_task_ids, appointments: state.appointments, tasks };
  }
  state.context = context;
  state.handler = async input => {
    const { pathname, method, request, reply } = input;
    if (pathname === "/api/v1/guidance-followups/eligible-assignees") {
      // The backend validates UUID query values; an absent source must be omitted, not sent as "null".
      for (const [key, value] of input.url.searchParams) assert.notEqual(value, "null", `eligible-assignees ${key} must be omitted when absent`);
      await reply({ items: [counselor], page: 1, page_size: 20, has_next: false }); return true; }
    const base = `${casesAPI}/${current().id}`;
    if (pathname === `${base}/closure-context`) {
      state.contextReads = (state.contextReads ?? 0) + 1;
      // Like the backend, outstanding-work review exists only for an Active case.
      if (current().status !== "ACTIVE") { await reply({ error: { code: "counseling_case_closed", message: "Private diagnostic" } }, 409); return true; }
      await reply(context()); return true;
    }
    if (![`${base}/close`, `${base}/reopen`].includes(pathname) && !pathname.endsWith("/after-closure")) return cases.handler(input);
    const body = JSON.parse(request.postData());
    state.operations.push({ pathname, method, body });
    if (state.mode === "failure") { await reply({ error: { code: "counseling_case_closure_invalid", message: "Private diagnostic" } }, 422); return true; }
    if (state.mode === "stale") { cases.detail = { ...current(), version: current().version + 1 }; state.mode = "success"; await reply({ error: { code: "counseling_case_changed", message: "Private diagnostic" } }, 409); return true; }
    if (state.mode === "blocked-race") { state.transfers = [{ id: "c3000000-0000-4000-8000-000000000001", reference_code: "TRF-CASE-2026-000001-001", state: "PREPARED" }]; await reply({ error: { code: "counseling_case_close_blocked", message: "Private diagnostic", blockers: ["TRANSFER"] } }, 409); return true; }
    assert.equal(body.expected_version, current().version, "A lifecycle action takes the case version reviewed by the owner");
    if (pathname.endsWith("/after-closure")) {
      const id = pathname.split("/").at(-2);
      const task = cases.followups.find(task => task.id === id);
      assert.equal(body.expected_task_version, task.version);
      assert.equal(body.administrative_action, true);
      assert.ok(body.assigned_to_id && body.due_at, "Kept work needs an explicit owner and due date");
      Object.assign(task, { assigned_to_id: body.assigned_to_id, due_at: body.due_at, post_closure_designated_at: "2026-11-13T04:00:00Z", version: task.version + 1 });
      cases.detail = { ...current(), version: current().version + 1 };
      await reply(current()); return true;
    }
    if (pathname.endsWith("/close")) {
      assert.equal(context().blockers.length, 0, "Fixture close refuses unresolved work");
      assert.equal(current().status, "ACTIVE");
      const row = { id: `c4000000-0000-4000-8000-${String(current().version).padStart(12, "0")}`, reason: body.reason, outcome: body.outcome, note: body.note, closed_at: "2026-11-13T04:00:00Z", closed_by: counselor, reopened_at: null, reopened_by: null, reopen_reason: null };
      cases.detail = { ...current(), status: "CLOSED", version: current().version + 1, can_manage: false, can_close: false, can_reopen: true, can_add_next_action: false, can_link_appointments: false, closure: row, closures: [...current().closures, row], closed_at: row.closed_at, closure_reason: row.reason };
    } else {
      assert.equal(current().status, "CLOSED");
      const rows = current().closures.map(row => row.reopened_at ? row : { ...row, reopened_at: "2026-11-13T05:00:00Z", reopened_by: counselor, reopen_reason: body.reason });
      cases.detail = { ...current(), status: "ACTIVE", version: current().version + 1, can_manage: true, can_close: true, can_reopen: false, can_add_next_action: true, can_link_appointments: true, closure: null, closures: rows, closed_at: null, closure_reason: null };
    }
    cases.list = [summary(current())];
    await reply(current());
    return true;
  };
  return state;
}
