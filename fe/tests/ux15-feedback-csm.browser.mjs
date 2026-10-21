// UX15 Pilot 6: actual Student Feedback forms and transport with synthetic opportunities only.
// Every API request is local and intercepted by the shared browser harness.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
const { check, shown, hidden, noHorizontalOverflow, navigate, finish } = await createBrowserHarness(`ux15-feedback-csm-${engine}`);
const evidenceDir = process.env.COMPASS_UX15_CAPTURE_DIR;
const capturePhase = process.env.COMPASS_UX15_CAPTURE_PHASE ?? "after";
const customerOpportunityId = "bb111111-1111-4111-8111-111111111111";
const csmOpportunityId = "cc111111-1111-4111-8111-111111111111";
const responseId = "dd111111-1111-4111-8111-111111111111";
const customerPath = `/portal/feedback/customer-feedback?opportunity=${customerOpportunityId}`;
const csmPath = `/portal/feedback/csm?opportunity=${csmOpportunityId}`;
const customerRatingKeys = [
  "personnel_accommodating_rating", "personnel_job_knowledge_rating", "personnel_flexibility_rating",
  "personnel_information_accuracy_rating", "personnel_appearance_rating", "personnel_commitment_delivery_rating",
  "office_location_rating", "office_cleanliness_rating", "office_environment_rating", "office_hours_rating",
  "personnel_availability_rating", "overall_satisfaction_rating",
];
const csmRatingKeys = Array.from({ length: 9 }, (_, index) => `sqd${index}`);

const customerOpportunity = (overrides = {}) => ({
  id: customerOpportunityId,
  service_kind: "COUNSELING",
  service_label: "Counseling",
  service_completed_at: "2026-10-14T00:00:00Z",
  customer_feedback_submitted: false,
  csm_submitted: false,
  can_submit_customer_feedback: true,
  can_submit_csm: false,
  ...overrides,
});
const csmOpportunity = (overrides = {}) => ({
  id: csmOpportunityId,
  service_kind: "COUNSELING",
  service_label: "Counseling",
  service_completed_at: "2026-10-14T00:00:00Z",
  customer_feedback_submitted: false,
  csm_submitted: false,
  can_submit_customer_feedback: false,
  can_submit_csm: true,
  ...overrides,
});
const account = (capability) => ({
  ...user("STUDENT"),
  id: "ux15-synthetic-student",
  first_name: "Account",
  last_name: "Identity",
  capabilities: [capability],
});
const session = (capability) => ({
  user: account(capability),
  session: { id: "ux15-synthetic-session", expires_at: "2099-01-01T00:00:00Z", is_current: true },
});
const feedbackOptions = ({ family, device = "desktop", opportunity, unrelated = false } = {}) => {
  const customer = family === "customer";
  const capability = customer ? "feedback.submit_customer_feedback" : "feedback.submit_csm";
  const opportunityId = customer ? customerOpportunityId : csmOpportunityId;
  const opportunityData = opportunity ?? (customer ? customerOpportunity() : csmOpportunity());
  return {
    device,
    overrides: {
      "/api/v1/auth/session": session(capability),
      "/api/v1/me/profile": {
        full_name: "Account Identity",
        current_address: "Account Current Address",
        permanent_address: "Account Permanent Address",
        contact_number: "Account Phone",
      },
      "/api/v1/feedback/opportunities": [opportunityData],
      [`/api/v1/feedback/opportunities/${opportunityId}`]: unrelated
        ? ({ reply }) => reply({ error: { code: "feedback_opportunity_not_found" } }, 404)
        : opportunityData,
    },
  };
};
const successBody = { id: responseId, submitted_at: "2026-10-20T02:30:00Z", submitted: true };

async function capture(page, name) {
  if (!evidenceDir || engine !== "chromium") return;
  await mkdir(evidenceDir, { recursive: true });
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await page.screenshot({ path: join(evidenceDir, `${capturePhase}-${name}.png`), fullPage: false });
}

async function fillCustomerRequired(page, { otherService = false, counselor = "yes" } = {}) {
  if (otherService) {
    await page.getByLabel("Others (please specify)", { exact: true }).check();
    await page.locator("#feedback-other-service").fill("Student leadership consultation");
  }
  await page.locator(`input[name="talked-to-guidance-counselor"][value="${counselor}"]`).check();
  if (counselor === "no") await page.getByLabel("Clerk / Personnel", { exact: true }).check();
  await page.locator("#feedback-office-visits").fill("2");
  await page.locator("#feedback-transaction-duration").fill("15 minutes");
  for (const key of customerRatingKeys) {
    await page.locator(`input[name="feedback-rating-${key}"][value="3"]`).check();
  }
  await page.locator("#feedback-course-year").fill("BSIS / 4");
}

async function fillCsmRequired(page, { cc1 = 1, zeroFirstSqd = false } = {}) {
  await page.locator('input[name="csm-client-type"][value="CITIZEN"]').check();
  await page.locator('input[name="csm-sex"][value="FEMALE"]').check();
  await page.locator("#csm-age").fill("20");
  await page.locator("#csm-region").fill("Region III");
  await page.locator("#csm-service").fill("Counseling");
  await page.locator(`input[name="csm-cc1"][value="${cc1}"]`).check();
  if (cc1 === 4) {
    await shown(page.getByText(/CC2 and CC3 are recorded as Not Applicable/));
  } else {
    await page.locator('input[name="csm-cc2"][value="2"]').check();
    await page.locator('input[name="csm-cc3"][value="3"]').check();
  }
  for (const [index, key] of csmRatingKeys.entries()) {
    await page.locator(`input[name="csm-${key}"][value="${zeroFirstSqd && index === 0 ? 0 : 5}"]`).check();
  }
}

await check("customer desktop context and continuous section navigation", customerPath, feedbackOptions({ family: "customer" }), async (page, fixture) => {
  await shown(page.getByRole("heading", { level: 1, name: "Customer Feedback Form" }));
  await shown(page.getByText("Feedback for Counseling."));
  assert.equal(await page.locator("#feedback-service-counseling").isChecked(), true);
  assert.equal(await page.locator("#feedback-service-counseling").isDisabled(), true);
  assert.equal(await page.locator('input[name^="feedback-rating-"][type="radio"]').count(), 60);
  assert.equal(await page.locator('input[name^="feedback-rating-"]').evaluateAll((nodes) => new Set(nodes.map((node) => node.name)).size), 12);
  await shown(page.getByRole("navigation", { name: "Customer Feedback sections" }));
  await capture(page, "customer-desktop-beginning");
  await page.getByRole("link", { name: "Overall satisfaction", exact: true }).click();
  await shown(page.locator("#feedback-vi-overall-satisfaction"));
  assert.equal(await page.evaluate(() => document.activeElement?.id), "feedback-vi-overall-satisfaction");
  assert.equal(new URL(page.url()).hash, "");
  assert.equal(await page.locator("#feedback-service-counseling").isChecked(), true);
  assert.equal(fixture.requests.some(({ method }) => method === "POST"), false);
  for (const id of ["feedback-respondent-name", "feedback-address", "feedback-mobile"]) {
    assert.equal(await page.locator(`#${id}`).inputValue(), "", `${id} must not be filled from profile data`);
  }
  await page.getByRole("link", { name: "Personnel experience", exact: true }).click();
  await shown(page.locator("#feedback-iv-service-personnel-experience"));
  await capture(page, "customer-desktop-ratings");
  await noHorizontalOverflow(page);
});

await check("customer required validation, conditional answers, confirmation cancel and success", customerPath, feedbackOptions({ family: "customer" }), async (page, fixture) => {
  const sent = [];
  await fixture.context.route("**/api/v1/feedback/customer-feedback", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") return route.fallback();
    sent.push({ body: request.postDataJSON(), key: request.headers()["idempotency-key"] });
    return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(successBody) });
  });
  await shown(page.locator("#feedback-course-year"));
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  assert.equal(await page.getByRole("alertdialog").count(), 0);
  assert.equal(await page.evaluate(() => document.activeElement?.name), "talked-to-guidance-counselor");
  assert.equal(await page.locator('input[name="talked-to-guidance-counselor"]').first().evaluate((input) => input.validity.valueMissing), true);
  await capture(page, "customer-validation-focus");

  await page.locator('input[name="talked-to-guidance-counselor"][value="no"]').check();
  const accommodation = page.getByLabel("Clerk / Personnel", { exact: true });
  await shown(accommodation);
  await accommodation.check();
  await page.locator('input[name="talked-to-guidance-counselor"][value="yes"]').check();
  await hidden(accommodation);
  await page.locator('input[name="talked-to-guidance-counselor"][value="no"]').check();
  await shown(accommodation);
  assert.equal(await accommodation.isChecked(), false, "Inactive conditional answers are cleared when the branch changes");
  await accommodation.check();
  await page.getByLabel("Others (please specify)", { exact: true }).check();
  await shown(page.locator("#feedback-other-service"));
  assert.equal(await page.locator("#feedback-other-service").evaluate((input) => input.required), true);
  await fillCustomerRequired(page, { otherService: true, counselor: "no" });
  // Required inputs are still empty optional identity fields even though a profile fixture exists.
  for (const id of ["feedback-respondent-name", "feedback-address", "feedback-mobile"]) {
    assert.equal(await page.locator(`#${id}`).inputValue(), "");
    assert.equal(await page.locator(`#${id}`).evaluate((input) => input.required), false);
  }
  assert.equal(await page.locator("#feedback-course-year").evaluate((input) => input.required), true);
  await page.locator("#feedback-respondent-name").scrollIntoViewIfNeeded();
  await capture(page, "customer-respondent-information");

  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Submit Customer Feedback?" });
  await shown(dialog);
  assert.match(await dialog.innerText(), /will not be able to edit or view this response again/);
  await capture(page, "customer-confirmation");
  await dialog.getByRole("button", { name: "Review response", exact: true }).click();
  await hidden(dialog);
  assert.equal(sent.length, 0, "Canceling confirmation does not submit");

  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  await shown(page.getByRole("alertdialog", { name: "Submit Customer Feedback?" }));
  await page.getByRole("button", { name: "Submit Customer Feedback", exact: true }).click();
  await shown(page.getByRole("heading", { level: 1, name: "Customer Feedback submitted" }));
  await capture(page, "customer-success");
  assert.equal(sent.length, 1);
  assert.ok(sent[0].key);
  assert.equal(sent[0].body.opportunity_id, customerOpportunityId);
  assert.deepEqual(sent[0].body.services_received, ["COUNSELING", "OTHER"]);
  assert.equal(sent[0].body.other_service, "Student leadership consultation");
  assert.equal(sent[0].body.talked_to_guidance_counselor, false);
  assert.ok(sent[0].body.accommodated_by);
  assert.equal(sent[0].body.office_visit_count, 2);
  assert.equal(sent[0].body.course_year, "BSIS / 4");
  for (const key of customerRatingKeys) assert.equal(sent[0].body[key], 3);
  for (const optionalField of ["respondent_name", "address", "mobile_number"]) assert.equal(sent[0].body[optionalField], undefined);
  assert.match(await page.getByRole("status").innerText(), /Your response was received/);
});

await check("customer uncertain submission retries the identical body and key", customerPath, feedbackOptions({ family: "customer" }), async (page, fixture) => {
  const requests = [];
  let attempts = 0;
  await fixture.context.route("**/api/v1/feedback/customer-feedback", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") return route.fallback();
    requests.push({ body: request.postData(), key: request.headers()["idempotency-key"] });
    attempts += 1;
    if (attempts === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "idempotency_unavailable" } }) });
    return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(successBody) });
  });
  await fillCustomerRequired(page);
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  await page.getByRole("button", { name: "Submit Customer Feedback", exact: true }).click();
  await shown(page.getByText("Submission result not confirmed", { exact: true }));
  await page.getByText("Submission result not confirmed", { exact: true }).scrollIntoViewIfNeeded();
  await capture(page, "customer-uncertain");
  assert.equal(await page.locator("fieldset[disabled]").count(), 1);
  await page.getByRole("button", { name: "Retry same submission", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Customer Feedback submitted", exact: true }));
  assert.equal(requests.length, 2);
  assert.deepEqual(requests[1], requests[0]);
});

await check("customer phone keyboard, touch target, and 768px reflow", customerPath, { ...feedbackOptions({ family: "customer", device: "phone" }), viewport: { width: 390, height: 844 } }, async (page) => {
  await shown(page.getByRole("navigation", { name: "Customer Feedback sections" }));
  await capture(page, "customer-phone-beginning");
  await page.locator("input[name='feedback-rating-personnel_accommodating_rating'][value='5']").focus();
  await page.locator("input[name='feedback-rating-personnel_accommodating_rating'][value='5']").press("ArrowRight");
  assert.equal(await page.locator("input[name='feedback-rating-personnel_accommodating_rating'][value='4']").isChecked(), true);
  const targetHeight = await page.locator("label[for='feedback-rating-personnel_accommodating_rating-1']").evaluate((label) => label.getBoundingClientRect().height);
  assert.ok(targetHeight >= 44, `Radio choice target is ${targetHeight}px high`);
  await page.getByRole("link", { name: "Personnel experience", exact: true }).click();
  await shown(page.locator("#feedback-iv-service-personnel-experience"));
  await capture(page, "customer-phone-ratings");
  await page.setViewportSize({ width: 768, height: 900 });
  const gridColumns = await page.locator('input[name="feedback-rating-personnel_accommodating_rating"]').first().evaluate((input) => getComputedStyle(input.closest("fieldset").querySelector(".grid")).gridTemplateColumns.split(" ").length);
  assert.equal(gridColumns, 2, "At tablet width, long labels retain a two-column choice grid");
  await noHorizontalOverflow(page);
  await page.setViewportSize({ width: 320, height: 640 });
  await noHorizontalOverflow(page);
  await page.addStyleTag({ content: ":root { font-size: 200% !important; }" });
  const formDimensions = await page.locator("form").evaluate((form) => ({ width: form.clientWidth, scrollWidth: form.scrollWidth }));
  assert.ok(formDimensions.scrollWidth <= formDimensions.width + 1, "The modified form reflows at 200% text size");
});

await check("Customer Feedback already-submitted and ineligible opportunities stay unavailable", customerPath, feedbackOptions({
  family: "customer",
  opportunity: customerOpportunity({ customer_feedback_submitted: true }),
}), async (page) => {
  await shown(page.getByRole("heading", { name: "Customer Feedback submitted", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Review and submit", exact: true }).count(), 0);
});

await check("customer ineligible opportunity stays unavailable", customerPath, feedbackOptions({
  family: "customer",
  opportunity: customerOpportunity({ can_submit_customer_feedback: false }),
}), async (page) => {
  await shown(page.getByRole("heading", { name: "Customer Feedback unavailable", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Review and submit", exact: true }).count(), 0);
});

await check("customer unsaved navigation guard keeps the response in place", customerPath, feedbackOptions({ family: "customer" }), async (page) => {
  const prompts = [];
  page.on("dialog", async (dialog) => {
    prompts.push(dialog.message());
    await dialog.dismiss();
  });
  const answer = page.locator("#feedback-additional");
  await answer.fill("Synthetic unsaved feedback.");
  await page.getByRole("link", { name: "Back to Feedback", exact: true }).click();
  assert.match(prompts[0] ?? "", /Discard your unfinished Customer Feedback response/);
  assert.equal(await page.locator("#feedback-additional").inputValue(), "Synthetic unsaved feedback.");
  assert.match(page.url(), /customer-feedback\?opportunity=/);
});

await check("customer Browser Back asks before discarding the response", customerPath, feedbackOptions({ family: "customer" }), async (page) => {
  const prompts = [];
  await navigate(page, "/portal/feedback");
  await shown(page.getByRole("link", { name: "Give feedback", exact: true }).first());
  await page.getByRole("link", { name: "Give feedback", exact: true }).first().click();
  await shown(page.locator("#feedback-additional"));
  await page.locator("#feedback-additional").fill("Synthetic browser-back draft.");
  page.on("dialog", async (dialog) => {
    prompts.push(dialog.message());
    await dialog.dismiss();
  });
  await page.evaluate(() => window.history.back());
  await page.waitForTimeout(100);
  assert.match(prompts[0] ?? "", /Discard your unfinished Customer Feedback response/);
  assert.equal(await page.locator("#feedback-additional").inputValue(), "Synthetic browser-back draft.");
  assert.match(page.url(), /customer-feedback\?opportunity=/);
});

await check("Customer Feedback malformed opportunity is rejected before a read", "/portal/feedback/customer-feedback?opportunity=not-a-uuid", feedbackOptions({ family: "customer" }), async (page, fixture) => {
  await shown(page.getByRole("heading", { name: "Customer Feedback unavailable", exact: true }));
  assert.equal(fixture.requests.some(({ pathname }) => pathname.includes("/feedback/opportunities/")), false);
});

await check("Customer Feedback opportunity owned by another Student is unavailable", customerPath, feedbackOptions({ family: "customer", unrelated: true }), async (page, fixture) => {
  await shown(page.getByRole("heading", { name: "Customer Feedback unavailable", exact: true }));
  assert.equal(fixture.requests.some(({ method }) => method === "POST"), false);
});

await check("CSM context, Citizen's Charter transition and Not Applicable value 0", csmPath, feedbackOptions({ family: "csm" }), async (page, fixture) => {
  await shown(page.getByRole("heading", { level: 1, name: "HELP US SERVE YOU BETTER!" }));
  await shown(page.getByText(/Feedback for Counseling/));
  await shown(page.locator('input[name="csm-cc2"][value="1"]'));
  await capture(page, "csm-desktop-beginning");
  assert.equal(await page.locator('input[name="csm-sqd0"]').count(), 6);
  assert.equal(await page.locator('input[name^="csm-sqd"]').evaluateAll((nodes) => new Set(nodes.map((node) => node.name)).size), 9);
  assert.equal(await page.locator('input[name="csm-sqd0"][value="0"]').count(), 1);
  await page.locator('input[name="csm-cc1"][value="1"]').check();
  await shown(page.locator('input[name="csm-cc2"][value="2"]'));
  await page.locator('input[name="csm-cc2"][value="2"]').check();
  await page.locator('input[name="csm-cc3"][value="3"]').check();
  await page.locator('input[name="csm-cc1"][value="4"]').check();
  await shown(page.getByText(/CC2 and CC3 are recorded as Not Applicable/));
  await capture(page, "csm-charter-not-applicable");
  assert.equal(await page.locator('input[name="csm-cc2"]').count(), 0);
  await page.locator('input[name="csm-cc1"][value="1"]').check();
  assert.equal(await page.locator('input[name="csm-cc2"]:checked').count(), 0);
  assert.equal(await page.locator('input[name="csm-cc3"]:checked').count(), 0);
  await page.locator('input[name="csm-cc1"][value="4"]').check();
  await page.locator('input[name="csm-sqd0"][value="0"]').check();
  assert.equal(await page.locator('input[name="csm-sqd0"][value="0"]').isChecked(), true);
  assert.equal(fixture.requests.some(({ method }) => method === "POST"), false);
});

await check("CSM required validation, optional email, confirmation cancel and success", csmPath, feedbackOptions({ family: "csm" }), async (page, fixture) => {
  const sent = [];
  await fixture.context.route("**/api/v1/feedback/csm", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") return route.continue();
    sent.push({ body: request.postDataJSON(), key: request.headers()["idempotency-key"] });
    return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(successBody) });
  });
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  assert.equal(await page.getByRole("alertdialog").count(), 0);
  assert.equal(await page.evaluate(() => document.activeElement?.name), "csm-client-type");
  await capture(page, "csm-validation-focus");
  await fillCsmRequired(page, { cc1: 4, zeroFirstSqd: true });
  assert.equal(await page.locator("#csm-service").inputValue(), "Counseling");
  assert.equal(await page.locator("#csm-service").evaluate((input) => input.required), true);
  await page.locator("#csm-suggestions").fill("Clear steps and signs help visitors.");
  await page.locator("#csm-email").fill("not-an-email");
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  assert.equal(await page.getByRole("alertdialog").count(), 0);
  assert.equal(await page.evaluate(() => document.activeElement?.id), "csm-email");
  assert.equal(await page.locator("#csm-email").evaluate((input) => input.validity.typeMismatch), true);
  await capture(page, "csm-email-validation");
  await page.locator("#csm-email").fill("student@example.edu");

  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  const dialog = page.getByRole("alertdialog", { name: "Submit Client Satisfaction Measurement?" });
  await shown(dialog);
  await capture(page, "csm-confirmation");
  await dialog.getByRole("button", { name: "Review response", exact: true }).click();
  await hidden(dialog);
  assert.equal(sent.length, 0, "Canceling confirmation does not submit");
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  await page.getByRole("button", { name: "Submit Client Satisfaction Measurement", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Client Satisfaction Measurement submitted", exact: true }));
  await capture(page, "csm-success");
  assert.equal(sent.length, 1);
  assert.ok(sent[0].key);
  assert.equal(sent[0].body.opportunity_id, csmOpportunityId);
  assert.equal(sent[0].body.service_availed, "Counseling");
  assert.equal(sent[0].body.cc1, 4);
  assert.equal(sent[0].body.cc2, 5);
  assert.equal(sent[0].body.cc3, 4);
  assert.equal(sent[0].body.sqd0, 0);
  for (const key of csmRatingKeys.slice(1)) assert.equal(sent[0].body[key], 5);
  assert.equal(sent[0].body.suggestions, "Clear steps and signs help visitors.");
  assert.equal(sent[0].body.email, "student@example.edu");
  assert.match(await page.getByRole("status").innerText(), /Your response was received/);
});

await check("CSM uncertain submission reuses the exact request and idempotency key", csmPath, feedbackOptions({ family: "csm" }), async (page, fixture) => {
  const sent = [];
  await fixture.context.route("**/api/v1/feedback/csm", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") return route.continue();
    sent.push({ body: request.postData(), key: request.headers()["idempotency-key"] });
    if (sent.length === 1) return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: { code: "idempotency_unavailable" } }) });
    return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(successBody) });
  });
  await fillCsmRequired(page, { cc1: 1, zeroFirstSqd: true });
  await page.getByRole("button", { name: "Review and submit", exact: true }).click();
  await page.getByRole("button", { name: "Submit Client Satisfaction Measurement", exact: true }).click();
  await shown(page.getByText("Submission result not confirmed", { exact: true }));
  await page.getByText("Submission result not confirmed", { exact: true }).scrollIntoViewIfNeeded();
  await capture(page, "csm-uncertain");
  assert.equal(await page.locator("fieldset[disabled]").count(), 1);
  await page.getByRole("button", { name: "Retry same submission", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Client Satisfaction Measurement submitted", exact: true }));
  assert.equal(sent.length, 2);
  assert.deepEqual(sent[1], sent[0]);
});

await check("CSM phone and narrow reflow keep six native choices keyboard accessible", csmPath, { ...feedbackOptions({ family: "csm", device: "phone" }), viewport: { width: 390, height: 844 } }, async (page) => {
  await shown(page.getByRole("heading", { name: "HELP US SERVE YOU BETTER!" }));
  await capture(page, "csm-phone-beginning");
  await page.locator('input[name="csm-cc1"][value="1"]').focus();
  await page.locator('input[name="csm-cc1"][value="1"]').press("ArrowDown");
  assert.equal(await page.locator('input[name="csm-cc1"][value="2"]').isChecked(), true);
  await page.locator("#feedback-service-quality").scrollIntoViewIfNeeded();
  await capture(page, "csm-phone-ratings");
  const gridColumns = await page.locator('input[name="csm-sqd0"]').first().evaluate((input) => getComputedStyle(input.closest("fieldset").querySelector(".grid")).gridTemplateColumns.split(" ").length);
  assert.equal(gridColumns, 1, "Long response descriptions use one column on phones");
  const targetHeight = await page.locator('label[for="csm-sqd0-5"]').evaluate((label) => label.getBoundingClientRect().height);
  assert.ok(targetHeight >= 44, `Not Applicable touch target is ${targetHeight}px high`);
  await page.setViewportSize({ width: 320, height: 640 });
  await noHorizontalOverflow(page);
  await page.addStyleTag({ content: ":root { font-size: 200% !important; }" });
  const formDimensions = await page.locator("form").evaluate((form) => ({ width: form.clientWidth, scrollWidth: form.scrollWidth }));
  assert.ok(formDimensions.scrollWidth <= formDimensions.width + 1, "The modified form reflows at 200% text size");
});

await check("CSM already-submitted and ineligible opportunities stay unavailable", csmPath, feedbackOptions({
  family: "csm",
  opportunity: csmOpportunity({ csm_submitted: true }),
}), async (page) => {
  await shown(page.getByRole("heading", { name: "Client Satisfaction Measurement submitted", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Review and submit", exact: true }).count(), 0);
});

await check("CSM ineligible opportunity stays unavailable", csmPath, feedbackOptions({
  family: "csm",
  opportunity: csmOpportunity({ can_submit_csm: false }),
}), async (page) => {
  await shown(page.getByRole("heading", { name: "Client Satisfaction Measurement unavailable", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Review and submit", exact: true }).count(), 0);
});

await check("CSM malformed opportunity is rejected before a read", "/portal/feedback/csm?opportunity=not-a-uuid", feedbackOptions({ family: "csm" }), async (page, fixture) => {
  await shown(page.getByRole("heading", { name: "Client Satisfaction Measurement unavailable", exact: true }));
  assert.equal(fixture.requests.some(({ pathname }) => pathname.includes("/feedback/opportunities/")), false);
});

await check("CSM opportunity owned by another Student is unavailable", csmPath, feedbackOptions({ family: "csm", unrelated: true }), async (page, fixture) => {
  await shown(page.getByRole("heading", { name: "Client Satisfaction Measurement unavailable", exact: true }));
  assert.equal(fixture.requests.some(({ method }) => method === "POST"), false);
});

await finish();
