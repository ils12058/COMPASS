import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import {
  calculateMyWorkBacklogCount,
  formatBadgeDisplay,
  getNavigationBadge,
} from "../src/features/portal/components/portal-navigation-attention.ts";
import { PortalNavigation } from "../src/features/portal/components/portal-navigation.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { getGuidanceOperationsGetQueryKey } from "../src/lib/api/generated/guidance-operations/guidance-operations.ts";
import { getGuidanceMessagesGetUnreadCountQueryKey } from "../src/lib/api/generated/guidance-messages/guidance-messages.ts";
import { messagesAccount, sessionFor } from "./support/guidance-messages-fixtures.mjs";

test("calculateMyWorkBacklogCount accurately sums authorized backlog metrics", () => {
  assert.equal(calculateMyWorkBacklogCount(null), null);
  assert.equal(calculateMyWorkBacklogCount(undefined), null);

  assert.equal(
    calculateMyWorkBacklogCount({
      guidance_messages: { count: 2, oldest_waiting_since: "2026-10-10T00:00:00Z" },
      routine_evaluations: { count: 1, oldest_waiting_since: "2026-10-10T00:00:00Z" },
      good_moral_preparation: { count: 0, oldest_waiting_since: null },
      good_moral_issuance: { count: 3, oldest_waiting_since: "2026-10-10T00:00:00Z" },
      call_slips_due: { count: 4, oldest_due_at: "2026-10-10T00:00:00Z" },
    }),
    10,
  );

  // Ineligible / null sources are safely ignored without treating them as zero
  assert.equal(
    calculateMyWorkBacklogCount({
      guidance_messages: { count: 0, oldest_waiting_since: null },
      routine_evaluations: null,
      good_moral_preparation: { count: 0, oldest_waiting_since: null },
      good_moral_issuance: null,
      call_slips_due: null,
    }),
    0,
  );
});

test("formatBadgeDisplay handles 1..99 and 99+ formatting", () => {
  assert.equal(formatBadgeDisplay(1), "1");
  assert.equal(formatBadgeDisplay(42), "42");
  assert.equal(formatBadgeDisplay(99), "99");
  assert.equal(formatBadgeDisplay(100), "99+");
  assert.equal(formatBadgeDisplay(999), "99+");
});

test("getNavigationBadge returns verified semantics for My Work and Messages only", () => {
  // My work singular and plural
  const singleWork = getNavigationBadge("/portal/work", { myWork: 1, messages: null });
  assert.deepEqual(singleWork, {
    count: 1,
    display: "1",
    ariaDescription: "1 item requiring attention",
  });

  const multiWork = getNavigationBadge("/portal/work", { myWork: 5, messages: null });
  assert.deepEqual(multiWork, {
    count: 5,
    display: "5",
    ariaDescription: "5 items requiring attention",
  });

  const overflowWork = getNavigationBadge("/portal/work", { myWork: 105, messages: null });
  assert.deepEqual(overflowWork, {
    count: 105,
    display: "99+",
    ariaDescription: "105 items requiring attention",
  });

  // Zero and null do not return a badge
  assert.equal(getNavigationBadge("/portal/work", { myWork: 0, messages: null }), null);
  assert.equal(getNavigationBadge("/portal/work", { myWork: null, messages: null }), null);

  // Messages singular and plural
  const singleMsg = getNavigationBadge("/portal/messages", { myWork: null, messages: 1 });
  assert.deepEqual(singleMsg, {
    count: 1,
    display: "1",
    ariaDescription: "1 unread conversation",
  });

  const multiMsg = getNavigationBadge("/portal/messages", { myWork: null, messages: 3 });
  assert.deepEqual(multiMsg, {
    count: 3,
    display: "3",
    ariaDescription: "3 unread conversations",
  });

  const overflowMsg = getNavigationBadge("/portal/messages", { myWork: null, messages: 200 });
  assert.deepEqual(overflowMsg, {
    count: 200,
    display: "99+",
    ariaDescription: "200 unread conversations",
  });

  assert.equal(getNavigationBadge("/portal/messages", { myWork: null, messages: 0 }), null);
  assert.equal(getNavigationBadge("/portal/messages", { myWork: null, messages: null }), null);

  // Other destinations have no badges (appointments omitted per Section 5)
  assert.equal(getNavigationBadge("/portal", { myWork: 10, messages: 10 }), null);
  assert.equal(getNavigationBadge("/portal/appointments", { myWork: 10, messages: 10 }), null);
  assert.equal(getNavigationBadge("/portal/counseling", { myWork: 10, messages: 10 }), null);
});

function renderNav({ role = "COUNSELOR", expanded = true, workBacklog, unreadCount }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  if (workBacklog !== undefined) {
    client.setQueryData(getGuidanceOperationsGetQueryKey(), {
      data: {
        generated_at: "2026-10-10T00:00:00Z",
        backlog: workBacklog,
        schedule: { upcoming_self_appointments_count: null, upcoming_managed_appointments_count: null, active_call_slips_count: null },
      },
      status: 200,
      headers: {},
    });
  }
  if (unreadCount !== undefined) {
    client.setQueryData(getGuidanceMessagesGetUnreadCountQueryKey(), {
      data: { unread_conversations_count: unreadCount },
      status: 200,
      headers: {},
    });
  }

  const html = renderToStaticMarkup(
    h(
      QueryClientProvider,
      { client },
      h(
        PortalSessionProvider,
        { value: sessionFor(messagesAccount(role)) },
        h(UnsavedChangesProvider, null, h(PortalNavigation, { expanded })),
      ),
    ),
  );
  client.clear();
  return html;
}

test("PortalNavigation renders badges and accessible names in expanded desktop sidebar", () => {
  const html = renderNav({
    role: "COUNSELOR",
    expanded: true,
    workBacklog: {
      guidance_messages: { count: 2, oldest_waiting_since: "2026-10-10T00:00:00Z" },
      routine_evaluations: { count: 3, oldest_waiting_since: "2026-10-10T00:00:00Z" },
      good_moral_preparation: null,
      good_moral_issuance: { count: 0, oldest_waiting_since: null },
      call_slips_due: null,
    },
    unreadCount: 4,
  });

  // My Work: 2 + 3 = 5
  assert.match(html, /aria-label="My work, 5 items requiring attention"/);
  assert.match(html, /data-testid="nav-badge-expanded"[^>]*>5<\/span>/);

  // Messages: 4 unread conversations
  assert.match(html, /aria-label="Messages, 4 unread conversations"/);
  assert.match(html, /data-testid="nav-badge-expanded"[^>]*>4<\/span>/);

  // Appointments has NO badge or attention aria-label
  assert.ok(!html.includes('Appointments, '));
});

test("PortalNavigation renders collapsed icon rail badge with pointer-events-none and accessible label", () => {
  const html = renderNav({
    role: "COUNSELOR",
    expanded: false,
    workBacklog: {
      guidance_messages: { count: 1, oldest_waiting_since: "2026-10-10T00:00:00Z" },
      routine_evaluations: null,
      good_moral_preparation: null,
      good_moral_issuance: null,
      call_slips_due: null,
    },
    unreadCount: 1,
  });

  // My work collapsed badge
  assert.match(html, /aria-label="My work, 1 item requiring attention"/);
  assert.match(html, /data-testid="nav-badge-collapsed"[^>]*>1<\/span>/);

  // Messages collapsed badge
  assert.match(html, /aria-label="Messages, 1 unread conversation"/);
  assert.match(html, /data-testid="nav-badge-collapsed"[^>]*>1<\/span>/);
});

test("PortalNavigation does not render badge for confirmed zero or unavailable counts", () => {
  const html = renderNav({
    role: "COUNSELOR",
    expanded: true,
    workBacklog: {
      guidance_messages: { count: 0, oldest_waiting_since: null },
      routine_evaluations: { count: 0, oldest_waiting_since: null },
      good_moral_preparation: null,
      good_moral_issuance: { count: 0, oldest_waiting_since: null },
      call_slips_due: null,
    },
    unreadCount: 0,
  });

  assert.ok(!html.includes("nav-badge-expanded"));
  assert.ok(!html.includes("nav-badge-collapsed"));
  assert.ok(!html.includes("requiring attention"));
  assert.ok(!html.includes("unread conversation"));
});

test("Student role sees Messages badge but no My work workspace", () => {
  const html = renderNav({
    role: "STUDENT",
    expanded: true,
    unreadCount: 2,
  });

  assert.ok(!html.includes('href="/portal/work"'));
  assert.match(html, /aria-label="Messages, 2 unread conversations"/);
  assert.match(html, /data-testid="nav-badge-expanded"[^>]*>2<\/span>/);
});
