// FB-1: actual portal components and transport, synthetic authenticated accounts/APIs only.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
const { check, shown, hidden, noHorizontalOverflow, finish } = await createBrowserHarness(`customer-feedback-identity-${engine}`);
const opportunityId = "bb111111-1111-4111-8111-111111111111";
const responseId = "bb222222-2222-4222-8222-222222222222";
const path = `/portal/feedback/customer-feedback?opportunity=${opportunityId}`;
const responsePath = "/api/v1/feedback/customer-feedback/responses";
const submitPath = "/api/v1/feedback/customer-feedback";
const optional = [
  ["feedback-respondent-name", "respondent_name", "Voluntary Respondent"],
  ["feedback-address", "address", "Voluntary Address 雪"],
  ["feedback-mobile", "mobile_number", "+63 912 345 6789"],
];
const ratingKeys = [
  "personnel_accommodating_rating", "personnel_job_knowledge_rating", "personnel_flexibility_rating",
  "personnel_information_accuracy_rating", "personnel_appearance_rating", "personnel_commitment_delivery_rating",
  "office_location_rating", "office_cleanliness_rating", "office_environment_rating", "office_hours_rating",
  "personnel_availability_rating", "overall_satisfaction_rating",
];
const account = (reviewer = false) => ({
  ...user(reviewer ? "COUNSELOR" : "STUDENT"),
  first_name: "Account", last_name: "Identity",
  capabilities: [reviewer ? "feedback.view_customer_feedback" : "feedback.submit_customer_feedback"],
  designations: reviewer ? ["HEAD_GUIDANCE_COUNSELOR"] : [],
});
const session = (reviewer = false) => ({ user: account(reviewer), session: { id: "fb1-synthetic", expires_at: "2099-01-01T00:00:00Z", is_current: true } });
const opportunity = {
  id: opportunityId, service_kind: "COUNSELING", service_label: "Counseling",
  service_completed_at: "2026-10-14T00:00:00Z", customer_feedback_submitted: false,
  csm_submitted: false, can_submit_customer_feedback: true, can_submit_csm: false,
};
const summary = { id: responseId, submitted_at: "2026-10-15T00:00:00Z", respondent_name: "", services_received: ["COUNSELING"] };
const detail = {
  ...summary, other_service: "", talked_to_guidance_counselor: true, accommodated_by: null,
  office_visit_count: 2, transaction_duration: "15 minutes", additional_feedback: "Helpful visit.",
  future_service_improvement: "Keep it clear.", course_year: "BSIS / 4", address: "", mobile_number: "",
  form_revision: { id: "f14", family_key: "customer_feedback", official_code: "CNSC-OP-GTA-01F14", official_revision: "0", internal_schema_version: 1 },
  ...Object.fromEntries(ratingKeys.map((key) => [key, 5])),
};
const base = (reviewer = false) => ({
  "/api/v1/auth/session": session(reviewer),
  // A populated profile must never be requested for composition.
  "/api/v1/me/profile": { full_name: "Account Identity", current_address: "Account Current Address", permanent_address: "Account Permanent Address", contact_number: "Account Phone" },
  [`/api/v1/feedback/opportunities/${opportunityId}`]: opportunity,
});
async function blank(page) {
  await shown(page.locator("#feedback-respondent-name"));
  for (const [id] of optional) assert.equal(await page.locator(`#${id}`).inputValue(), "");
}
async function requiredAnswers(page, course = true) {
  await page.getByRole("radio", { name: "Yes", exact: true }).check();
  await page.locator("#feedback-office-visits").fill("2");
  await page.locator("#feedback-transaction-duration").fill("15 minutes");
  for (const key of ratingKeys) await page.locator(`input[name="feedback-rating-${key}"][value="5"]`).check();
  if (course) await page.locator("#feedback-course-year").fill("BSIS / 4");
}
async function review(page) {
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Submit Customer Feedback?" });
  await shown(dialog);
  assert.match(await dialog.innerText(), /will not be able to edit or view this response again/);
  return dialog;
}
const success = ({ reply }) => reply({ id: responseId, submitted_at: summary.submitted_at, submitted: true }, 201);

for (let mask = 0; mask < 8; mask++) {
  const sent = [];
  await check(`optional-combination-${mask}`, path, {
    mobile: mask === 0, overrides: base(),
    handler: async ({ pathname, method, request, reply }) => {
      if (pathname !== submitPath || method !== "POST") return false;
      sent.push({ body: request.postDataJSON(), key: request.headers()["idempotency-key"] });
      await success({ reply }); return true;
    },
  }, async (page) => {
    await blank(page);
    await shown(page.getByText(/Providing your name, address, and mobile number is optional/));
    await shown(page.getByText(/Submission activity is recorded separately for security and accountability/));
    await requiredAnswers(page);
    const expected = {};
    for (const [bit, [id, field, value]] of optional.entries()) {
      if (mask & (1 << bit)) { await page.locator(`#${id}`).fill(`  ${value}  `); expected[field] = value; }
    }
    const dialog = await review(page);
    await noHorizontalOverflow(page);
    await dialog.getByRole("button", { name: "Submit Customer Feedback", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Customer Feedback submitted", exact: true }));
    assert.equal(sent.length, 1);
    assert.ok(sent[0].key);
    assert.equal(sent[0].body.opportunity_id, opportunityId);
    assert.equal(sent[0].body.course_year, "BSIS / 4");
    for (const [, field] of optional) assert.equal(sent[0].body[field], expected[field]);
    await noHorizontalOverflow(page);
  });
}

const clearedSubmissions = [];
await check("clearing-cancel-validation-and-rerender", path, {
  overrides: { ...base(), [`POST ${submitPath}`]: ({ request, reply }) => {
    clearedSubmissions.push(request.postDataJSON());
    return success({ reply });
  } },
}, async (page) => {
  await blank(page);
  for (const [id, , value] of optional) {
    await page.locator(`#${id}`).fill(value);
    await page.locator(`#${id}`).fill("");
  }
  await requiredAnswers(page, false);
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  assert.equal(await page.locator("#feedback-course-year").evaluate((el) => el.validity.valueMissing), true);
  assert.equal(await page.getByRole("alertdialog").count(), 0);
  await blank(page);
  await page.locator("#feedback-course-year").fill("BSIS / 4");
  const dialog = await review(page);
  await dialog.getByRole("button", { name: "Review response", exact: true }).click();
  await hidden(dialog);
  await blank(page);
  await page.locator("#feedback-additional").fill("Triggers rerender");
  await blank(page);
  for (const [id] of optional) await page.locator(`#${id}`).fill("   ");
  const again = await review(page);
  await again.getByRole("button", { name: "Submit Customer Feedback", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Customer Feedback submitted", exact: true }));
  assert.equal(clearedSubmissions.length, 1);
  for (const [, field] of optional) assert.equal(clearedSubmissions[0][field], undefined);
});

await check("server-validation-keeps-voluntary-input-and-cleared-name", path, {
  overrides: { ...base(), [`POST ${submitPath}`]: ({ reply }) => reply({ error: { code: "invalid_feedback_request" } }, 422) },
}, async (page) => {
  await blank(page); await requiredAnswers(page);
  await page.locator("#feedback-respondent-name").fill("Typed then cleared");
  await page.locator("#feedback-respondent-name").fill("");
  await page.locator("#feedback-address").fill("Voluntary Address");
  const dialog = await review(page);
  await dialog.getByRole("button", { name: "Submit Customer Feedback", exact: true }).click();
  await shown(dialog.getByRole("alert"));
  await dialog.getByRole("button", { name: "Review response", exact: true }).click();
  await hidden(dialog);
  assert.equal(await page.locator("#feedback-respondent-name").inputValue(), "");
  assert.equal(await page.locator("#feedback-address").inputValue(), "Voluntary Address");
  assert.equal(await page.locator("#feedback-mobile").inputValue(), "");
});

for (const provided of [false, true]) {
  const sent = [];
  await check(`uncertain-retry-stable-${provided}`, path, {
    overrides: base(), handler: async ({ pathname, method, request, reply }) => {
      if (pathname !== submitPath || method !== "POST") return false;
      sent.push({ body: request.postData(), key: request.headers()["idempotency-key"] });
      if (sent.length === 1) await reply({ error: { code: "idempotency_unavailable" } }, 503);
      else await success({ reply });
      return true;
    },
  }, async (page) => {
    await blank(page); await requiredAnswers(page);
    if (provided) await page.locator("#feedback-mobile").fill(optional[2][2]);
    const dialog = await review(page);
    await dialog.getByRole("button", { name: "Submit Customer Feedback", exact: true }).click();
    await shown(page.getByText("Submission result not confirmed", { exact: true }));
    for (const [id] of optional) assert.equal(await page.locator(`#${id}`).isDisabled(), true);
    await page.getByRole("button", { name: "Retry same submission", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Customer Feedback submitted", exact: true }));
    assert.equal(sent.length, 2); assert.deepEqual(sent[1], sent[0]);
    const body = JSON.parse(sent[0].body);
    assert.equal(body.respondent_name, undefined); assert.equal(body.address, undefined);
    assert.equal(body.mobile_number, provided ? optional[2][2] : undefined);
  });
}

for (const named of [false, true]) {
  const row = { ...summary, respondent_name: named ? "Voluntary Respondent" : "" };
  const record = { ...detail, ...row, address: named ? "Voluntary Address" : "", mobile_number: named ? "+63 912 345 6789" : "" };
  await check(`reviewer-list-detail-${named}`, "/portal/feedback/customer-feedback/responses", {
    mobile: !named, overrides: {
      ...base(true), [responsePath]: { items: [row], page: 1, page_size: 25, has_next: false, ordering: "NEWEST_SUBMITTED", filter_options: { form_revisions: [] } },
      [`${responsePath}/${responseId}`]: record,
    },
  }, async (page) => {
    const link = page.getByRole("link", { name: named ? row.respondent_name : "Name not provided", exact: true });
    await shown(link); assert.match(await link.getAttribute("href"), new RegExp(responseId));
    await shown(page.getByRole("cell", { name: "Counseling", exact: true }));
    await link.click();
    await shown(page.getByRole("heading", { level: 1, name: named ? row.respondent_name : "Customer Feedback response", exact: true }));
    for (const [label, value] of [["Name", row.respondent_name], ["Address", record.address], ["Mobile Number", record.mobile_number]]) {
      const field = page.locator("dl > div").filter({ has: page.locator("dt", { hasText: new RegExp(`^${label}$`) }) });
      assert.equal(await field.locator("dd").innerText(), value || "Not provided");
    }
    await shown(page.getByText("Helpful visit.", { exact: true }));
    await shown(page.getByText("CNSC-OP-GTA-01F14", { exact: false }));
    await noHorizontalOverflow(page);
  });
}

await finish();
