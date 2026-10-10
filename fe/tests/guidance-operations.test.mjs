import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { hasGuidanceOperations } from "../src/features/guidance-operations/guidance-operations-access.ts";
import { presentOperations } from "../src/features/guidance-operations/guidance-operations-presentation.ts";
import { GuidanceOperationsPage } from "../src/features/guidance-operations/guidance-operations-page.tsx";
import { invalidateGuidanceWork } from "../src/features/freshness/guidance-work-invalidation.ts";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getGuidanceOperationsGetQueryKey } from "../src/lib/api/generated/guidance-operations/guidance-operations.ts";
import { getWorkQueueListQueryKey } from "../src/lib/api/generated/work/work.ts";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { operationsData, operationsAccount } from "./support/guidance-operations-fixtures.mjs";

function render(data, user = operationsAccount("COUNSELOR")) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  client.setQueryData(getGuidanceOperationsGetQueryKey(), { data, status: 200, headers: {} });
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, h(PortalSessionProvider,
    { value: sessionFor(user) }, h(GuidanceOperationsPage))));
  client.clear();
  return html;
}

test("Guidance operations follows My work for the two canonical Guidance roles", () => {
  for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
    const user = operationsAccount(role, { capabilities: [] });
    const allowed = ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role);
    assert.equal(hasGuidanceOperations(user), allowed);
    const links = portalWorkspaceGroups(user).flatMap((group) => group.links);
    assert.equal(links.some((link) => link.href === "/portal/operations"), allowed);
    if (allowed) assert.deepEqual(links.slice(0, 2).map((link) => link.label), ["My work", "Guidance operations"]);
  }
});

test("null is omitted and authorized zero remains an explicit metric", () => {
  const data = operationsData("GUIDANCE_SERVICES_STAFF");
  data.backlog.good_moral_preparation.count = 0;
  data.backlog.good_moral_preparation.oldest_waiting_since = null;
  const html = render(data, operationsAccount("GUIDANCE_SERVICES_STAFF"));
  assert.doesNotMatch(html, /Routine evaluations pending|Good Moral ready for issuance|Your upcoming appointments/);
  assert.match(html, /Good Moral needs preparation/);
  assert.match(html, /<dd[^>]*>0<\/dd>/);
  assert.match(html, /Upcoming managed appointments/);
});

test("returned backlog and schedule facts retain semantic labels and oldest associations", () => {
  const html = render(operationsData());
  assert.match(html, /<h1[^>]*>Guidance operations<\/h1>/);
  assert.match(html, /<h2[^>]*>Actionable backlog<\/h2>/);
  assert.match(html, /<h2[^>]*>Schedule<\/h2>/);
  assert.match(html, /<dl[^>]*aria-label="Actionable backlog metrics"/);
  assert.match(html, /Oldest waiting: /);
  assert.match(html, /Oldest due: /);
  assert.match(html, /<time dateTime="2026-10-10T00:00:00Z"/);
  assert.doesNotMatch(html, /guidance_messages|oldest_due_at|good_moral\.issue|total_backlog|leaderboard|overdue|<svg/);
});

test("Head designation never synthesizes null metrics or institution-wide wording", () => {
  const data = operationsData();
  data.backlog.routine_evaluations = null;
  data.backlog.guidance_messages = null;
  const user = operationsAccount("COUNSELOR", { designations: ["HEAD_GUIDANCE_COUNSELOR"] });
  const html = render(data, user);
  assert.doesNotMatch(html, /Routine evaluations pending|Messages awaiting reply|institution-wide|All Counselors/);
});

test("only existing exact-population routes link from metrics", () => {
  const rows = presentOperations(operationsData(), operationsAccount("COUNSELOR"));
  assert.equal(rows.backlog.find((row) => row.label === "Messages awaiting reply").href, undefined);
  assert.equal(rows.backlog.find((row) => row.label === "Call Slips due").href, undefined);
  assert.equal(rows.backlog.find((row) => row.label === "Routine evaluations pending").href, undefined);
  assert.equal(rows.backlog.find((row) => row.label === "Good Moral needs preparation").href, "/portal/good-moral?status=REQUESTED");
  assert.equal(rows.backlog.find((row) => row.label === "Good Moral ready for issuance").href, "/portal/good-moral?status=READY_FOR_ISSUANCE");
  assert.equal(rows.schedule.find((row) => row.label === "Your upcoming appointments").href, "/portal/appointments/my?status=UPCOMING");
  assert.equal(rows.schedule.find((row) => row.label === "Active Call Slips").href, "/portal/call-slips?state=ACTIVE");
  const gss = presentOperations(operationsData("GUIDANCE_SERVICES_STAFF"), operationsAccount("GUIDANCE_SERVICES_STAFF"));
  assert.equal(gss.schedule.find((row) => row.label === "Upcoming managed appointments").href, "/portal/appointments/manage?status=UPCOMING");
});

test("empty wording is constrained to available workflows and leaves schedule context", () => {
  const data = operationsData();
  for (const metric of Object.values(data.backlog)) {
    metric.count = 0;
    if ("oldest_due_at" in metric) metric.oldest_due_at = null;
    else metric.oldest_waiting_since = null;
  }
  const html = render(data);
  assert.match(html, /No work is currently waiting for your action\./);
  assert.doesNotMatch(html, /Office has no|caught up|Oldest waiting|Oldest due/);
  assert.match(html, /Active Call Slips/);
  assert.match(html, /Open My work/);
});

test("all-null backlog is not an authorized zero assertion", () => {
  const data = operationsData();
  for (const name of Object.keys(data.backlog)) data.backlog[name] = null;
  const html = render(data);
  assert.match(html, /No work is available for you to act on/);
  assert.doesNotMatch(html, /No work is currently waiting for your action/);
});

test("shared confirmed-mutation invalidation targets just the two staff projections", async () => {
  const client = new QueryClient();
  const workKey = getWorkQueueListQueryKey({ page: 1, page_size: 20 });
  const operationsKey = getGuidanceOperationsGetQueryKey();
  const unrelatedKey = ["unrelated-sensitive-workspace"];
  for (const key of [workKey, operationsKey, unrelatedKey]) client.setQueryData(key, { confirmed: true });
  await invalidateGuidanceWork(client);
  assert.equal(client.getQueryState(workKey).isInvalidated, true);
  assert.equal(client.getQueryState(operationsKey).isInvalidated, true);
  assert.equal(client.getQueryState(unrelatedKey).isInvalidated, false);
  client.clear();
});
