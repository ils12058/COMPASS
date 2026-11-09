import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { DocumentationReviewPanel } from "../src/features/counseling/documentation-review-panel.tsx";
import { getCounselingAccess } from "../src/features/counseling/counseling-access.ts";
import {
  appointmentDetailHref,
  completeConfirmationDescription,
  counselingMismatchNotice,
  counselingReconciliationNotice,
  documentationReviewReasonCopy,
  encounterDetailHref,
  reviewHref,
  reviewPageFromParam,
} from "../src/features/counseling/documentation-review.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { getCounselingListDocumentationReviewQueryKey } from "../src/lib/api/generated/counseling/counseling.ts";
import { withNextRouter } from "./support/next-router.mjs";
import { counselor, session } from "./support/cont1a-summary-fixtures.mjs";

const ok = (data) => ({ data, status: 200, headers: { date: new Date().toUTCString() } });
const PATHNAME = "/portal/counseling";
const PAGE_SIZE = 5;

function person(id, displayName, institutionalId = null) {
  return {
    id,
    institutional_id: institutionalId,
    display_name: displayName,
    profile_photo_url: null,
    profile_photo_updated_at: null,
  };
}

function row(reason, { appointmentId, studentId, encounterId = null, status = "COMPLETED" }) {
  return {
    appointment_id: appointmentId,
    reference_code: `APT-REVIEW-${appointmentId}`,
    student: person(studentId, `Student ${studentId}`, `ID-${studentId}`),
    delivery_mode: "IN_PERSON",
    starts_at: "2026-11-05T01:00:00Z",
    ends_at: "2026-11-05T02:00:00Z",
    status,
    reason,
    encounter_id: encounterId,
  };
}

const threeRows = [
  row("MISSING_ENCOUNTER", { appointmentId: "a-missing", studentId: "s-ana" }),
  row("UNCOMPLETED_APPOINTMENT", {
    appointmentId: "a-uncompleted",
    studentId: "s-bea",
    encounterId: "e-bea",
    status: "SCHEDULED",
  }),
  row("LINKED_CONFLICT", { appointmentId: "a-conflict", studentId: "s-cec" }),
];

function renderPanel({ search = "", user = counselor(), seed = () => {} } = {}) {
  // A static render never runs mount effects, so the on-mount refetch decision has to be pinned off:
  // otherwise TanStack optimistically reports a data-less error query as pending and the error branch
  // is unreachable. retryOnMount/refetchOnMount are harness settings, not the panel's.
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, retryOnMount: false, refetchOnMount: false, staleTime: Infinity } },
  });
  const page = reviewPageFromParam(new URLSearchParams(search).get("review_page"));
  const params = { page, page_size: PAGE_SIZE };
  seed(client, getCounselingListDocumentationReviewQueryKey(params));
  const html = renderToStaticMarkup(
    withNextRouter(
      h(
        QueryClientProvider,
        { client },
        h(PortalSessionProvider, { value: session(user) }, h(DocumentationReviewPanel, { access: getCounselingAccess(user) })),
      ),
      { pathname: PATHNAME, search },
    ),
  );
  client.clear();
  return html;
}

const seeded = (client, key, items, { page = 1, hasNext = false } = {}) =>
  client.setQueryData(key, ok({ items, page, page_size: PAGE_SIZE, has_next: hasNext }));

const failure = (status, code) => new CompassApiError({
  status,
  body: { error: { code, message: "server detail" } },
  headers: {},
  method: "GET",
  url: "/api/v1/counseling/documentation-review",
});

test("each review reason says what is missing without assuming attendance", () => {
  assert.deepEqual(documentationReviewReasonCopy.MISSING_ENCOUNTER, {
    label: "Completed without an Encounter",
    message:
      "This Appointment is marked completed, but no Counseling Encounter is recorded. Attendance isn’t assumed; record an Encounter only if Counseling took place.",
  });
  assert.deepEqual(documentationReviewReasonCopy.UNCOMPLETED_APPOINTMENT, {
    label: "Encounter recorded, Appointment not completed",
    message:
      "The Counseling Encounter is already recorded. Completing the Appointment won’t create another Encounter.",
  });
  assert.deepEqual(documentationReviewReasonCopy.LINKED_CONFLICT, {
    label: "Encounter link needs review",
    message: counselingMismatchNotice,
  });
  assert.equal(
    counselingMismatchNotice,
    "A Counseling Encounter is linked to this Appointment but doesn’t match its Counseling details. This needs administrative review and can’t be corrected here.",
  );
  assert.equal(
    counselingReconciliationNotice,
    "This Counseling Encounter is already recorded. Complete the Appointment to reconcile it; this won’t create another Encounter.",
  );
  assert.equal(
    completeConfirmationDescription({ reconciliation: false }),
    "This Appointment will be marked completed and will no longer be scheduled.",
  );
  assert.equal(
    completeConfirmationDescription({ reconciliation: true }),
    "This Appointment will be marked completed. The Counseling Encounter already recorded for it will be kept; no second Encounter will be created.",
  );
});

test("the review page parameter is safe and only moves its own list", () => {
  assert.equal(reviewPageFromParam(null), 1);
  assert.equal(reviewPageFromParam("2"), 2);
  assert.equal(reviewPageFromParam("0"), 1);
  assert.equal(reviewPageFromParam("-3"), 1);
  assert.equal(reviewPageFromParam("two"), 1);
  assert.equal(reviewPageFromParam("9007199254740993"), 1);

  const current = new URLSearchParams("page=3&search=ana&entry_mode=WALK_IN&ordering=LATEST_ENCOUNTER");
  assert.equal(
    reviewHref(PATHNAME, current, 2),
    "/portal/counseling?page=3&search=ana&entry_mode=WALK_IN&ordering=LATEST_ENCOUNTER&review_page=2",
  );
  assert.equal(
    reviewHref(PATHNAME, new URLSearchParams("review_page=2&page=3"), 1),
    "/portal/counseling?page=3",
  );
  assert.equal(reviewHref(PATHNAME, new URLSearchParams(), 1), PATHNAME);
  assert.equal(appointmentDetailHref("a-1"), "/portal/appointments/a-1");
  assert.equal(encounterDetailHref("e-1"), "/portal/counseling/encounters/e-1");
});

test("the panel lists every reason and offers only review links", () => {
  const html = renderPanel({ seed: (client, key) => seeded(client, key, threeRows) });

  assert.match(html, />Needs documentation</);
  assert.match(
    html,
    /These Appointments may still need a Counseling Encounter record\. Being listed doesn&#x27;t mean Counseling took place\./,
  );
  assert.match(html, /3 Appointments/);
  for (const reason of ["MISSING_ENCOUNTER", "UNCOMPLETED_APPOINTMENT", "LINKED_CONFLICT"]) {
    const copy = documentationReviewReasonCopy[reason];
    assert.match(html, new RegExp(`>${copy.label}</`));
    assert.ok(html.includes(copy.message), reason);
  }
  assert.match(html, /Student s-ana/);
  assert.match(html, /ID-s-bea/);
  assert.match(html, /APT-REVIEW-a-missing/);
  assert.match(html, /href="\/portal\/appointments\/a-missing"/);
  assert.match(html, /href="\/portal\/counseling\/encounters\/e-bea"/);
  assert.doesNotMatch(html, /href="\/portal\/counseling\/encounters\/e-"/);

  // Nothing here writes: authoring and completion stay on the surfaces that own them.
  assert.doesNotMatch(html, /Finish counseling|Record encounter|Follow-up|Follow Up/);
  assert.equal((html.match(/Review Appointment/g) ?? []).length, 3);
  assert.equal((html.match(/View encounter/g) ?? []).length, 1);
});

test("a Counselor without Appointment management is given no way to act", () => {
  const viewer = {
    ...counselor(),
    capabilities: counselor().capabilities.filter((code) => code !== "appointments.manage"),
  };
  const html = renderPanel({ user: viewer, seed: (client, key) => seeded(client, key, threeRows) });
  assert.doesNotMatch(html, /Review Appointment/);
  assert.doesNotMatch(html, /\/portal\/appointments\//);
  assert.match(html, /APT-REVIEW-a-missing/);
  assert.match(html, /View encounter/);
});

test("an empty worklist is silent, and a stale page explains itself", () => {
  assert.equal(renderPanel({ seed: (client, key) => seeded(client, key, []) }), "");

  const stranded = renderPanel({
    search: "review_page=2",
    seed: (client, key) => seeded(client, key, [], { page: 2 }),
  });
  assert.match(stranded, /No Appointments on this page need documentation\./);
  assert.match(stranded, /href="\/portal\/counseling"/);
  assert.match(stranded, /Back to the first page/);
});

test("the worklist reports a failure instead of pretending to be empty", () => {
  const failed = renderPanel({
    seed: (client, key) => client.getQueryCache().build(client, { queryKey: key }).setState({
      status: "error",
      fetchStatus: "idle",
      data: undefined,
      error: failure(500, "internal_error"),
    }),
  });
  assert.match(failed, /Couldn&#x27;t load Appointments that need documentation\. Try again\./);
  assert.match(failed, /Retry/);

  const stale = renderPanel({
    seed: (client, key) => client.getQueryCache().build(client, { queryKey: key }).setState({
      status: "error",
      fetchStatus: "idle",
      data: ok({ items: threeRows, page: 1, page_size: PAGE_SIZE, has_next: false }),
      errorUpdatedAt: Date.now(),
      error: failure(500, "internal_error"),
    }),
  });
  assert.match(stale, /Completed without an Encounter/);
  assert.match(stale, /Latest information could not be refreshed|Couldn&#x27;t load/);
});

test("the panel pages its own list without disturbing the encounters", () => {
  const html = renderPanel({
    search: "page=2&search=ana",
    seed: (client, key) => seeded(client, key, threeRows, { page: 2, hasNext: true }),
  });
  assert.match(html, /aria-label="Needs documentation pages"/);
  assert.match(html, /Page 2 · 3 Appointments on this page/);
  assert.match(html, /aria-label="Previous"/);
  assert.match(html, /aria-label="Next"/);
  // The pager is buttons over a query parameter the panel owns; the row links stay plain hrefs.
  assert.doesNotMatch(html, /href="[^"]*review_page/);
  assert.match(html, /href="\/portal\/appointments\/a-missing"/);
});
