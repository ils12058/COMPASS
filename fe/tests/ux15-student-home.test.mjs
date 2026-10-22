import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PortalHome } from "../src/features/portal/home/portal-home.tsx";
import { StudentHomeAttention } from "../src/features/portal/home/student-home-attention.tsx";
import { getStudentHomeDestinations } from "../src/features/portal/home/student-home-presentation.ts";
import { useOverviewAttention } from "../src/features/portal/home/overview-work.ts";
import { getOverviewMetrics, getOverviewPrimaryAction, getOverviewGreeting, formatOverviewDate, getOverviewRoleContext } from "../src/features/portal/home/overview-presentation.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { getStudentActionsListQueryKey } from "../src/lib/api/generated/student-actions/student-actions.ts";
import { getOverviewGetSummaryQueryKey } from "../src/lib/api/generated/overview/overview.ts";
import { getAnnouncementsListVisibleQueryKey } from "../src/lib/api/generated/announcements/announcements.ts";
import { homeWorld, homeAction, homeInstant, homeCapabilities } from "./support/ux15-home-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";

function renderWorld(state, Component = PortalHome) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  const response = (data) => ({ data, status: 200, headers: {} });
  client.setQueryData(getStudentActionsListQueryKey({ page: 1, page_size: 5 }), response({ items: state.items.slice(0, 5), page: 1, page_size: 5, has_next: state.items.length > 5, generated_at: homeInstant }));
  client.setQueryData(getOverviewGetSummaryQueryKey(), response(state.summary));
  client.setQueryData(getAnnouncementsListVisibleQueryKey({ page: 1, page_size: 3 }), response({ items: state.announcements, page: 1, page_size: 3, has_next: false }));
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: sessionFor(state.account) }, h(Component))));
  client.clear();
  return html;
}

test("Student hierarchy puts actions before discovery, context and announcements", () => {
  const html = renderWorld(homeWorld());
  const sections = ["overview-attention-heading", "student-home-services-heading", "overview-summary-heading", "overview-announcements-heading"].map((id) => html.indexOf(`id="${id}"`));
  assert.ok(sections.every((index) => index >= 0));
  assert.deepEqual(sections, [...sections].sort((a, b) => a - b));
  assert.equal((html.match(/<h1\b/g) ?? []).length, 1);
  assert.match(html, /href="\/portal\/appointments\/book"/);
  assert.match(html, /Book appointment/);
});

test("Home preview preserves the canonical first-five order even when dates would sort differently", () => {
  const state = homeWorld({ items: [homeAction("INVENTORY_START", "INCOMPLETE_SELF_SERVICE", 1), homeAction("CALL_SLIP_ACTIVE", "TIME_SENSITIVE", 2), homeAction("GUIDANCE_MESSAGE_UNREAD", "ACTION_REQUIRED", 3)] });
  function Preview() { return h(StudentHomeAttention, { data: useOverviewAttention(state.account, state.summary) }); }
  const html = renderWorld(state, Preview);
  assert.ok(html.indexOf("Individual Inventory") < html.indexOf("Call Slip"));
  assert.ok(html.indexOf("Call Slip") < html.indexOf("Guidance Messages"));
  assert.match(html, /href="\/portal\/actions"/);
  assert.equal((html.match(/<li\b/g) ?? []).length, 3);
});

test("only server TIME_SENSITIVE actions receive the urgency label", () => {
  const state = homeWorld({ items: [homeAction("CALL_SLIP_ACTIVE", "ACTION_REQUIRED", 1, { due_at: homeInstant })] });
  function Preview() { return h(StudentHomeAttention, { data: useOverviewAttention(state.account, state.summary) }); }
  assert.doesNotMatch(renderWorld(state, Preview), /Time sensitive/);
  state.items[0].priority = "TIME_SENSITIVE";
  assert.match(renderWorld(state, Preview), /Time sensitive/);
});

test("the discovery selection is small, authorized, and never advertises the management catalog", () => {
  assert.deepEqual(getStudentHomeDestinations(homeWorld().account).map((d) => d.href), ["/portal/appointments/my", "/portal/messages", "/portal/inventory", "/portal/good-moral"]);
  const account = homeWorld({ capabilities: ["services.catalog.view", "services.manage", "inventory.manage_self", "good_moral.request_self", "guidance_messages.manage_self"] }).account;
  assert.deepEqual(getStudentHomeDestinations(account), [], "Writing capability alone does not advertise a reading workspace");
});

test("Current, Graduated and Former navigation keeps reading separate from initiation", () => {
  for (const lifecycle of ["CURRENT", "GRADUATED", "FORMER"]) {
    const account = homeWorld({ lifecycle }).account;
    const destinations = getStudentHomeDestinations(account);
    assert.equal(getOverviewPrimaryAction(account)?.href ?? null, lifecycle === "CURRENT" ? "/portal/appointments/book" : null);
    assert.equal(destinations.some((d) => d.href === "/portal/graduate-tracer"), lifecycle === "GRADUATED");
    assert.equal(destinations.some((d) => d.href === "/portal/inventory"), lifecycle !== "GRADUATED");
    assert.ok(destinations.every((d) => !/required|start|complete|available slot/i.test(d.description)));
  }
});

test("missing Graduate Tracer view authority falls back only to authorized historical Inventory", () => {
  const account = homeWorld({ lifecycle: "GRADUATED", capabilities: homeCapabilities.filter((c) => c !== "graduate_tracer.view_self") }).account;
  assert.ok(getStudentHomeDestinations(account).some((d) => d.href === "/portal/inventory"));
  account.capabilities = [];
  assert.deepEqual(getStudentHomeDestinations(account), []);
  assert.equal(getOverviewPrimaryAction(account), null);
});

test("Student metric meanings, null omission, zero and exact destinations are retained", () => {
  const state = homeWorld();
  assert.deepEqual(getOverviewMetrics(state.summary, state.account), [
    { label: "Upcoming appointments", value: 2, href: "/portal/appointments/my?status=UPCOMING" },
    { label: "Routine Interview drafts", value: 1, href: "/portal/routine-interviews" },
    { label: "Good Moral requests", value: 1, href: "/portal/good-moral" },
    { label: "Active Call Slips", value: 1, href: "/portal/call-slips?state=ACTIVE" },
  ]);
  state.summary.student.routine_intake_draft_count = null;
  state.summary.student.upcoming_appointments_count = 0;
  const metrics = getOverviewMetrics(state.summary, state.account);
  assert.equal(metrics[0].value, 0);
  assert.equal(metrics.some((m) => m.label === "Routine Interview drafts"), false);
});

test("Student composition excludes unexpected professional sections and email data", () => {
  const state = homeWorld({ capabilities: [...homeCapabilities, "platform_operations.view"] });
  state.summary.guidance = homeWorld({ role: "COUNSELOR" }).summary.guidance;
  state.summary.platform = homeWorld({ role: "IT_ADMIN" }).summary.platform;
  const html = renderWorld(state);
  assert.doesNotMatch(html, /Email delivery|Routine evaluations pending|Good Moral ready for issuance|View all work|Synthetic Student/);
});

test("professional roles and designations retain their composition without Student discovery", () => {
  for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
    const state = homeWorld({ role, designations: role === "COUNSELOR" ? ["HEAD_GUIDANCE_COUNSELOR"] : role === "INSTITUTIONAL_OFFICER" ? ["DPO"] : [] });
    const html = renderWorld(state);
    assert.doesNotMatch(html, /student-home-services-heading|View all actions|Book appointment/);
    assert.deepEqual(getStudentHomeDestinations(state.account), []);
    assert.equal(html.includes("counselor-work-heading"), role === "COUNSELOR", "Only Counselors receive the dedicated Counselor Home composition");
    if (role === "GUIDANCE_SERVICES_STAFF" || role === "IT_ADMIN") assert.match(html, /overview-attention-heading/);
    if (role === "IT_ADMIN") assert.match(html, /Email delivery|email delivery/);
    if (role === "INSTITUTIONAL_OFFICER") assert.doesNotMatch(html, /overview-summary-heading/);
    assert.equal(getOverviewRoleContext(state.account)?.includes("Head Guidance Counselor") ?? false, role === "COUNSELOR");
  }
});

test("loading, initial failure, stale empty and confirmed empty remain distinct", () => {
  const base = { items: [], isVisible: true, isPending: false, staleNotices: [], viewAllActions: true };
  const render = (data) => renderToStaticMarkup(h(StudentHomeAttention, { data: { ...base, ...data } }));
  assert.match(render({ isPending: true }), /aria-busy="true"/);
  assert.doesNotMatch(render({ isPending: true }), /caught up/);
  assert.match(render({ isCaughtUp: true }), /No current actions need your attention/);
  assert.doesNotMatch(render({ staleNotices: ["My actions could not be refreshed."], retryActions() {} }), /caught up/);
  assert.match(render({ staleNotices: ["My actions could not be refreshed."], retryActions() {} }), /Your last confirmed result had no actions/);
  assert.doesNotMatch(render({ items: [{ id: "error", title: "My actions could not be loaded", detail: "Try again.", href: "/portal/actions", actionLabel: "Open My actions", isError: true }] }), /caught up/);
});

test("greeting and date use institutional time even at a UTC day boundary", () => {
  const account = homeWorld().account;
  assert.equal(getOverviewGreeting(account, new Date("2026-10-21T23:30:00Z")), "Good morning, Alex");
  assert.equal(formatOverviewDate(new Date("2026-10-21T23:30:00Z")), "Thursday, October 22");
});
