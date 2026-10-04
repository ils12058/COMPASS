import assert from "node:assert/strict";
import { test } from "node:test";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { Dialog, DialogContent } from "../src/components/ui/dialog.tsx";
import {
  ACKNOWLEDGMENT_HELP,
  nextPendingNotice,
  PENDING_NOTICE_PARAMS,
} from "../src/features/account/privacy/privacy-acknowledgment.ts";
import { PrivacyNoticePrompt, promptSuppressedOn } from "../src/features/account/privacy/privacy-notice-prompt.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { draftConflict, draftConflictMessages } from "../src/features/privacy-governance/notices/draft-conflict.ts";
import { privacyErrorMessage } from "../src/features/privacy-governance/privacy-governance-errors.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import {
  getPrivacyGovernanceListMyNoticesQueryKey,
  getPrivacyGovernanceListMyNoticesUrl,
} from "../src/lib/api/generated/privacy-governance/privacy-governance.ts";

const notice = (overrides = {}) => ({
  acknowledged: false,
  acknowledged_at: null,
  audiences: ["STUDENT"],
  body: "Notice text as written by the Data Protection Officer.",
  code: "PN-1",
  effective_on: "2026-09-01",
  name: "Student Privacy Notice",
  notice_id: "n1",
  requires_acknowledgment: true,
  revision_id: "r1",
  revision_number: 2,
  summary: "How COMPASS handles Student records.",
  title: "Student Privacy Notice",
  ...overrides,
});

test("the portal asks the server for the next pending notice directly, not page 1 of history", () => {
  const url = new URL(getPrivacyGovernanceListMyNoticesUrl(PENDING_NOTICE_PARAMS), "http://compass.test");
  assert.equal(url.searchParams.get("pending_acknowledgment"), "true");
  assert.equal(url.searchParams.get("page_size"), "1");
  // A different query from the Account › Privacy history list, so neither overwrites the other.
  assert.notDeepEqual(
    getPrivacyGovernanceListMyNoticesQueryKey(PENDING_NOTICE_PARAMS),
    getPrivacyGovernanceListMyNoticesQueryKey({ page: 1, page_size: 20 }),
  );
});

test("only a notice that still asks for acknowledgment is offered", () => {
  assert.equal(nextPendingNotice([notice()])?.revision_id, "r1");
  assert.equal(nextPendingNotice([notice({ acknowledged: true, acknowledged_at: "2026-09-02T00:00:00Z" })]), undefined);
  assert.equal(nextPendingNotice([notice({ requires_acknowledgment: false })]), undefined);
  assert.equal(nextPendingNotice([]), undefined);
  assert.equal(nextPendingNotice(undefined), undefined);
});

test("the prompt stays out of the Privacy page and live E-Counseling sessions", () => {
  assert.equal(promptSuppressedOn("/portal/account/privacy"), true);
  assert.equal(promptSuppressedOn("/portal/e-counseling/60000000-0000-4000-8000-000000000001"), true);
  assert.equal(promptSuppressedOn("/portal/e-counseling"), false);
  assert.equal(promptSuppressedOn("/portal"), false);
  assert.equal(promptSuppressedOn("/portal/appointments"), false);
});

function renderPrompt(items, pathname = "/portal") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(getPrivacyGovernanceListMyNoticesQueryKey(PENDING_NOTICE_PARAMS), {
    data: { items, page: 1, page_size: 1, has_next: false },
    status: 200,
    headers: {},
  });
  const wrap = (element) =>
    withNextRouter(
      createElement(QueryClientProvider, { client }, createElement(UnsavedChangesProvider, null, element)),
      { pathname },
    );
  let dialog;
  function Probe() {
    dialog = PrivacyNoticePrompt();
    return null;
  }
  renderToStaticMarkup(wrap(createElement(Probe)));
  if (!dialog) return { dialog };
  const content = [dialog.props.children].flat().find((child) => child?.type === DialogContent);
  let portal;
  function Portal() {
    portal = DialogContent.render(content.props, null);
    return null;
  }
  renderToStaticMarkup(createElement(Portal));
  const rendered = [portal.props.children].flat().at(-1);
  return { dialog, html: renderToStaticMarkup(wrap(createElement(Dialog, { open: true }, rendered))) };
}

test("a pending notice opens one prompt with its text, the acknowledgment meaning, and a way out", () => {
  const { dialog, html } = renderPrompt([notice()]);

  assert.equal(dialog.props.open, true);
  assert.match(html, /Privacy notice update/);
  assert.match(html, /Student Privacy Notice/);
  assert.match(html, /Effective/);
  assert.match(html, /Notice text as written by the Data Protection Officer\./);
  assert.ok(html.includes(ACKNOWLEDGMENT_HELP.replace(/'/g, "&#x27;")));
  assert.match(html, /It is not consent to all data processing\./);
  assert.match(html, />Acknowledge notice</);
  // Not blocking: it can be put off, and the full list stays in Account › Privacy.
  assert.match(html, />Not now</);
  assert.match(html, /href="\/portal\/account\/privacy"/);
});

test("no prompt for an acknowledged notice, and none on the Privacy page itself", () => {
  assert.equal(renderPrompt([notice({ acknowledged: true })]).dialog, null);
  assert.equal(renderPrompt([notice()], "/portal/account/privacy").dialog.props.open, false);
});

test("a draft editor tells a save elsewhere apart from publication and retirement", () => {
  const base = "2026-10-04T02:00:00.000Z";
  assert.equal(draftConflict({ baseUpdatedAt: base, latest: { status: "DRAFT", updated_at: base }, noticeActive: true }), null);
  assert.equal(
    draftConflict({ baseUpdatedAt: base, latest: { status: "DRAFT", updated_at: "2026-10-04T02:05:00.000Z" }, noticeActive: true }),
    "saved-elsewhere",
  );
  assert.equal(draftConflict({ baseUpdatedAt: base, latest: { status: "PUBLISHED", updated_at: base }, noticeActive: true }), "no-longer-draft");
  assert.equal(draftConflict({ baseUpdatedAt: base, latest: { status: "DRAFT", updated_at: base }, noticeActive: false }), "retired");
  for (const message of Object.values(draftConflictMessages)) {
    assert.match(message, /kept here/);
  }
});

test("conflict copy no longer asks for a refresh COMPASS already did", () => {
  const conflict = (code) =>
    new CompassApiError({ status: 409, body: { error: { code, message: code } }, headers: {}, method: "POST", url: "/api/v1/privacy" });
  assert.doesNotMatch(privacyErrorMessage(conflict("privacy_notice_revision_not_current"), "x"), /Refresh/);
  assert.match(privacyErrorMessage(conflict("privacy_notice_revision_changed"), "x"), /Review the latest saved version/);
});
