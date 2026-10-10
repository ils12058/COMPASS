// Collection ordering contract (ADR-090): closed URL ordering, accessible sortable headers, one
// Sort control on every screen size, sorting kept apart from filters, and Overview attention
// ranked by priority and waiting time rather than by assembly order.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import { SortField } from "../src/components/ui/sort-field.tsx";
import { SortableColumnHeader } from "../src/components/ui/sortable-column-header.tsx";
import { readOrdering, withOrdering } from "../src/features/portal/components/list-ordering-params.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { GoodMoralOperationalList } from "../src/features/good-moral/good-moral-operational-list.tsx";
import { AccountsList } from "../src/features/accounts/list/accounts-list.tsx";
import { CounselorRoutineWorkspace } from "../src/features/routine-interviews/routine-counselor-workspace.tsx";
import { getRoutineInterviewAccess } from "../src/features/routine-interviews/routine-interviews-access.ts";
import { AppointmentsMyPage } from "../src/features/appointments/appointments-my-page.tsx";
import { AnnouncementList } from "../src/features/public/announcements/announcement-list.tsx";
import { ResourceList } from "../src/features/public/resources/resource-list.tsx";
import { ResourcesListPage } from "../src/features/resources/resources-list-page.tsx";
import { useOverviewAttention } from "../src/features/portal/home/overview-work.ts";
import {
  AttentionPriority,
  attentionKey,
  compareAttention,
  rankAttention,
} from "../src/features/portal/home/overview-attention-ranking.ts";
import * as model from "../src/lib/api/generated/model/index.ts";
import { getGoodMoralListRequestsQueryKey } from "../src/lib/api/generated/good-moral/good-moral.ts";
import { getAccountsListQueryKey } from "../src/lib/api/generated/accounts/accounts.ts";
import { getRoutineInterviewsListAssignedQueryKey } from "../src/lib/api/generated/routine-interviews/routine-interviews.ts";
import { getAppointmentsListMyQueryKey } from "../src/lib/api/generated/appointments/appointments.ts";
import { getAnnouncementsListPublicQueryKey } from "../src/lib/api/generated/announcements/announcements.ts";
import { getResourcesListManagedQueryKey, getResourcesListPublicQueryKey } from "../src/lib/api/generated/resources/resources.ts";
import { getWorkQueueListQueryKey } from "../src/lib/api/generated/work/work.ts";
import { getAuthGetSessionQueryKey } from "../src/lib/api/generated/auth/auth.ts";

const ok = (data) => ({ data, status: 200, headers: {} });
const page = (items, extra = {}) => ok({ items, page: 1, page_size: 20, has_next: false, ...extra });
const person = (overrides) => ({
  student_lifecycle_status: null,
  designations: [],
  first_name: "Example",
  last_name: "Person",
  email: "person@example.test",
  ...overrides,
});

function render(element, { user, seed = () => {}, router = {} } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  seed(client);
  const tree = h(QueryClientProvider, { client }, user ? h(PortalSessionProvider, { value: { user } }, element) : element);
  const html = renderToStaticMarkup(withNextRouter(tree, router));
  client.clear();
  return html;
}

const header = (html, label) => {
  const match = html.match(new RegExp(`<th[^>]*>\\s*<button[^>]*>\\s*<span>${label}</span>[\\s\\S]*?</th>`));
  assert.ok(match, `${label} is a sortable header`);
  return match[0];
};
const selectedSort = (html, id) => {
  const select = html.match(new RegExp(`<select[^>]*id="${id}"[^>]*>([\\s\\S]*?)</select>`));
  assert.ok(select, `${id} renders`);
  return select[1].match(/<option value="([^"]*)" selected="">([^<]*)<\/option>/)?.[2];
};

// Shared primitives --------------------------------------------------------------------------------

test("a sortable header is a real button whose th reports the applied order", () => {
  const props = {
    label: "Date and time",
    ascending: "EARLIEST_START",
    descending: "LATEST_START",
    ascendingLabel: "Earliest start first",
    descendingLabel: "Latest start first",
    onSort() {},
  };
  const ascending = renderToStaticMarkup(h("table", null, h("thead", null, h("tr", null, h(SortableColumnHeader, { ...props, current: "EARLIEST_START" })))));
  assert.match(ascending, /<th scope="col" aria-sort="ascending"><button type="button"/);
  assert.match(ascending, /, sorted earliest start first\. Sort latest start first/);
  const descending = renderToStaticMarkup(h("table", null, h("thead", null, h("tr", null, h(SortableColumnHeader, { ...props, current: "LATEST_START" })))));
  assert.match(descending, /aria-sort="descending"/);
  const inactive = renderToStaticMarkup(h("table", null, h("thead", null, h("tr", null, h(SortableColumnHeader, { ...props, current: "STUDENT_ASC" })))));
  assert.doesNotMatch(inactive, /aria-sort/);
  assert.match(inactive, /Sort earliest start first/);
});

test("pressing a header applies its first direction, then reverses it", () => {
  const calls = [];
  const press = (props) => SortableColumnHeader(props).props.children.props.onClick();
  const base = {
    label: "Submitted",
    ascending: "OLDEST_SUBMITTED",
    descending: "NEWEST_SUBMITTED",
    ascendingLabel: "Oldest submitted first",
    descendingLabel: "Newest submitted first",
    onSort: (next) => calls.push(next),
  };
  press({ ...base, current: "STUDENT_ASC", firstDirection: "descending" });
  press({ ...base, current: "NEWEST_SUBMITTED" });
  press({ ...base, current: "OLDEST_SUBMITTED" });
  assert.deepEqual(calls, ["NEWEST_SUBMITTED", "OLDEST_SUBMITTED", "NEWEST_SUBMITTED"]);

  // A one-way column reports its own direction and has nothing to change once applied.
  const oneWay = { label: "Updated", descending: "RECENTLY_UPDATED", descendingLabel: "Recently updated first", onSort() {} };
  const active = renderToStaticMarkup(h("table", null, h("thead", null, h("tr", null, h(SortableColumnHeader, { ...oneWay, current: "RECENTLY_UPDATED" })))));
  assert.match(active, /aria-sort="descending"/);
  assert.match(active, /<button type="button" disabled=""/);
});

test("the Sort field offers only closed values and waits for the applied order", () => {
  const options = [{ value: "NAME_ASC", label: "Last name A–Z" }, { value: "NEWEST_CREATED", label: "Newest accounts first" }];
  const loading = renderToStaticMarkup(h(SortField, { id: "s", value: undefined, options, onChange() {} }));
  assert.match(loading, /<label[^>]*for="s"[^>]*>Sort<\/label>/);
  assert.match(loading, /disabled=""/);
  assert.match(loading, /Loading…/);
  const ready = renderToStaticMarkup(h(SortField, { id: "s", value: "NAME_ASC", options, onChange() {} }));
  assert.match(ready, /<option value="NAME_ASC" selected="">Last name A–Z<\/option>/);

  const chosen = [];
  const select = SortField({ id: "s", value: "NAME_ASC", options, onChange: (next) => chosen.push(next) }).props.children[1];
  select.props.onChange({ target: { value: "NEWEST_CREATED" } });
  select.props.onChange({ target: { value: "created_at" } });
  select.props.onChange({ target: { value: "NAME_ASC" } });
  assert.deepEqual(chosen, ["NEWEST_CREATED"]);
});

test("ordering lives in the URL: closed values only, filters kept, page reset", () => {
  assert.equal(readOrdering("OLDEST_FIRST", model.GoodMoralOrdering), "OLDEST_FIRST");
  for (const invalid of ["-created_at", "created_at", "oldest_first", "", null]) {
    assert.equal(readOrdering(invalid, model.GoodMoralOrdering), undefined);
  }
  const next = withOrdering(new URLSearchParams("status=REQUESTED&search=Reyes&page=4&ordering=NEWEST_FIRST"), "APPLICANT_ASC");
  assert.equal(next.toString(), "status=REQUESTED&search=Reyes&ordering=APPLICANT_ASC");
});

test("every sortable collection has a closed generated ordering enum", () => {
  for (const name of [
    "AccountOrdering",
    "AnnouncementManagementOrdering",
    "AnnouncementOrdering",
    "AppointmentListOrdering",
    "CallSlipOrdering",
    "CounselingEncounterOrdering",
    "EmailDeliveryOrdering",
    "ExitInterviewOrdering",
    "FeedbackResponseOrdering",
    "GoodMoralOrdering",
    "GraduateTracerOrdering",
    "InventoryRosterOrdering",
    "ReferralOrdering",
    "ResourceManagementOrdering",
    "ResourceOrdering",
    "RoutineInterviewOrdering",
    "ServiceOrdering",
  ]) {
    assert.ok(model[name], name);
    for (const value of Object.values(model[name])) assert.match(value, /^[A-Z_]+$/, `${name}.${value}`);
  }
  assert.deepEqual(Object.values(model.AppointmentListOrdering), ["EARLIEST_START", "LATEST_START"]);
});

// Queues and directories ---------------------------------------------------------------------------

const goodMoralStaff = person({ id: "staff", role: "GUIDANCE_SERVICES_STAFF", capabilities: ["good_moral.view"] });
const goodMoralRow = (id, name, created_at) => ({
  id,
  variant: "GRADUATE",
  status: "REQUESTED",
  applicant_name: name,
  issued_at: null,
  cancelled_at: null,
  created_at,
  updated_at: created_at,
  student_institutional_id: null,
  official_receipt_number: "",
  academic_year: null,
  prepared_at: null,
});

test("the Good Moral queue shows the waiting-longest default and does not count it as a filter", () => {
  const filters = { search: "", formRevisionId: "", variant: "", status: "REQUESTED", page: 1 };
  const html = render(h(GoodMoralOperationalList, { filters }), {
    user: goodMoralStaff,
    seed: (client) =>
      client.setQueryData(
        getGoodMoralListRequestsQueryKey({ status: "REQUESTED", page: 1 }),
        page([goodMoralRow("old", "Oldest Applicant", "2026-09-01T00:00:00Z"), goodMoralRow("new", "Newest Applicant", "2026-10-01T00:00:00Z")], {
          ordering: "OLDEST_FIRST",
          filter_options: { form_revisions: [] },
        }),
      ),
  });
  assert.equal(selectedSort(html, "good-moral-sort"), "Waiting longest first");
  assert.ok(html.indexOf("Oldest Applicant") < html.indexOf("Newest Applicant"));
  assert.doesNotMatch(header(html, "Applicant"), /aria-sort/);
  // Status is the one filter in use; the order is not counted.
  assert.match(html, /<span class="sr-only">, 1 in use<\/span>/);

  const sortedOnly = render(h(GoodMoralOperationalList, { filters: { ...filters, status: "", ordering: "APPLICANT_ASC" } }), {
    user: goodMoralStaff,
    seed: (client) =>
      client.setQueryData(
        getGoodMoralListRequestsQueryKey({ ordering: "APPLICANT_ASC", page: 1 }),
        page([goodMoralRow("a", "Ana", "2026-09-01T00:00:00Z")], { ordering: "APPLICANT_ASC", filter_options: { form_revisions: [] } }),
      ),
  });
  assert.doesNotMatch(sortedOnly, / in use</);
  assert.match(header(sortedOnly, "Applicant"), /aria-sort="ascending"/);
  // The chosen order survives filter submission through the GET form.
  assert.match(sortedOnly, /<input type="hidden" name="ordering" value="APPLICANT_ASC"\/>/);
});

const routineCounselor = person({
  id: "counselor",
  role: "COUNSELOR",
  capabilities: ["routine_interviews.view_assigned", "routine_interviews.manage_assigned"],
});
const routineRow = (id, name, submitted) => ({
  id,
  workflow_state: "ACTIVE",
  student: { id: "s-" + id, display_name: name, institutional_id: null },
  academic_year: null,
  inventory_context: null,
  entry_mode: "WALK_IN",
  delivery_mode: "IN_PERSON",
  intake_status: "SUBMITTED",
  intake_submitted_at: submitted,
  evaluation_status: "DRAFT",
  evaluation_finalized_at: null,
  form_revision: null,
  appointment: null,
  counseling_encounter: null,
  created_at: "2026-10-06T00:00:00Z",
});

test("pending Routine evaluations render oldest waiting first with the intake header active", () => {
  const html = render(h(CounselorRoutineWorkspace, { access: getRoutineInterviewAccess(routineCounselor) }), {
    user: routineCounselor,
    router: { pathname: "/portal/routine-interviews", search: "intake_status=SUBMITTED&evaluation_status=DRAFT" },
    seed: (client) =>
      client.setQueryData(
        getRoutineInterviewsListAssignedQueryKey({ intake_status: "SUBMITTED", evaluation_status: "DRAFT", page: 1, page_size: 20 }),
        page([routineRow("r1", "Waited Longest", "2026-09-01T00:00:00Z"), routineRow("r2", "Submitted Today", "2026-10-07T00:00:00Z")], {
          ordering: "OLDEST_WAITING",
        }),
      ),
  });
  assert.equal(selectedSort(html, "routine-queue-sort"), "Oldest waiting first");
  assert.match(header(html, "Student Intake"), /aria-sort="ascending"/);
  assert.ok(html.indexOf("Waited Longest") < html.indexOf("Submitted Today"));
});

const accountsAdmin = person({ id: "admin", role: "IT_ADMIN", capabilities: ["accounts.view", "accounts.manage"] });
const account = (id, first, last) => ({
  id,
  institutional_id: null,
  email: `${id}@example.test`,
  first_name: first,
  middle_name: "",
  last_name: last,
  suffix: "",
  full_name: `${first} ${last}`,
  role: "COUNSELOR",
  student_lifecycle_status: null,
  designations: [],
  is_active: true,
  password_configured: true,
  email_verified: true,
  created_at: "2026-10-01T00:00:00Z",
});

test("the account directory defaults to last name A–Z", () => {
  const html = render(h(AccountsList), {
    user: accountsAdmin,
    router: { pathname: "/portal/accounts" },
    seed: (client) =>
      client.setQueryData(
        getAccountsListQueryKey({ page: 1, page_size: 20 }),
        page([account("a", "Ben", "Abad"), account("b", "Ana", "Reyes")], { ordering: "NAME_ASC" }),
      ),
  });
  assert.equal(selectedSort(html, "accounts-sort"), "Last name A–Z");
  assert.match(header(html, "Account"), /aria-sort="ascending"/);
  assert.match(header(html, "Account"), /Sort last name z–a/);
});

const appointmentStudent = person({ id: "student", role: "STUDENT", student_lifecycle_status: "CURRENT", capabilities: ["appointments.view_self", "appointments.manage_self"] });
const appointment = {
  id: "ap1",
  reference_code: "APT-2026-000001",
  student_id: "student",
  student: { id: "student", institutional_id: null, display_name: "Student Example" },
  service: { id: "svc", code: "COUNSELING", name: "Counseling" },
  provider: { id: "c", display_name: "Counselor Example" },
  delivery_mode: "IN_PERSON",
  starts_at: "2026-10-09T01:00:00Z",
  ends_at: "2026-10-09T02:00:00Z",
  status: "SCHEDULED",
  cancellation_cutoff_minutes: 30,
  cancelled_at: null,
  completed_at: null,
  no_show_at: null,
  created_at: "2026-10-01T00:00:00Z",
};

test("scheduled Appointments show the earliest default, and a chosen order is not a filter", () => {
  const scheduled = render(h(AppointmentsMyPage), {
    user: appointmentStudent,
    router: { pathname: "/portal/appointments" },
    seed: (client) =>
      client.setQueryData(
        getAppointmentsListMyQueryKey({ status: "SCHEDULED", page: 1, page_size: 20 }),
        page([appointment], { ordering: "EARLIEST_START" }),
      ),
  });
  assert.equal(selectedSort(scheduled, "my-appointment-sort"), "Earliest start first");
  assert.doesNotMatch(scheduled, /Order<\/label>/);
  assert.doesNotMatch(scheduled, / in use</);

  const latest = render(h(AppointmentsMyPage), {
    user: appointmentStudent,
    router: { pathname: "/portal/appointments", search: "ordering=LATEST_START" },
    seed: (client) =>
      client.setQueryData(
        getAppointmentsListMyQueryKey({ status: "SCHEDULED", ordering: "LATEST_START", page: 1, page_size: 20 }),
        page([appointment], { ordering: "LATEST_START" }),
      ),
  });
  assert.equal(selectedSort(latest, "my-appointment-sort"), "Latest start first");
  assert.doesNotMatch(latest, / in use</);
  assert.doesNotMatch(latest, />Clear filters</);
  assert.match(latest, /<input type="hidden" name="ordering" value="LATEST_START"\/>/);
});

// Curated feeds --------------------------------------------------------------------------------------

const signedOut = (client) => client.setQueryData(getAuthGetSessionQueryKey(), ok({ authenticated: false, session: null, user: null }));
const announcement = (id, title, pinned) => ({ id, title, body_markdown: "Body", published_at: "2026-10-01T02:00:00Z", expires_at: null, is_pinned: pinned, audience: "PUBLIC" });
const resource = (id, title) => ({ id, title, body_markdown: "Body", published_at: "2026-10-01T02:00:00Z", kind: "ARTICLE", category: "GENERAL", audience: "PUBLIC", external_url: null, has_file: false });

test("public Announcements default to the editorial order and the preview cannot be re-sorted", () => {
  const index = render(h(AnnouncementList, { mode: "index", page: 1 }), {
    seed: (client) => {
      signedOut(client);
      client.setQueryData(getAnnouncementsListPublicQueryKey({ page: 1, page_size: 10 }), page([announcement("pin", "Pinned notice", true)], { page_size: 10, ordering: "RECOMMENDED" }));
    },
  });
  assert.equal(selectedSort(index, "announcement-sort"), "Recommended (pinned first)");

  const sorted = render(h(AnnouncementList, { mode: "index", page: 2, ordering: "TITLE_ASC" }), {
    seed: (client) => {
      signedOut(client);
      client.setQueryData(
        getAnnouncementsListPublicQueryKey({ ordering: "TITLE_ASC", page: 2, page_size: 10 }),
        page([announcement("a", "Alpha", false)], { page: 2, page_size: 10, ordering: "TITLE_ASC", has_next: true }),
      );
    },
  });
  const links = [...sorted.matchAll(/href="([^"]*)"/g)].map((match) => match[1].replaceAll("&amp;", "&"));
  assert.ok(links.includes("/announcements/a?ordering=TITLE_ASC&page=2"), "detail keeps the order");
  assert.ok(links.includes("/announcements?ordering=TITLE_ASC&page=3"), "pagination keeps the order");

  const preview = render(h(AnnouncementList, { mode: "preview" }), {
    seed: (client) => {
      signedOut(client);
      client.setQueryData(getAnnouncementsListPublicQueryKey({ page: 1, page_size: 3 }), page([announcement("pin", "Pinned notice", true)], { page_size: 3, ordering: "RECOMMENDED" }));
    },
  });
  assert.match(preview, /Pinned notice/);
  assert.doesNotMatch(preview, /Sort|<select/);
});

test("public Resources default to the curated order and managers can sort by display order", () => {
  const index = render(h(ResourceList, { mode: "index", page: 1 }), {
    seed: (client) => {
      signedOut(client);
      client.setQueryData(getResourcesListPublicQueryKey({ page: 1, page_size: 9 }), page([resource("r1", "First")], { page_size: 9, ordering: "RECOMMENDED" }));
    },
  });
  assert.equal(selectedSort(index, "resource-sort"), "Recommended order");

  const managed = render(h(ResourcesListPage), {
    router: { pathname: "/portal/resources", search: "ordering=DISPLAY_ORDER" },
    seed: (client) =>
      client.setQueryData(
        getResourcesListManagedQueryKey({ ordering: "DISPLAY_ORDER", page: 1, page_size: 20 }),
        page(
          [{
            ...resource("m1", "Shown first"),
            status: "PUBLISHED",
            display_order: 1,
            content_type: null,
            original_filename: null,
            size_bytes: 0,
            created_at: "2026-09-30T02:00:00Z",
            updated_at: "2026-10-01T02:00:00Z",
            created_by: { id: "p", display_name: "Editor" },
            updated_by: { id: "p", display_name: "Editor" },
            published_by: { id: "p", display_name: "Editor" },
          }],
          { ordering: "DISPLAY_ORDER" },
        ),
      ),
  });
  assert.equal(selectedSort(managed, "resource-management-sort"), "Display order (as readers see it)");
  assert.match(header(managed, "Order"), /aria-sort="ascending"/);
  assert.match(managed, /Readers see Resources in this order: lower display order first, then the newest published\./);
});

// Overview attention -------------------------------------------------------------------------------

test("attention ranks by priority, deadline, then waiting age, independent of input order", () => {
  const item = (id, rank) => ({ id, rank: { stableKey: attentionKey(id, 0, id), ...rank } });
  const items = [
    item("draft", { priority: AttentionPriority.INCOMPLETE_SELF_SERVICE, waitingSince: "2026-01-01T00:00:00Z" }),
    item("recent-work", { priority: AttentionPriority.ACTION_REQUIRED, waitingSince: "2026-10-05T00:00:00Z" }),
    item("undated-work", { priority: AttentionPriority.ACTION_REQUIRED }),
    item("old-work", { priority: AttentionPriority.ACTION_REQUIRED, waitingSince: "2026-09-01T00:00:00Z" }),
    item("failed", { priority: AttentionPriority.CRITICAL }),
    item("due", { priority: AttentionPriority.ACTION_REQUIRED, dueAt: "2026-12-01T00:00:00Z" }),
  ];
  const expected = ["failed", "due", "old-work", "recent-work", "undated-work", "draft"];
  assert.deepEqual(rankAttention(items).map((entry) => entry.id), expected);
  assert.deepEqual(rankAttention([...items].reverse()).map((entry) => entry.id), expected);
  // Equal facts fall back to the stable key.
  assert.ok(compareAttention({ priority: "ACTION_REQUIRED", stableKey: "a" }, { priority: "ACTION_REQUIRED", stableKey: "b" }) < 0);
});

const headCounselor = person({
  id: "head",
  role: "COUNSELOR",
  designations: ["HEAD_GUIDANCE_COUNSELOR"],
  capabilities: ["routine_interviews.view_assigned", "good_moral.view"],
});

function Attention({ user, summary }) {
  const data = useOverviewAttention(user, summary);
  return h("ol", null, data.items.map((item) => h("li", { key: item.id }, `${item.title}: ${item.subject ?? ""}`)));
}

test("Guidance Overview preserves the shared Work Queue backend order", () => {
  const rows = [
    { id: "good-moral-preparation:g1", kind: "GOOD_MORAL_PREPARATION", priority: "ACTION_REQUIRED", source_id: "g1", student: { id: "s1", display_name: "Waiting Applicant" }, waiting_since: "2026-09-20T00:00:00Z", due_at: null, conversation_kind: null },
    { id: "routine-evaluation:r1", kind: "ROUTINE_EVALUATION", priority: "ACTION_REQUIRED", source_id: "r1", student: { id: "s2", display_name: "Routine Student" }, waiting_since: "2026-10-05T00:00:00Z", due_at: null, conversation_kind: null },
  ];
  const html = render(h(Attention, { user: headCounselor, summary: undefined }), {
    user: headCounselor,
    seed: (client) => client.setQueryData(getWorkQueueListQueryKey({ page: 1, page_size: 5 }), page(rows, { page_size: 5, generated_at: "2026-10-10T00:00:00Z" })),
  });
  const order = [...html.matchAll(/<li>([^<]*)<\/li>/g)].map((match) => match[1]);
  assert.deepEqual(order, ["Prepare Good Moral request: Waiting Applicant", "Review Routine Interview: Routine Student"]);
});
