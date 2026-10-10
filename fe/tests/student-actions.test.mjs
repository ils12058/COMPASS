import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { hasStudentActions } from "../src/features/student-actions/student-actions-access.ts";
import { presentStudentAction } from "../src/features/student-actions/student-actions-presentation.ts";
import { StudentActionsPage } from "../src/features/student-actions/student-actions-page.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getStudentActionsListQueryKey } from "../src/lib/api/generated/student-actions/student-actions.ts";
import { messagesAccount, sessionFor } from "./support/guidance-messages-fixtures.mjs";

function render(items) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  client.setQueryData(getStudentActionsListQueryKey({ page: 1, page_size: 20 }), {
    data: { items, page: 1, page_size: 20, has_next: false, generated_at: "2026-10-10T00:00:00Z" }, status: 200, headers: {},
  });
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: sessionFor(messagesAccount("STUDENT")) }, h(StudentActionsPage))));
  client.clear();
  return html;
}

test("Students get the first daily workspace without a new capability", () => {
  for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
    const user = messagesAccount(role, { capabilities: [] });
    const allowed = role === "STUDENT";
    assert.equal(hasStudentActions(user), allowed);
    const links = portalWorkspaceGroups(user).flatMap((group) => group.links);
    assert.equal(links.some((link) => link.href === "/portal/actions"), allowed);
    if (allowed) assert.equal(links[0].label, "My actions");
  }
});

test("closed item kinds navigate to their source and use action-specific copy", () => {
  const expected = [
    ["GUIDANCE_MESSAGE_UNREAD", "Guidance Messages", "messages"],
    ["ROUTINE_INTAKE", "Routine Interview", "routine-interviews"],
    ["EXIT_INTERVIEW_CONTINUE", "Exit Interview", "exit-interviews"],
    ["EXIT_INTERVIEW_CORRECTION", "Exit Interview correction", "exit-interviews"],
    ["CALL_SLIP_ACTIVE", "Call Slip", "call-slips"],
  ];
  for (const [kind, title, domain] of expected) {
    const row = presentStudentAction({ kind, source_id: "synthetic", due_at: null, waiting_since: "2026-10-10T00:00:00Z" });
    assert.equal(row.title, title);
    assert.equal(row.href, `/portal/${domain}/synthetic`);
    assert.match(row.timing, /^Waiting since /);
  }
  assert.match(presentStudentAction({ kind: "CALL_SLIP_ACTIVE", source_id: "s", due_at: "2026-10-10T00:00:00Z" }).timing, /^Report time: /);
});

test("confirmed queue order renders unchanged as a semantic list with visible links", () => {
  const html = render([
    { id: "r", kind: "ROUTINE_INTAKE", source_id: "r", waiting_since: "2026-10-10T00:00:00Z" },
    { id: "m", kind: "GUIDANCE_MESSAGE_UNREAD", source_id: "m", waiting_since: "2026-01-01T00:00:00Z" },
  ]);
  assert.ok(html.indexOf("Routine Interview") < html.indexOf("Guidance Messages"), "No browser sort changes backend order");
  assert.match(html, /<ul[^>]*>/); assert.match(html, /<li[^>]*>/);
  assert.match(html, /href="\/portal\/messages\/m"/);
  assert.doesNotMatch(html, /Mark complete|Reply inline|<textarea/);
});

test("confirmed empty queue has the requested empty copy", () => {
  assert.match(render([]), /You(?:&#x27;|')re all caught up\./);
});

test("frontend CI runs Student Actions in both engines and compiles its route", () => {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  assert.match(pkg.scripts["test:ui:regressions"], /node tests\/student-actions\.browser\.mjs/);
  assert.match(pkg.scripts["test:ui:regressions"], /COMPASS_UI_BROWSER=webkit node tests\/student-actions\.browser\.mjs/);
  const workflow = readFileSync(new URL("../../.github/workflows/frontend-targeted.yml", import.meta.url), "utf8");
  assert.match(workflow, /\/portal\/actions/);
  assert.match(workflow, /pnpm test:ui:regressions/);
});


test("all eleven kinds map to canonical routes without raw enums or invented completion", () => {
  const expected = {
    INVENTORY_START: "/portal/inventory", INVENTORY_CONTINUE: "/portal/inventory/current",
    ROUTINE_INTAKE: "/portal/routine-interviews/source", EXIT_INTERVIEW_START: "/portal/exit-interviews",
    EXIT_INTERVIEW_CONTINUE: "/portal/exit-interviews/source", EXIT_INTERVIEW_CORRECTION: "/portal/exit-interviews/source",
    GRADUATE_TRACER_CONTINUE: "/portal/graduate-tracer", CALL_SLIP_ACTIVE: "/portal/call-slips/source",
    ECOUNSELING_CONSENT: "/portal/e-counseling/source", ECOUNSELING_JOIN: "/portal/e-counseling/source",
    GUIDANCE_MESSAGE_UNREAD: "/portal/messages/source",
  };
  for (const [kind, href] of Object.entries(expected)) {
    const row = presentStudentAction({ kind, source_id: "source", priority: "ACTION_REQUIRED", pending_count: 2, due_at: null, waiting_since: null });
    assert.equal(row.href, href); assert.ok(row.title && row.detail && row.actionLabel);
    assert.doesNotMatch(row.title + row.detail + row.actionLabel, /INVENTORY_|ACTION_REQUIRED|COUNSELING|Mark complete|Reply to/);
  }
});
