import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import { getExitInterviewAccess } from "../src/features/exit-interviews/exit-interviews-access.ts";
import { useOverviewAttention } from "../src/features/portal/home/overview-work.ts";
import { ExitInterviewStudentHome } from "../src/features/exit-interviews/exit-interview-student-home.tsx";
import { GoodMoralRequestPage } from "../src/features/good-moral/good-moral-request-page.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { portalCommandDestinations } from "../src/features/portal/components/portal-command-destinations.ts";
import { getExitInterviewsGetMyCurrentQueryKey, getExitInterviewsGetMyStatusQueryKey, getExitInterviewsListMineQueryKey } from "../src/lib/api/generated/exit-interviews/exit-interviews.ts";

const student = { id: "student", role: "STUDENT", student_lifecycle_status: "CURRENT", designations: [], first_name: "Student", last_name: "Example", email: "student@example.test", capabilities: ["exit_interviews.view_self", "exit_interviews.manage_self", "good_moral.view_self", "good_moral.request_self"], exit_interview_workspace_available: false };
const year = { id: "year", label: "2026-2027" };
const empty = { academic_year: year, opportunity: null, current_record: null, has_records: false, inventory_submitted: true, can_start: false, can_edit_current: false, graduation_good_moral_blocked: false };
const opportunity = { id: "opportunity", academic_year: year, source: "GRADUATION", status: "OPEN", opened_at: "2026-10-05T00:00:00Z", completed_at: null, revoked_at: null };
const record = { id: "interview", student: { id: "student", display_name: "Student Example", institutional_id: "2026-1" }, student_name: "Student Example", academic_year: year, status: "SUBMITTED", first_submitted_at: "2026-10-05T01:00:00Z", last_submitted_at: "2026-10-05T01:00:00Z", created_at: "2026-10-05T00:00:00Z", updated_at: "2026-10-05T01:00:00Z" };
const ok = (data) => ({ data, status: 200, headers: {} });
function render(element, state = empty, user = student, history = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  client.setQueryData(getExitInterviewsGetMyStatusQueryKey(), ok(state));
  if (state.current_record) client.setQueryData(getExitInterviewsGetMyCurrentQueryKey(), ok({ ...state.current_record, can_edit: state.can_edit_current }));
  client.setQueryData(getExitInterviewsListMineQueryKey(), ok({ items: history }));
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, element))));
  client.clear(); return html;
}
const destinations = (user) => portalWorkspaceGroups(user).flatMap((group) => group.links).map((item) => item.href);
const home = (state, user = student, history = []) => render(h(ExitInterviewStudentHome, { access: getExitInterviewAccess(user) }), state, user, history);

test("server-backed workspace visibility follows opportunities or history, with capability checks", () => {
  assert.ok(!destinations(student).includes("/portal/exit-interviews"));
  assert.ok(!portalCommandDestinations(student).some((item) => item.href === "/portal/exit-interviews"));
  const opened = { ...student, exit_interview_workspace_available: true };
  for (const lifecycle of ["CURRENT", "GRADUATED", "FORMER"]) assert.ok(destinations({ ...opened, student_lifecycle_status: lifecycle }).includes("/portal/exit-interviews"));
  assert.ok(!destinations({ ...opened, capabilities: [] }).includes("/portal/exit-interviews"));
  assert.equal(getExitInterviewAccess({ ...student, role: "IT_ADMIN", capabilities: ["accounts.manage"] }).canManageOpportunities, false);
  assert.equal(getExitInterviewAccess({ ...student, role: "COUNSELOR", capabilities: ["exit_interviews.manage_opportunities"] }).hasOperationalWorkspace, true);
});
test("no admission means no start action on the direct page", () => {
  const html = home(empty); assert.match(html, /has not opened an Exit Interview/); assert.doesNotMatch(html, />Start</);
});
test("an open graduation opportunity explains the office workflow and offers Start", () => {
  const html = home({ ...empty, opportunity, can_start: true, graduation_good_moral_blocked: true });
  assert.match(html, /Guidance and Counseling Office has opened/); assert.match(html, /graduation Good Moral/); assert.match(html, />Start<span class="sr-only"> Exit Interview/);
});
test("missing Inventory offers its prerequisite link and no Start", () => {
  const html = home({ ...empty, opportunity, inventory_submitted: false }); assert.match(html, /href="\/portal\/inventory"/); assert.doesNotMatch(html, />Start</);
});
test("completed response offers View without another Start", () => {
  const html = home({ ...empty, opportunity: { ...opportunity, status: "COMPLETED" }, current_record: record, has_records: true }); assert.match(html, /View submitted Exit Interview/); assert.doesNotMatch(html, />Start</);
});
test("revoked draft remains visible without Continue", () => {
  const html = home({ ...empty, opportunity: { ...opportunity, status: "REVOKED" }, current_record: { ...record, status: "DRAFT" }, has_records: true }); assert.match(html, /View draft Exit Interview/); assert.doesNotMatch(html, /Continue Exit Interview/);
});
test("controlled reopened draft remains actionable after opportunity completion", () => {
  const html = home({ ...empty, opportunity: { ...opportunity, status: "COMPLETED" }, current_record: { ...record, status: "DRAFT" }, can_edit_current: true, has_records: true }); assert.match(html, /Continue Exit Interview/); assert.doesNotMatch(html, />Start</);
});
test("historical response remains linked without a configured current year", () => {
  const html = home({ ...empty, academic_year: null, has_records: true }, { ...student, student_lifecycle_status: "GRADUATED", exit_interview_workspace_available: true }, [record]); assert.match(html, /href="\/portal\/exit-interviews\/interview"/); assert.doesNotMatch(html, />Start</);
});
test("graduation F4 is blocked with an actionable Exit Interview link", () => {
  const html = render(h(GoodMoralRequestPage), { ...empty, opportunity, graduation_good_moral_blocked: true }); assert.match(html, /Complete and submit your Exit Interview/); assert.match(html, /href="\/portal\/exit-interviews"/); assert.match(html, /<button type="submit"[^>]*disabled=""/);
});
test("ordinary, Manual, and completed graduation F4 remain available", () => {
  for (const state of [empty, { ...empty, opportunity: { ...opportunity, source: "MANUAL" } }, { ...empty, opportunity: { ...opportunity, status: "COMPLETED" }, current_record: record }]) {
    const html = render(h(GoodMoralRequestPage), state); assert.doesNotMatch(html, /Complete and submit your Exit Interview/); assert.doesNotMatch(html, /<button type="submit"[^>]*disabled=""/); assert.match(html, /good-moral-year-level/);
  }
});
test("legacy graduate F6 is available despite current graduation status", () => {
  const html = render(h(GoodMoralRequestPage), { ...empty, opportunity, graduation_good_moral_blocked: true }, { ...student, student_lifecycle_status: "GRADUATED" }); assert.match(html, /good-moral-degree/); assert.doesNotMatch(html, /Complete and submit your Exit Interview/); assert.doesNotMatch(html, /<button type="submit"[^>]*disabled=""/);
});

function Attention({ user }) {
  const data = useOverviewAttention(user, undefined);
  return h("div", null, data.items.map((item) => item.actionLabel).join(" "));
}
test("Overview has no Exit Interview action without a relevant workspace", () => {
  assert.doesNotMatch(render(h(Attention, { user: student })), /Exit Interview/);
});
test("Overview offers Continue only for a server-editable current draft", () => {
  const user = { ...student, exit_interview_workspace_available: true };
  const state = { ...empty, current_record: { ...record, status: "DRAFT" } };
  assert.doesNotMatch(render(h(Attention, { user }), state, user), /Continue Exit Interview/);
  assert.match(render(h(Attention, { user }), { ...state, can_edit_current: true }, user), /Continue Exit Interview/);
});
