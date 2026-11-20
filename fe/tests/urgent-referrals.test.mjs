import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { UrgencyCheckbox, UrgentBadge, UrgentFilter } from "../src/features/referrals/referral-urgency.tsx";
import { filtersToUrl } from "../src/features/referrals/referrals-page.tsx";
import { SubmissionFacts, SubmissionRows } from "../src/features/faculty-referrals/records.tsx";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";
import { presentGoaWork } from "../src/features/portal/home/goa-home-presentation.ts";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";

import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";

const html = (component, props) => renderToStaticMarkup(createElement(component, props));
const record = { id: "referral-1", reference_code: "REF-2026-1", student: { display_name: "Synthetic Student" }, submitted_at: "2026-11-20T02:00:00Z", state: "SUBMITTED", received_at: null, closed_at: null, timing_status: "NOT_PROVIDED", is_urgent: true };

test("Both intake checkboxes name the urgent concern and connect the safety help", () => {
  for (const id of ["faculty-urgent", "gco-urgent"]) {
    const rendered = html(UrgencyCheckbox, { id, checked: true, disabled: true, onChange() {} });
    assert.match(rendered, /type="checkbox"/);
    assert.match(rendered, /name="is_urgent"/);
    assert.ok(rendered.includes(`for="${id}"`));
    assert.ok(rendered.includes(`aria-describedby="${id}-help"`));
    assert.match(rendered, /This concern is urgent/);
    assert.match(rendered, /student needs attention today/);
    assert.match(rendered, /immediate danger/);
    assert.match(rendered, /Guidance and Counseling Office or campus security directly/);
    assert.match(rendered, /COMPASS is not an emergency hotline/);
    assert.match(rendered, /checked=""/);
    assert.match(rendered, /disabled=""/);
  }
});

test("Checkbox and filter pass the user's checked value, including clearing", () => {
  for (const component of [UrgencyCheckbox, UrgentFilter]) {
    let changed;
    const tree = component({ id: "urgent", checked: false, onChange(value) { changed = value; } });
    const children = Array.isArray(tree.props.children) ? tree.props.children : [tree.props.children];
    const input = children.find(child => child?.type === "input") ?? children[0].props.children[0];
    input.props.onChange({ target: { checked: true } });
    assert.equal(changed, true);
    input.props.onChange({ target: { checked: false } });
    assert.equal(changed, false);
  }
});

test("Faculty own lists and detail visibly show the urgent badge", () => {
  assert.equal(html(UrgentBadge, { urgent: false }), "");
  assert.match(html(SubmissionFacts, { item: record }), />Urgent</);
  assert.match(renderToStaticMarkup(createElement(UnsavedChangesProvider, {}, createElement(SubmissionRows, { items: [record] }))), />Urgent</);
  assert.doesNotMatch(html(SubmissionFacts, { item: { ...record, is_urgent: false } }), />Urgent</);
});

test("Urgent filtering preserves list navigation and uses the server parameter", () => {
  assert.match(html(UrgentFilter, { checked: true, onChange() {} }), /Urgent only/);
  const filters = { urgentOnly: true, search: "Synthetic", fromDate: "", toDate: "", formRevisionId: "", includeVoided: false, page: 2 };
  const url = new URL(filtersToUrl(filters), "https://synthetic.invalid");
  assert.equal(url.searchParams.get("is_urgent"), "true");
  assert.equal(url.searchParams.get("page"), "2");
  assert.equal(url.searchParams.get("search"), "Synthetic");
  assert.equal(new URL(filtersToUrl({ ...filters, urgentOnly: false }), url).searchParams.has("is_urgent"), false);
});

test("The queue, Overview and notice open the same authorized staff referral", () => {
  const work = { id: "urgent-referral:referral-1", source_id: record.id, kind: "URGENT_REFERRAL", priority: "TIME_SENSITIVE", due_at: null, waiting_since: record.submitted_at, student: record.student };
  const row = presentWork(work);
  assert.equal(row.title, "Review urgent referral");
  assert.equal(row.href, "/portal/referrals/referral-1");
  assert.deepEqual(presentGoaWork(work, { role: "GUIDANCE_OFFICE_ASSISTANT", capabilities: ["referrals.view", "referrals.manage"] }), row);
  assert.equal(presentGoaWork(work, { role: "GUIDANCE_OFFICE_ASSISTANT", capabilities: ["referrals.view"] }), null);
  assert.equal(notificationDestination({ target_type: "REFERRAL", target_id: record.id }, "staff").href, row.href);
});
