// Announcement and Resource search, traced boundary by boundary: the submitted form value, the
// canonical URL, the list's query parameters, the generated request URL and query key, and the
// rows rendered from the response for that exact query.
import assert from "node:assert/strict";
import { test } from "node:test";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { AnnouncementsListPage } from "../src/features/announcements/announcements-list-page.tsx";
import { contentListHref } from "../src/features/content/use-content-list-params.ts";
import { listReturnHref } from "../src/features/content/list-return-href.ts";
import { announcementSearchHref } from "../src/features/public/announcements/announcement-search.tsx";
import { AnnouncementList } from "../src/features/public/announcements/announcement-list.tsx";
import { resourceFiltersHref } from "../src/features/public/resources/resource-filters.tsx";
import { ResourceList } from "../src/features/public/resources/resource-list.tsx";
import { ResourcesListPage } from "../src/features/resources/resources-list-page.tsx";
import {
  getAnnouncementsListManagedQueryKey,
  getAnnouncementsListManagedUrl,
  getAnnouncementsListPublicQueryKey,
  getAnnouncementsListPublicUrl,
  getAnnouncementsListVisibleQueryKey,
  getAnnouncementsListVisibleUrl,
} from "../src/lib/api/generated/announcements/announcements.ts";
import { getAuthGetSessionQueryKey } from "../src/lib/api/generated/auth/auth.ts";
import {
  getResourcesListManagedQueryKey,
  getResourcesListManagedUrl,
  getResourcesListPublicQueryKey,
  getResourcesListPublicUrl,
  getResourcesListVisibleQueryKey,
  getResourcesListVisibleUrl,
} from "../src/lib/api/generated/resources/resources.ts";

const ok = (data) => ({ data, status: 200, headers: {} });
const page = (items, { page = 1, hasNext = false, pageSize } = {}) =>
  ok({ items, page, page_size: pageSize, has_next: hasNext });
const person = { id: "p1", display_name: "Content Editor" };

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
}

function signedOut(queryClient) {
  queryClient.setQueryData(getAuthGetSessionQueryKey(), ok({ authenticated: false, session: null, user: null }));
}

function signedIn(queryClient) {
  queryClient.setQueryData(
    getAuthGetSessionQueryKey(),
    ok({ authenticated: true, session: { id: "s1" }, user: { id: "u1", role: "STUDENT", capabilities: [] } }),
  );
}

function render(queryClient, element, router) {
  return renderToStaticMarkup(
    withNextRouter(createElement(QueryClientProvider, { client: queryClient }, element), router),
  );
}

// The query keys the rendered list actually asked for.
function requestedKeys(queryClient, url) {
  return queryClient
    .getQueryCache()
    .findAll({ queryKey: [url] })
    .map((query) => query.queryKey[1]);
}

const hrefs = (html) => [...html.matchAll(/href="([^"]*)"/g)].map((match) => match[1].replaceAll("&amp;", "&"));

const announcement = (id, title) => ({
  id,
  title,
  body_markdown: `${title} body`,
  published_at: "2026-10-01T02:00:00Z",
  expires_at: null,
  is_pinned: false,
  audience: "PUBLIC",
});
const resource = (id, title) => ({
  id,
  title,
  body_markdown: `${title} body`,
  published_at: "2026-10-01T02:00:00Z",
  kind: "ARTICLE",
  category: "MENTAL_HEALTH",
  audience: "PUBLIC",
  external_url: null,
  has_file: false,
});

// Generated client: search reaches both the request and the query identity.

test("search is serialized into every Announcement and Resource list request", () => {
  const builders = [
    getAnnouncementsListPublicUrl,
    getAnnouncementsListVisibleUrl,
    getAnnouncementsListManagedUrl,
    getResourcesListPublicUrl,
    getResourcesListVisibleUrl,
    getResourcesListManagedUrl,
  ];
  for (const build of builders) {
    const url = new URL(build({ search: "stress care", page: 2, page_size: 10 }), "http://compass.test");
    assert.equal(url.searchParams.get("search"), "stress care", build.name);
    assert.equal(url.searchParams.get("page"), "2", build.name);
  }
});

test("different search terms are different queries for every list", () => {
  const keys = [
    getAnnouncementsListPublicQueryKey,
    getAnnouncementsListVisibleQueryKey,
    getAnnouncementsListManagedQueryKey,
    getResourcesListPublicQueryKey,
    getResourcesListVisibleQueryKey,
    getResourcesListManagedQueryKey,
  ];
  const queryClient = client();
  for (const key of keys) {
    const unfiltered = queryClient.getQueryCache().build(queryClient, { queryKey: key({ page: 1, page_size: 10 }) });
    const searched = queryClient.getQueryCache().build(queryClient, { queryKey: key({ page: 1, page_size: 10, search: "wellness" }) });
    const other = queryClient.getQueryCache().build(queryClient, { queryKey: key({ page: 1, page_size: 10, search: "career" }) });
    assert.notEqual(unfiltered.queryHash, searched.queryHash, key.name);
    assert.notEqual(searched.queryHash, other.queryHash, key.name);
  }
});

// Form → canonical URL.

test("public searches write a trimmed canonical URL without a page", () => {
  assert.equal(announcementSearchHref("  wellness  "), "/announcements?search=wellness");
  assert.equal(announcementSearchHref("   "), "/announcements");
  assert.equal(
    resourceFiltersHref({ search: " stress ", category: "MENTAL_HEALTH", kind: "ARTICLE" }),
    "/resources?search=stress&category=MENTAL_HEALTH&kind=ARTICLE",
  );
  assert.equal(resourceFiltersHref({ search: "", category: "CAREER", kind: "" }), "/resources?category=CAREER");
  assert.equal(resourceFiltersHref({ search: " ", category: "", kind: "" }), "/resources");
});

test("managed list changes keep the other filters, reset the page, and clear completely", () => {
  const current = new URLSearchParams("search=orientation&status=PUBLISHED&audience=STUDENTS&page=3");
  assert.equal(
    contentListHref("/portal/announcements", current, { search: "enrollment", status: "PUBLISHED", audience: "STUDENTS" }),
    "/portal/announcements?search=enrollment&status=PUBLISHED&audience=STUDENTS",
  );
  assert.equal(
    contentListHref("/portal/announcements", current, { status: "DRAFT" }),
    "/portal/announcements?search=orientation&status=DRAFT&audience=STUDENTS",
  );
  assert.equal(
    contentListHref("/portal/announcements", current, { page: "4" }, false),
    "/portal/announcements?search=orientation&status=PUBLISHED&audience=STUDENTS&page=4",
  );
  assert.equal(
    contentListHref("/portal/announcements", current, { search: null, status: null, audience: null }),
    "/portal/announcements",
  );
});

test("returning from a record keeps only the list's own context", () => {
  const values = new URLSearchParams("search=career&category=CAREER&page=2&other=x");
  assert.equal(
    listReturnHref("/resources", values, ["search", "category", "kind", "page"]),
    "/resources?search=career&category=CAREER&page=2",
  );
});

// Public Announcements.

test("signed-out Announcement search asks the public list for the term and keeps it in links", () => {
  const queryClient = client();
  signedOut(queryClient);
  queryClient.setQueryData(
    getAnnouncementsListPublicQueryKey({ page: 2, page_size: 10, search: "wellness" }),
    page([announcement("a1", "Wellness week")], { page: 2, hasNext: true, pageSize: 10 }),
  );

  const html = render(queryClient, createElement(AnnouncementList, { mode: "index", page: 2, search: "wellness" }));

  assert.deepEqual(requestedKeys(queryClient, "/api/v1/public/announcements"), [{ page: 2, page_size: 10, search: "wellness" }]);
  assert.match(html, /Wellness week/);
  const links = hrefs(html);
  assert.ok(links.includes("/announcements/a1?search=wellness&page=2"), "detail keeps search and page");
  assert.ok(links.includes("/announcements?search=wellness&page=1"), "previous page keeps search");
  assert.ok(links.includes("/announcements?search=wellness&page=3"), "next page keeps search");
  assert.ok(links.includes("/announcements"), "clear search returns to the unfiltered list");
});

test("signed-in Announcement search asks the visible list, not the public one", () => {
  const queryClient = client();
  signedIn(queryClient);
  queryClient.setQueryData(
    getAnnouncementsListVisibleQueryKey({ page: 1, page_size: 10, search: "enrollment" }),
    page([announcement("a2", "Student enrollment reminder")], { pageSize: 10 }),
  );

  const html = render(queryClient, createElement(AnnouncementList, { mode: "index", page: 1, search: "enrollment" }));

  assert.deepEqual(requestedKeys(queryClient, "/api/v1/announcements"), [{ page: 1, page_size: 10, search: "enrollment" }]);
  assert.match(html, /Student enrollment reminder/);
});

test("an Announcement search with no matches says so, not that nothing exists", () => {
  const queryClient = client();
  signedOut(queryClient);
  queryClient.setQueryData(
    getAnnouncementsListPublicQueryKey({ page: 1, page_size: 10, search: "zzz" }),
    page([], { pageSize: 10 }),
  );

  const html = render(queryClient, createElement(AnnouncementList, { mode: "index", page: 1, search: "zzz" }));

  assert.match(html, /No announcements match this search\./);
  assert.doesNotMatch(html, /are available right now/);
});

// Public Resources.

test("signed-out Resource search sends search, category, and type together and keeps them in links", () => {
  const queryClient = client();
  signedOut(queryClient);
  const params = { category: "MENTAL_HEALTH", kind: "ARTICLE", search: "stress", page: 2, page_size: 9 };
  queryClient.setQueryData(getResourcesListPublicQueryKey(params), page([resource("r1", "Managing stress")], { page: 2, hasNext: true, pageSize: 9 }));

  const html = render(
    queryClient,
    createElement(ResourceList, { mode: "index", page: 2, search: "stress", category: "MENTAL_HEALTH", kind: "ARTICLE" }),
  );

  assert.deepEqual(requestedKeys(queryClient, "/api/v1/public/resources"), [params]);
  assert.match(html, /Managing stress/);
  const links = hrefs(html);
  assert.ok(links.includes("/resources/r1?search=stress&category=MENTAL_HEALTH&kind=ARTICLE&page=2"));
  assert.ok(links.includes("/resources?search=stress&category=MENTAL_HEALTH&kind=ARTICLE&page=3"));
  assert.ok(links.includes("/resources"), "clear filters returns to the unfiltered list");
});

test("signed-in Resource search uses the visible list with the same criteria", () => {
  const queryClient = client();
  signedIn(queryClient);
  const params = { category: "CAREER", kind: undefined, search: "career", page: 1, page_size: 9 };
  queryClient.setQueryData(getResourcesListVisibleQueryKey(params), page([resource("r2", "Career planning")], { pageSize: 9 }));

  const html = render(queryClient, createElement(ResourceList, { mode: "index", page: 1, search: "career", category: "CAREER" }));

  const [key] = requestedKeys(queryClient, "/api/v1/resources");
  assert.equal(key.search, "career");
  assert.equal(key.category, "CAREER");
  assert.match(html, /Career planning/);
});

test("a Resource search with filters and no matches names both", () => {
  const queryClient = client();
  signedOut(queryClient);
  queryClient.setQueryData(
    getResourcesListPublicQueryKey({ category: "MENTAL_HEALTH", kind: "ARTICLE", search: "zzz", page: 1, page_size: 9 }),
    page([], { pageSize: 9 }),
  );

  const html = render(
    queryClient,
    createElement(ResourceList, { mode: "index", page: 1, search: "zzz", category: "MENTAL_HEALTH", kind: "ARTICLE" }),
  );

  assert.match(html, /No resources match this search and the selected filters\./);
});

// Managed Announcements and Resources read their criteria from the URL.

const managedAnnouncement = {
  ...announcement("m1", "Orientation schedule"),
  audience: "STUDENTS",
  status: "PUBLISHED",
  created_at: "2026-09-30T02:00:00Z",
  updated_at: "2026-10-01T02:00:00Z",
  created_by: person,
  updated_by: person,
  published_by: person,
};

test("managed Announcement search composes with status and audience and keeps them across pages", () => {
  const queryClient = client();
  const params = { status: "PUBLISHED", audience: "STUDENTS", search: "orientation", page: 2, page_size: 20 };
  queryClient.setQueryData(getAnnouncementsListManagedQueryKey(params), page([managedAnnouncement], { page: 2, pageSize: 20 }));

  const html = render(queryClient, createElement(AnnouncementsListPage), {
    pathname: "/portal/announcements",
    search: "search=orientation&status=PUBLISHED&audience=STUDENTS&page=2",
  });

  assert.deepEqual(requestedKeys(queryClient, "/api/v1/announcements/management"), [params]);
  assert.match(html, /Orientation schedule/);
  assert.ok(hrefs(html).includes("/portal/announcements/m1?search=orientation&status=PUBLISHED&audience=STUDENTS&page=2"));
  // The search field and the folded filters start from the applied values.
  assert.match(html, /name="search"[^>]*value="orientation"|value="orientation"[^>]*name="search"/);
});

test("managed Announcement search with no matches says so", () => {
  const queryClient = client();
  queryClient.setQueryData(
    getAnnouncementsListManagedQueryKey({ status: "DRAFT", search: "zzz", page: 1, page_size: 20 }),
    page([], { pageSize: 20 }),
  );

  const html = render(queryClient, createElement(AnnouncementsListPage), {
    pathname: "/portal/announcements",
    search: "search=zzz&status=DRAFT",
  });

  assert.match(html, /No Announcements match this search and the selected filters\./);
});

test("managed Resource search composes with every structured filter, including folded ones", () => {
  const queryClient = client();
  const params = {
    status: "PUBLISHED",
    audience: "STUDENTS",
    category: "MENTAL_HEALTH",
    kind: "ARTICLE",
    search: "stress",
    page: 1,
    page_size: 20,
  };
  queryClient.setQueryData(
    getResourcesListManagedQueryKey(params),
    page(
      [{
        ...resource("mr1", "Stress workbook"),
        audience: "STUDENTS",
        status: "PUBLISHED",
        display_order: 1,
        content_type: null,
        original_filename: null,
        size_bytes: 0,
        created_at: "2026-09-30T02:00:00Z",
        updated_at: "2026-10-01T02:00:00Z",
        created_by: person,
        updated_by: person,
        published_by: person,
      }],
      { pageSize: 20 },
    ),
  );

  const html = render(queryClient, createElement(ResourcesListPage), {
    pathname: "/portal/resources",
    search: "search=stress&status=PUBLISHED&audience=STUDENTS&category=MENTAL_HEALTH&kind=ARTICLE",
  });

  assert.deepEqual(requestedKeys(queryClient, "/api/v1/resources/management"), [params]);
  assert.match(html, /Stress workbook/);
  assert.ok(hrefs(html).includes("/portal/resources/mr1?search=stress&status=PUBLISHED&audience=STUDENTS&category=MENTAL_HEALTH&kind=ARTICLE"));
  // Folded filters stay in the form with their applied values, so the next search keeps them.
  for (const [name, value] of [["status", "PUBLISHED"], ["audience", "STUDENTS"], ["category", "MENTAL_HEALTH"], ["kind", "ARTICLE"]]) {
    const select = html.match(new RegExp(`<select[^>]*name="${name}"[^>]*>([\\s\\S]*?)</select>`));
    assert.ok(select, `${name} is in the form`);
    assert.match(select[1], new RegExp(`<option value="${value}" selected="">`), `${name} keeps ${value}`);
  }
});

test("a failed search shows the failure instead of earlier unfiltered rows", async () => {
  const { CompassApiError } = await import("../src/lib/api/errors.ts");
  const queryClient = client();
  signedOut(queryClient);
  const query = queryClient.getQueryCache().build(queryClient, {
    queryKey: getAnnouncementsListPublicQueryKey({ page: 1, page_size: 10, search: "wellness" }),
  });
  // The search request failed while rows from an earlier, unfiltered list were still on hand.
  query.setState({
    status: "error",
    data: page([announcement("old", "Unfiltered announcement")], { pageSize: 10 }),
    error: new CompassApiError({ status: 503, body: {}, headers: {}, method: "GET", url: "/api/v1/public/announcements" }),
  });

  const html = render(queryClient, createElement(AnnouncementList, { mode: "index", page: 1, search: "wellness" }));

  assert.match(html, /announcements could not be loaded/i);
  assert.doesNotMatch(html, /Unfiltered announcement/);
});
