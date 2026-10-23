import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CounselingContextPanel, CounselingWorkspace } from "../src/features/counseling/counseling-workspace.tsx";
import { EncounterDetailPage } from "../src/features/counseling/encounter-detail-page.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import * as counselingApi from "../src/lib/api/generated/counseling/counseling.ts";
import { CounselingContextSection } from "../src/lib/api/generated/model/index.ts";
import { withNextRouter } from "./support/next-router.mjs";
import { appointmentId, encounterId, counselor, session, overview, encounter, recorded, summary, priorSummary, privateBody } from "./support/cont1a-summary-fixtures.mjs";

const response = (data) => ({ data, status: 200, headers: { date: new Date().toUTCString() } });
function render(element, seed = () => {}, actor = counselor()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  seed(client);
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: session(actor) }, h(UnsavedChangesProvider, null, element)))));
  client.clear();
  return html;
}
const workspace = () => h(CounselingWorkspace, { anchorType: "APPOINTMENT", anchorId: appointmentId });
function seedOverview(client) {
  client.setQueryData(counselingApi.getCounselingContextGetOverviewQueryKey("APPOINTMENT", appointmentId), response(overview({ matching_encounter: recorded })));
}

test("generated Context contract has no Summary operation, query key, hook or section", () => {
  for (const name of ["counselingContextListStudentSessionSummaries", "getCounselingContextListStudentSessionSummariesQueryKey", "useCounselingContextListStudentSessionSummaries"]) {
    assert.equal(name in counselingApi, false, name);
  }
  assert.equal("SHARED_SUMMARIES" in CounselingContextSection, false);
  for (const name of ["useCounselingGetAssignedStudentSessionSummary", "useCounselingPutAssignedStudentSessionSummary", "useCounselingPublishAssignedStudentSessionSummary", "useCounselingGetMyStudentSessionSummary", "useCounselingListMyStudentSessionSummaries"]) {
    assert.equal(typeof counselingApi[name], "function", `${name} remains available`);
  }
});

for (const summaries of [true, false]) {
  test(`Context ignores legacy section and cached prior publication with summary capabilities=${summaries}`, () => {
    const html = render(h(CounselingContextPanel, { anchorType: "APPOINTMENT", anchorId: appointmentId, overview: overview() }), (client) => {
      client.setQueryData([`/api/v1/counseling/context/APPOINTMENT/${appointmentId}/student-session-summaries`, { limit: 20 }], response({ items: [priorSummary] }));
    }, counselor(summaries));
    assert.doesNotMatch(html, /Student Session Summaries|Previous published summaries|student-session-summary-heading/);
    assert.ok(!html.includes(privateBody));
    for (const label of ["Overview", "Inventory", "Support", "History"]) assert.ok(html.includes(`>${label}</button>`), label);
  });
}

test("a Context reference alone does not advertise the Encounter authoring link", () => {
  const html = render(workspace(), seedOverview);
  assert.doesNotMatch(html, /View encounter/);
});

test("the independently authorized own Encounter retains its existing authoring link", () => {
  const html = render(workspace(), (client) => {
    seedOverview(client);
    client.setQueryData(counselingApi.getCounselingGetEncounterQueryKey(encounterId), response(encounter()));
  });
  assert.match(html, /View encounter/);
  assert.ok(html.includes(`/portal/counseling/encounters/${encounterId}`));
  assert.doesNotMatch(html, /Student Session Summary draft|Previous published summaries/);
});

for (const [name, record] of [
  ["other Counselor", encounter({ counselor: { id: "other-counselor", display_name: "Other" } })],
  ["other Student", encounter({ student: { id: "other-student", display_name: "Other" } })],
  ["different record", encounter({ id: "other-encounter" })],
]) {
  test(`canonical Encounter response for ${name} does not advertise authoring`, () => {
    const html = render(workspace(), (client) => {
      seedOverview(client);
      client.setQueryData(counselingApi.getCounselingGetEncounterQueryKey(encounterId), response(record));
    });
    assert.doesNotMatch(html, /View encounter/);
  });
}

test("denied Encounter refresh hides its link even when previously cached data exists", () => {
  const html = render(workspace(), (client) => {
    seedOverview(client);
    const key = counselingApi.getCounselingGetEncounterQueryKey(encounterId);
    client.setQueryData(key, response(encounter()));
    client.getQueryCache().find({ queryKey: key, exact: true }).setState({ status: "error", error: new CompassApiError({ status: 404, body: { error: { code: "counseling_not_found", message: "Unavailable" } }, headers: {}, method: "GET", url: key[0] }) });
  });
  assert.doesNotMatch(html, /View encounter/);
});

for (const status of [401, 403, 404]) {
  test(`denied Context refresh ${status} hides cached protected presentation`, () => {
    const html = render(workspace(), (client) => {
      seedOverview(client);
      client.setQueryData([`/api/v1/counseling/context/APPOINTMENT/${appointmentId}/student-session-summaries`, { limit: 20 }], response({ items: [priorSummary] }));
      const key = counselingApi.getCounselingContextGetOverviewQueryKey("APPOINTMENT", appointmentId);
      client.getQueryCache().find({ queryKey: key, exact: true }).setState({ status: "error", error: new CompassApiError({ status, body: { error: { code: status === 404 ? "counseling_context_not_found" : "permission_denied", message: "Unavailable" } }, headers: {}, method: "GET", url: key[0] }) });
    });
    assert.match(html, /Counseling information unavailable/);
    assert.doesNotMatch(html, /Synthetic CONT-1A Student|Student Session Summaries|Previous published summaries|View encounter/);
    assert.ok(!html.includes(privateBody));
  });
}

for (const published of [false, true]) {
  test(`Encounter Detail keeps the ordinary author summary ${published ? "publication" : "editor"}`, () => {
    const html = render(h(EncounterDetailPage, { encounterId }), (client) => {
      client.setQueryData(counselingApi.getCounselingGetEncounterQueryKey(encounterId), response(encounter()));
      client.setQueryData(counselingApi.getCounselingGetAssignedStudentSessionSummaryQueryKey(encounterId), response(summary({ published_at: published ? "2026-01-06T02:00:00Z" : null })));
    });
    assert.match(html, published ? /Published to Student/ : /Student Session Summary draft/);
    assert.match(html, /Synthetic author draft/);
    assert.ok(!html.includes(privateBody));
  });
}


test("retired ordinary operations and frontend route are removed", async () => {
  for (const name of ["useCounselingGetAssignedSharedSummary", "useCounselingPutAssignedSharedSummary", "useCounselingPublishAssignedSharedSummary", "useCounselingGetMySharedSummary", "useCounselingListMySharedSummaries", "counselingContextListSharedSummaries"]) {
    assert.equal(name in counselingApi, false, name);
  }
  const { existsSync } = await import("node:fs");
  assert.equal(existsSync(new URL("../src/app/(portal)/portal/counseling/summaries/[summaryId]/page.tsx", import.meta.url)), false);
  assert.equal(existsSync(new URL("../src/app/(portal)/portal/counseling/student-session-summaries/[summaryId]/page.tsx", import.meta.url)), true);
});
