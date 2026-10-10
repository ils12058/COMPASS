import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup as render } from "react-dom/server";
import { ActiveStatusBadge } from "../src/components/ui/active-status-badge.tsx";
import { StatusBadge } from "../src/features/organization/components/organization-shared.tsx";
import { ServicesStatusBadge } from "../src/features/services/services-shared.tsx";
import { AvailabilityStatusBadge } from "../src/features/availability/availability-shared.tsx";
import { RoutineQueryError } from "../src/features/routine-interviews/routine-interviews-shared.tsx";
import { PageHeader } from "../src/components/ui/page-header.tsx";
import { PageAction } from "../src/components/ui/page-action.tsx";
import { Plus } from "lucide-react";

test("identical Active/Inactive meanings share presentation while Legacy keeps its meaning", () => {
  for (const active of [true, false]) {
    const expected = render(h(ActiveStatusBadge, { active }));
    for (const component of [StatusBadge, ServicesStatusBadge, AvailabilityStatusBadge]) assert.equal(render(h(component, { active })), expected);
  }
  const legacy = render(h(AvailabilityStatusBadge, { active: false, legacy: true }));
  assert.match(legacy, /Legacy Availability/);
  assert.match(legacy, /text-warning/);
  assert.doesNotMatch(legacy, />Inactive</);
});

test("Routine query errors preserve heading, content and Retry with one shared alert", () => {
  const html = render(h(RoutineQueryError, { title: "Routine unavailable", message: "Please retry.", onRetry() {} }, h("a", { href: "/portal" }, "Return to Overview")));
  assert.equal((html.match(/role="alert"/g) ?? []).length, 1);
  assert.match(html, /<h2>Routine unavailable<\/h2>/);
  assert.match(html, /Please retry\./);
  assert.match(html, /href="\/portal"/);
  assert.match(html, /<button[^>]*>Retry<\/button>/);
  assert.doesNotMatch(render(h(RoutineQueryError, { message: "Unavailable" })), /<button/);
});

test("header metadata and Help stay outside its named command region", () => {
  const html = render(h(PageHeader, { title: "Response", meta: h("span", null, "Submitted"), help: h("button", null, "Help"), actions: h(PageAction, { icon: Plus, label: "Download" }) }));
  assert.match(html, /<h1[^>]*>Response<\/h1><span>Submitted<\/span>/);
  assert.match(html, /data-page-header-actions=""/);
  const commands = html.slice(html.indexOf('data-page-header-actions=""'));
  assert.doesNotMatch(commands, /Submitted/);
  assert.match(commands, /data-page-action-label=""/);
});

test("back and Help share the navigation row without nesting Help in the back slot", () => {
  const html = render(h(PageHeader, { title: "Session", back: h("a", { href: "/portal/appointments" }, "Back to appointment"), help: h("button", null, "Help") }));
  assert.match(html, /Back to appointment<\/a><button>Help<\/button><\/div>/);
  assert.ok(html.indexOf("<button>Help</button>") < html.indexOf("<h1"));
  assert.equal((html.match(/<button>Help<\/button>/g) ?? []).length, 1);
});
