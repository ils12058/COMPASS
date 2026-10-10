import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { hasWorkQueue } from "../src/features/work-queue/work-queue-access.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";
import { WorkQueuePage } from "../src/features/work-queue/work-queue-page.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getWorkQueueListQueryKey } from "../src/lib/api/generated/work/work.ts";
import { messagesAccount, sessionFor } from "./support/guidance-messages-fixtures.mjs";

function render(items) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  client.setQueryData(getWorkQueueListQueryKey({ page: 1, page_size: 20 }), {
    data: { items, page: 1, page_size: 20, has_next: false, generated_at: "2026-10-10T00:00:00Z" }, status: 200, headers: {},
  });
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: sessionFor(messagesAccount("COUNSELOR")) }, h(WorkQueuePage))));
  client.clear();
  return html;
}

test("Guidance roles get the first daily workspace without a new capability", () => {
  for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
    const user = messagesAccount(role, { capabilities: [] });
    const allowed = ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role);
    assert.equal(hasWorkQueue(user), allowed);
    const links = portalWorkspaceGroups(user).flatMap((group) => group.links);
    assert.equal(links.some((link) => link.href === "/portal/work"), allowed);
    if (allowed) assert.equal(links[0].label, "My work");
  }
});

test("closed item kinds navigate to their source and use action-specific copy", () => {
  const expected = [
    ["GUIDANCE_MESSAGE_REPLY", "Reply to Guidance Message", "messages"],
    ["ROUTINE_EVALUATION", "Review Routine Interview", "routine-interviews"],
    ["GOOD_MORAL_PREPARATION", "Prepare Good Moral request", "good-moral"],
    ["GOOD_MORAL_ISSUANCE", "Issue Good Moral certificate", "good-moral"],
    ["CALL_SLIP_DUE", "Review Call Slip", "call-slips"],
  ];
  for (const [kind, title, domain] of expected) {
    const row = presentWork({ kind, source_id: "synthetic", due_at: null, waiting_since: "2026-10-10T00:00:00Z" });
    assert.equal(row.title, title);
    assert.equal(row.href, `/portal/${domain}/synthetic`);
    assert.match(row.detail, /^Waiting since /);
  }
  assert.match(presentWork({ kind: "CALL_SLIP_DUE", source_id: "s", due_at: "2026-10-10T00:00:00Z" }).detail, /^Report time: /);
});

test("confirmed queue order renders unchanged as a semantic list with visible links", () => {
  const html = render([
    { id: "r", kind: "ROUTINE_EVALUATION", source_id: "r", student: { display_name: "Routine Student" }, waiting_since: "2026-10-10T00:00:00Z" },
    { id: "m", kind: "GUIDANCE_MESSAGE_REPLY", source_id: "m", student: { display_name: "Message Student" }, waiting_since: "2026-01-01T00:00:00Z" },
  ]);
  assert.ok(html.indexOf("Routine Student") < html.indexOf("Message Student"), "No browser sort changes backend order");
  assert.match(html, /<ul[^>]*>/); assert.match(html, /<li[^>]*>/);
  assert.match(html, /href="\/portal\/messages\/m"/);
  assert.doesNotMatch(html, /Mark complete|Reply inline|<textarea/);
});

test("confirmed empty queue has the requested empty copy", () => {
  assert.match(render([]), /You’re caught up\./);
});

test("frontend CI runs Work Queue in both engines and compiles its route", () => {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  assert.match(pkg.scripts["test:ui:regressions"], /node tests\/work-queue\.browser\.mjs/);
  assert.match(pkg.scripts["test:ui:regressions"], /COMPASS_UI_BROWSER=webkit node tests\/work-queue\.browser\.mjs/);
  const workflow = readFileSync(new URL("../../.github/workflows/frontend-targeted.yml", import.meta.url), "utf8");
  assert.match(workflow, /\/portal\/work/);
  assert.match(workflow, /pnpm test:ui:regressions/);
});
