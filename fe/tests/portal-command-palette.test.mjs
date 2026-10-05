import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

import * as React from "react";
import * as jsx from "react/jsx-runtime";
import { renderToStaticMarkup } from "react-dom/server";
import * as icons from "lucide-react";
import ts from "typescript";

import * as dialog from "../src/components/ui/dialog.tsx";
import { Input } from "../src/components/ui/input.tsx";
import { GuardedPortalLink } from "../src/features/form-safety/guarded-portal-link.tsx";
import { UnsavedChangesProvider, useUnsavedNavigation } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import * as commands from "../src/features/portal/components/portal-command-destinations.ts";
import * as keyboard from "../src/features/portal/components/portal-command-keyboard.ts";
import { PortalCommandPalette, PortalCommandSearch } from "../src/features/portal/components/portal-command-palette.tsx";
import * as session from "../src/features/portal/components/portal-session.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { cn } from "../src/lib/utils/cn.ts";
import { withNextRouter } from "./support/next-router.mjs";

const { createElement: h, isValidElement } = React;
const user = (role, capabilities, extra = {}) => ({ id: "00000000-0000-4000-8000-000000000001", email: "fixture@example.test", first_name: "Fixture", last_name: "User", role, capabilities, designations: [], student_lifecycle_status: role === "STUDENT" ? "CURRENT" : null, ...extra });
// Current role/designation authority from accounts/policy.py; unused confidential-domain grants
// are omitted. Tests below separately exercise overridden effective capabilities.
const student = user("STUDENT", ["accounts.view", "organization.structure.view", "services.catalog.view", "availability.view", "appointments.view_self", "appointments.manage_self", "inventory.view_self", "inventory.manage_self", "exit_interviews.view_self", "exit_interviews.manage_self", "routine_interviews.view_self", "routine_interviews.manage_self", "shared_summaries.view_self", "call_slips.view_self", "good_moral.view_self", "good_moral.request_self", "feedback.submit_customer_feedback", "feedback.submit_csm", "graduate_tracer.view_self", "graduate_tracer.manage_self"]);
const staff = user("GUIDANCE_SERVICES_STAFF", ["exit_interviews.manage_opportunities", "academic_years.view", "institutional_forms.view", "good_moral.view", "good_moral.prepare", "accounts.view", "organization.structure.view", "services.catalog.view", "availability.view", "appointments.view_self", "appointments.manage", "referrals.view", "referrals.manage", "call_slips.view", "call_slips.manage", "announcements.manage", "resources.manage"]);
const counselor = user("COUNSELOR", [...staff.capabilities.filter((code) => code !== "exit_interviews.manage_opportunities"), "academic_years.view", "institutional_forms.view", "availability.manage_self", "inventory.view", "inventory.reopen", "counseling.view_assigned", "counseling.manage_assigned", "routine_interviews.view_assigned", "reports.view", "good_moral.view", "good_moral.manage", "good_moral.issue"]);
const head = { ...counselor, designations: ["HEAD_GUIDANCE_COUNSELOR"], capabilities: [...counselor.capabilities, "exit_interviews.manage_opportunities", "organization.manage", "services.manage", "availability.manage", "academic_years.manage", "exit_interviews.view", "feedback.view_customer_feedback", "feedback.view_csm", "graduate_tracer.view"] };
const it = user("IT_ADMIN", ["accounts.view", "accounts.manage", "platform_operations.view", "platform_operations.manage", "organization.structure.view", "organization.manage", "services.catalog.view", "services.manage", "availability.view", "availability.manage"]);
const dpo = user("INSTITUTIONAL_OFFICER", ["privacy_governance.view", "privacy_governance.manage", "privacy_governance.retention.view", "privacy_governance.retention.manage", "privacy_governance.retention.approve", "privacy_governance.activity.export"], { designations: ["DPO"] });
const hrefs = (account) => commands.portalCommandDestinations(account).map((item) => item.href);

for (const [name, account] of Object.entries({ student, staff, counselor, head, it, dpo })) {
  test(`${name}: root visibility matches the dock and account destinations remain available`, () => {
    const index = commands.portalCommandDestinations(account);
    for (const group of portalWorkspaceGroups(account)) {
      for (const root of group.links) assert.ok(index.some((item) => item.href === root.href && item.label === root.label));
    }
    assert.equal(index[0].label, "Overview");
    assert.equal(index.filter((item) => item.group === "Account").length, 5);
    for (const item of index) {
      assert.ok(existsSync(new URL(`../src/app/(portal)${item.href}/page.tsx`, import.meta.url)), item.href);
      assert.doesNotMatch(item.href, /\[|\]|\?|[0-9a-f]{8}-/);
      assert.doesNotMatch(JSON.stringify(item), /fixture@example|00000000|Fixture/);
    }
  });
}

test("Students get self destinations and never staff/admin/DPO destinations", () => {
  const paths = hrefs(student);
  for (const path of ["/portal/appointments/my", "/portal/appointments/book", "/portal/inventory/current", "/portal/good-moral/request", "/portal/feedback"]) assert.ok(paths.includes(path));
  assert.ok(paths.every((path) => !/^\/portal\/(accounts|organization|privacy|platform|availability|reports)(?:\/|$)|\/responses|\/manage/.test(path)));
  assert.ok(!hrefs({ ...student, student_lifecycle_status: "GRADUATED" }).includes("/portal/appointments/book"));
});

test("GSS, Counselor, and Head Guidance keep their distinct scheduling and operational scopes", () => {
  assert.ok(hrefs(staff).includes("/portal/appointments/manage"));
  assert.ok(!hrefs(staff).includes("/portal/appointments/my"));
  assert.ok(!hrefs(staff).some((path) => path.startsWith("/portal/availability")));
  assert.ok(hrefs(counselor).includes("/portal/availability/me"));
  assert.ok(!hrefs(counselor).includes("/portal/availability/office"));
  assert.ok(!hrefs(counselor).some((path) => /^\/portal\/(platform|privacy|accounts|organization)/.test(path)));
  for (const path of ["/portal/organization/responsibilities", "/portal/organization/student-affiliations", "/portal/availability/office", "/portal/availability/providers", "/portal/feedback/csm/responses"]) assert.ok(hrefs(head).includes(path));
  assert.ok(!hrefs(head).some((path) => /^\/portal\/(platform|privacy|accounts)/.test(path)));
});

test("reference structure, catalog reads, and submission access never imply management access", () => {
  const account = user("STUDENT", ["organization.structure.view", "services.catalog.view", "feedback.submit_csm"]);
  assert.ok(!hrefs(account).some((path) => /^\/portal\/(organization|services)/.test(path)));
  assert.ok(!hrefs(account).includes("/portal/feedback/csm/responses"));
  assert.ok(!hrefs(head).includes("/portal/feedback/csm"), "submission forms require an opportunity and are not indexed");
});

test("DPO and Platform destinations follow effective capabilities, not role/designation labels", () => {
  assert.ok(hrefs(dpo).includes("/portal/privacy/retention"));
  assert.ok(!hrefs({ ...dpo, capabilities: [] }).includes("/portal/privacy"));
  const privacyReader = user("COUNSELOR", ["privacy_governance.view"]);
  assert.ok(hrefs(privacyReader).includes("/portal/privacy/activity"));
  assert.ok(!hrefs(privacyReader).includes("/portal/privacy/retention"));
  const retentionReader = user("INSTITUTIONAL_OFFICER", ["privacy_governance.retention.view"]);
  assert.ok(hrefs(retentionReader).includes("/portal/privacy/retention"));
  assert.ok(!hrefs(retentionReader).includes("/portal/privacy/notices"));
  assert.ok(!hrefs(retentionReader).includes("/portal/privacy/retention/rules/new"));
  for (const slug of ["health", "maintenance", "email-delivery", "environment", "activity"]) assert.ok(hrefs(it).includes(`/portal/platform/${slug}`));
  assert.ok(!hrefs({ ...it, capabilities: it.capabilities.filter((value) => value !== "platform_operations.view") }).some((path) => path.startsWith("/portal/platform")));
});

test("deep actions disappear when their actual manage capability is removed", () => {
  const readonly = { ...head, capabilities: head.capabilities.filter((value) => !value.endsWith(".manage")) };
  for (const path of ["/portal/referrals/new", "/portal/call-slips/new", "/portal/resources/new", "/portal/announcements/new", "/portal/services/new"]) assert.ok(!hrefs(readonly).includes(path));
  const privacyReader = { ...dpo, capabilities: dpo.capabilities.filter((value) => !value.endsWith(".manage")) };
  assert.ok(!hrefs(privacyReader).includes("/portal/privacy/notices/new"));
  assert.ok(!hrefs(privacyReader).includes("/portal/privacy/retention/rules/new"));
});

const all = commands.portalCommandDestinations({ ...head, capabilities: [...new Set([...student.capabilities, ...head.capabilities, ...it.capabilities, ...dpo.capabilities])] });
for (const [query, expected] of [["retention", "/portal/privacy/retention"], ["student affiliation", "/portal/organization/student-affiliations"], ["mfa", "/portal/account/security"], ["email delivery", "/portal/platform/email-delivery"], ["worker", "/portal/platform/health"], ["forms", "/portal/institutional-forms"], ["profile", "/portal/account/profile"], ["book", "/portal/appointments/book"]]) {
  test(`search alias: ${query}`, () => {
    const index = query === "book" ? commands.portalCommandDestinations(student) : all;
    assert.ok(commands.searchPortalCommands(index, query).some((item) => item.href === expected));
  });
}

test("search normalization, ranking, no-results and stable ties are deterministic", () => {
  const base = all[0];
  const index = [
    { ...base, label: "Other", keywords: ["find"] },
    { ...base, label: "Context", breadcrumb: "Find › Context" },
    { ...base, label: "A finder" },
    { ...base, label: "Finder" },
    { ...base, label: "Find" },
    { ...base, label: "Finder again" },
  ];
  assert.deepEqual(commands.searchPortalCommands(index, " FIND ").map((item) => item.label), ["Find", "Finder", "Finder again", "A finder", "Context", "Other"]);
  assert.equal(commands.normalizeCommandQuery("  STUDENT   affiliation  "), "student affiliation");
  assert.deepEqual(commands.searchPortalCommands(all, "xyzzynothing"), []);
  assert.deepEqual(commands.searchPortalCommands(all, "  "), all);
  assert.deepEqual(commands.searchPortalCommands(all, "activity"), commands.searchPortalCommands(all, "ACTIVITY"));
});

function key(overrides = {}) {
  return Object.assign(new Event("keydown", { cancelable: true }), { key: "k", ctrlKey: true, metaKey: false, altKey: false, shiftKey: false, repeat: false, isComposing: false, ...overrides });
}
test("Ctrl/Meta+K toggle, prevent default, ignore repeats/composition/modifiers, and clean up", () => {
  const window = new EventTarget();
  let toggles = 0;
  let open = false;
  const stop = keyboard.registerPortalCommandShortcut(() => { toggles += 1; open = !open; }, () => null, window, { querySelectorAll: () => [] });
  for (const event of [key(), key({ ctrlKey: false, metaKey: true })]) {
    window.dispatchEvent(event);
    assert.equal(event.defaultPrevented, true);
  }
  assert.equal(open, false);
  for (const changes of [{ repeat: true }, { isComposing: true }, { shiftKey: true }, { altKey: true }, { ctrlKey: false }, { metaKey: true }, { key: "j" }]) {
    const event = key(changes);
    window.dispatchEvent(event);
    assert.equal(event.defaultPrevented, false);
  }
  const owned = key(); owned.preventDefault(); window.dispatchEvent(owned);
  assert.equal(toggles, 2);
  stop(); window.dispatchEvent(key()); assert.equal(toggles, 2);
});

test("foreign Radix dialogs, confirmations, and native dialogs block the shortcut", () => {
  const window = new EventTarget();
  const own = {};
  let modals = [{}];
  let toggles = 0;
  const stop = keyboard.registerPortalCommandShortcut(() => { toggles += 1; }, () => own, window, {
    querySelectorAll(selector) {
      assert.match(selector, /role="dialog"/);
      assert.match(selector, /role="alertdialog"/);
      assert.match(selector, /dialog\[open\]/);
      return modals;
    },
  });
  const ignored = key(); window.dispatchEvent(ignored);
  assert.equal(ignored.defaultPrevented, false);
  assert.equal(toggles, 0);
  modals = [own]; window.dispatchEvent(key()); assert.equal(toggles, 1);
  stop();
});

function find(node, predicate) {
  if (!isValidElement(node)) return null;
  if (predicate(node)) return node;
  for (const child of [node.props.children].flat(Infinity)) {
    const match = find(child, predicate);
    if (match) return match;
  }
  return null;
}

// Exercise the actual search component's handlers with small hook storage. SSR below separately
// verifies its real React markup and guarded links; the browser review covers the DOM lifecycle.
function searchHarness(destinations = commands.portalCommandDestinations(student), pathname = "/portal") {
  const source = readFileSync(new URL("../src/features/portal/components/portal-command-palette.tsx", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } });
  const slots = [];
  let cursor = 0;
  let closes = 0;
  let activations = 0;
  const dependencies = {
    "react/jsx-runtime": jsx, "lucide-react": icons, "next/navigation": { usePathname: () => pathname },
    "@/components/ui/dialog": dialog, "@/components/ui/input": { Input },
    "@/features/form-safety/guarded-portal-link": { GuardedPortalLink },
    "@/features/portal/components/portal-command-destinations": commands,
    "@/features/portal/components/portal-command-keyboard": keyboard,
    "@/features/portal/components/portal-session": session, "@/lib/utils/cn": { cn },
    react: { ...React,
      useState(initial) { const index = cursor++; if (!(index in slots)) slots[index] = initial; return [slots[index], (value) => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
      useRef(initial) { const index = cursor++; return slots[index] ??= { current: initial }; },
      useId() { return `command-${cursor++}`; }, useEffect() {}, useMemo: (derive) => derive(),
    },
  };
  const context = { exports: {}, require: (name) => { assert.ok(name in dependencies, name); return dependencies[name]; } };
  vm.runInNewContext(outputText, context);
  return {
    render() {
      cursor = 0;
      const tree = context.exports.PortalCommandSearch({ destinations, pathname, onNavigate: () => { closes += 1; } });
      find(tree, (node) => node.props.role === "listbox").props.ref.current = { querySelector: () => ({ click() { activations += 1; } }) };
      return tree;
    },
    get closes() { return closes; }, get activations() { return activations; },
  };
}

test("Arrow Down/Up update aria selection, Enter activates the guarded link, and query resets it", () => {
  const harness = searchHarness();
  let tree = harness.render();
  const input = () => find(tree, (node) => node.props.role === "combobox").props;
  const selected = () => find(tree, (node) => node.props["aria-selected"] === true).props;
  const event = (key) => ({ key, nativeEvent: { isComposing: false }, preventDefault() {} });
  const first = selected().id;
  input().onKeyDown(event("ArrowDown")); tree = harness.render(); assert.notEqual(selected().id, first);
  input().onKeyDown(event("ArrowUp")); tree = harness.render(); assert.equal(selected().id, first);
  input().onKeyDown(event("Enter")); assert.equal(harness.activations, 1);
  input().onChange({ target: { value: "mfa" } }); tree = harness.render(); assert.equal(selected().href, "/portal/account/security");
  assert.equal(input()["aria-activedescendant"], selected().id);
  input().onChange({ target: { value: "no-such-feature" } }); tree = harness.render();
  assert.equal(input()["aria-activedescendant"], undefined);
  input().onKeyDown(event("Enter")); assert.equal(harness.activations, 1);
});

test("selecting the current pathname closes without navigation and preserves existing query state", () => {
  const harness = searchHarness(undefined, "/portal/account/security");
  const tree = harness.render();
  const result = find(tree, (node) => node.props.href === "/portal/account/security").props;
  let prevented = false;
  result.onClick({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(harness.closes, 1);
  assert.equal(harness.activations, 0);
});

test("actual GuardedPortalLink rejects dirty-form navigation before the palette can close", () => {
  let link;
  let guard;
  let closed = false;
  let route = "/portal/account/profile";
  const form = { contact_number: "unsaved value" };
  function Probe() {
    guard = useUnsavedNavigation();
    link = GuardedPortalLink({ href: "/portal/notifications", onNavigate() { closed = true; } });
    return null;
  }
  renderToStaticMarkup(h(UnsavedChangesProvider, null, h(Probe)));
  guard.registerGuard("profile", { pathname: route, message: "Discard your unsaved profile?" });
  const previous = globalThis.window;
  try {
    for (const accepted of [false, true]) {
      globalThis.window = { location: { href: "http://localhost" + route }, confirm: () => accepted };
      let prevented = false;
      link.props.onNavigate({ preventDefault() { prevented = true; } });
      if (!prevented) route = "/portal/notifications";
      assert.equal(closed, accepted);
      assert.equal(route, accepted ? "/portal/notifications" : "/portal/account/profile");
      assert.equal(form.contact_number, "unsaved value");
    }
  } finally { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; }
});

test("authorized search markup exposes coherent ARIA and never contains hidden unauthorized commands", () => {
  const html = renderToStaticMarkup(withNextRouter(h(UnsavedChangesProvider, null, h(PortalCommandSearch, { destinations: commands.portalCommandDestinations(student), pathname: "/portal", onNavigate() {} }))));
  assert.match(html, /role="combobox"/); assert.match(html, /role="listbox"/); assert.match(html, /role="option"/);
  assert.match(html, /aria-activedescendant=/); assert.match(html, /aria-selected="true"/);
  assert.match(html, /Search COMPASS features/); assert.match(html, /Account › Security/);
  assert.doesNotMatch(html, /Platform Operations|Retention|Manage appointments|Student affiliations|Create account/);
});

test("visible trigger names the same palette and shortcut hints are supplemental", () => {
  const html = renderToStaticMarkup(withNextRouter(h(session.PortalSessionProvider, { value: { user: student } }, h(PortalCommandPalette))));
  assert.match(html, /aria-label="Go to a COMPASS feature"/);
  assert.match(html, /Go to…/);
  assert.match(html, /aria-keyshortcuts="Meta\+K Control\+K"/);
  assert.match(html, /<kbd aria-hidden="true"/);
  assert.doesNotMatch(html, /role="dialog"/, "closed palette creates no hidden result index");
});

test("opening focuses search and closing returns to the opener or the surviving trigger", () => {
  let palette;
  function Probe() { palette = PortalCommandPalette(); return null; }
  renderToStaticMarkup(withNextRouter(h(session.PortalSessionProvider, { value: { user: student } }, h(Probe))));
  const content = find(palette, (node) => node.type === dialog.DialogContent).props;
  const trigger = find(palette, (node) => node.type === "button").props;
  class Element {
    isConnected = true;
    count = 0;
    focus() { this.count += 1; }
  }
  const originalDocument = globalThis.document;
  const originalElement = globalThis.HTMLElement;
  try {
    const opener = new Element();
    const search = new Element();
    const button = new Element();
    globalThis.HTMLElement = Element;
    globalThis.document = { activeElement: opener };
    content.ref.current = { querySelector: () => search };
    trigger.ref.current = button;
    const event = { preventDefault() {} };
    content.onOpenAutoFocus(event);
    assert.equal(search.count, 1);
    content.onCloseAutoFocus(event);
    assert.equal(opener.count, 1);
    opener.isConnected = false;
    content.onCloseAutoFocus(event);
    assert.equal(button.count, 1);
  } finally {
    if (originalDocument === undefined) delete globalThis.document; else globalThis.document = originalDocument;
    if (originalElement === undefined) delete globalThis.HTMLElement; else globalThis.HTMLElement = originalElement;
  }
});

test("typing stays local, keeps aliases out of rendered labels, and does not persist or log queries", () => {
  const harness = searchHarness();
  let tree = harness.render();
  find(tree, (node) => node.props.role === "combobox").props.onChange({ target: { value: "mfa" } });
  tree = harness.render();
  const match = find(tree, (node) => node.props.role === "option");
  assert.equal(match.props.href, "/portal/account/security");
  assert.equal(match.props.prefetch, false);
  assert.doesNotMatch(JSON.stringify(match.props.children), /authenticator|2fa|sessions/);
  const source = readFileSync(new URL("../src/features/portal/components/portal-command-palette.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(source, /fetch\(|localStorage|sessionStorage|console\.|router\.push|mutate/);
  assert.ok(!all.some((item) => /\/security\/(password|email|sessions|authenticator)|\/feedback\/(csm|customer-feedback)$/.test(item.href)));
});
