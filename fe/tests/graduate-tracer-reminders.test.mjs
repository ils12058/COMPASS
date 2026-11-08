import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { RemindersPage } from "../src/features/reminders/reminders-page.tsx";
import { GraduateTracerReminders } from "../src/features/reminders/graduate-tracer-reminders.tsx";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { getGraduateTracerListRemindersQueryKey } from "../src/lib/api/generated/graduate-tracer/graduate-tracer.ts";

const reviewer = {
  id: "head-1", role: "COUNSELOR", first_name: "Head", last_name: "Counselor",
  email: "head@example.test", designations: ["HEAD_GUIDANCE_COUNSELOR"],
  student_lifecycle_status: null, capabilities: ["graduate_tracer.view"],
};
const graduate = { ...reviewer, role: "STUDENT", student_lifecycle_status: "GRADUATED", capabilities: ["graduate_tracer.view_self"] };
const items = [{
  graduation_record_id: "graduation-1", graduate_name: "Graduate One", graduation_date: "2026-05-08",
  reminders: [
    { kind: "SIX_MONTH", due_date: "2026-11-08", issued_at: "2026-11-08T01:00:00Z", state: "SENT" },
    { kind: "FOLLOW_UP", due_date: "2026-12-08", issued_at: null, state: "UPCOMING" },
  ],
}, {
  graduation_record_id: "graduation-2", graduate_name: "Graduate Two", graduation_date: "2026-05-09",
  reminders: [
    { kind: "SIX_MONTH", due_date: "2026-11-09", issued_at: null, state: "ANSWERED" },
    { kind: "FOLLOW_UP", due_date: "2026-12-09", issued_at: null, state: "ANSWERED" },
  ],
}];

function render({ user = reviewer, rows = items, search = "", pending = false, error = false, page = 1, hasNext = false, component = RemindersPage } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryOnMount: false, staleTime: Infinity, gcTime: Infinity } } });
  const key = getGraduateTracerListRemindersQueryKey({ page, page_size: 20 });
  if (!pending && !error) client.setQueryData(key, { data: { items: rows, page, page_size: 20, has_next: hasNext, ordering: "EARLIEST_GRADUATION" }, status: 200, headers: {} });
  if (error) {
    const query = client.getQueryCache().build(client, { queryKey: key });
    query.setState({ status: "error", error: new Error("Test failure"), fetchStatus: "idle" });
  }
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(component))), { pathname: "/portal/reminders", search }));
  client.clear();
  return html;
}

test("Graduate Tracer review permission opens the section without Appointment management", () => {
  const html = render();
  assert.match(html, /Graduate Tracer/);
  assert.match(html, /Graduate One|Graduate Two/);
  assert.match(html, /Six-month notice/);
  assert.match(html, /30-day follow-up/);
  assert.match(html, /Graduation date/);
  assert.match(html, />Sent<|>Upcoming<|>Answered</);
  assert.match(html, /2026-05-08|2026-11-08|2026-12-08/);
  assert.match(html, /aria-sort="ascending"/);
  assert.doesNotMatch(html, /Upcoming reminders|Send reminder|type="checkbox"|SIX_MONTH|FOLLOW_UP|ANSWERED/);
});

test("non-reviewers cannot see Graduate Tracer reminder data or its section", () => {
  assert.doesNotMatch(render({ user: graduate }), /Graduate One|Six-month notice|Graduate Tracer reminder dates/);
  assert.doesNotMatch(render({ user: { ...reviewer, capabilities: ["appointments.manage"] } }), /Graduate One|Six-month notice|Graduate Tracer reminder dates/);
});

test("reviewers can reach Reminders through the canonical navigation", () => {
  const links = portalWorkspaceGroups(reviewer).flatMap((group) => group.links);
  assert.equal(links.find((link) => link.href === "/portal/reminders")?.label, "Reminders");
  assert.ok(!portalWorkspaceGroups(graduate).flatMap((group) => group.links).some((link) => link.href === "/portal/reminders"));
});

test("loading, empty and failure each remain within the section", () => {
  assert.match(render({ component: GraduateTracerReminders, pending: true }), /Loading Graduate Tracer reminders/);
  assert.match(render({ rows: [] }), /No Graduate Tracer reminders for active Graduate accounts/);
  const html = render({ component: GraduateTracerReminders, error: true });
  assert.match(html, /Graduate Tracer reminders could not be loaded/);
  assert.match(html, /Retry/);
  assert.doesNotMatch(html, /No Graduate Tracer reminders/);
});

test("pagination stays available on an empty later page", () => {
  const html = render({ component: GraduateTracerReminders, rows: [], page: 2, search: "tracer_page=2" });
  assert.match(html, /Graduate Tracer reminder pages/);
  assert.match(html, /Previous/);
  assert.match(html, /Page 2/);
});

test("Graduate Tracer notices deep-link only to the recipient's existing survey page", () => {
  const notice = { target_type: "GRADUATE_TRACER", target_id: "graduate-1" };
  assert.deepEqual(notificationDestination(notice, "graduate-1"), { href: "/portal/graduate-tracer", label: "Open Graduate Tracer survey" });
  assert.equal(notificationDestination(notice, "other-1"), null);
});

test("the section is read-only and keeps independent URL state", () => {
  const source = readFileSync(new URL("../src/features/reminders/graduate-tracer-reminders.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(source, /useMutation|dispatch_due|Send reminder|type="checkbox"|localStorage|\bfetch\(/);
  assert.match(source, /tracer_page/);
  assert.match(source, /tracer_ordering/);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /RefreshFailureNotice/);
});
