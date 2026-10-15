import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup as render } from "react-dom/server";
import { ExitInterviewFormSections } from "../src/features/exit-interviews/exit-interview-form-sections.tsx";
import { exitInterviewFormFromDetail, exitInterviewDraftPayload } from "../src/features/exit-interviews/exit-interview-presentation.ts";
import { exitInterviewTextLimits } from "../src/features/exit-interviews/exit-interview-field-limits.ts";
import { ReviewSection } from "../src/features/inventory/editor/review-section.tsx";
import { exitRecord } from "./support/form-ui-1b-fixtures.mjs";

const contract = JSON.parse(readFileSync(new URL("../../contracts/openapi.json", import.meta.url), "utf8"));
const codes = contract.components.schemas.CollegeFeedbackItemValue.enum;
const selfCodes = contract.components.schemas.SelfAssessmentItemValue.enum;
const textFields = { studentName: ["exit-student-name", "input"], civilStatus: ["exit-civil-status", "input"], course: ["exit-course", "input"], major: ["exit-major", "input"], emailAddress: ["exit-email-address", "input"], contactNumber: ["exit-contact-number", "input"], homeAddress: ["exit-home-address", "textarea"], delayOther: ["exit-delay-other-detail", "textarea"], significantLearningOther: ["exit-learning-other-detail", "textarea"], suggestionsRecommendations: ["exit-suggestions-recommendations", "textarea"] };
const fieldTag = (html, id, element) => html.match(new RegExp(`<${element}[^>]*id="${id}"[^>]*>`))?.[0];
function exitHtml(detail, transform = (form) => form) {
  const form = transform(exitInterviewFormFromDetail(detail));
  return render(h(ExitInterviewFormSections, { form, disabled: false, onTextChange() {}, onProgramCompletionChange() {}, onToggleDelayReason() {}, onToggleLearning() {}, onToggleCareerMode() {}, onToggleWorkChoice() {}, onToggleStudyChoice() {}, onRatingChange() {} }));
}
test("Exit Interview mirrored limits match authoritative confidential and model bounds", () => {
  const source = readFileSync(new URL("../../be/compass/exit_interviews/confidential_content.py", import.meta.url), "utf8");
  const server = Object.fromEntries([...source.slice(source.indexOf("CONTENT_LIMITS = {"), source.indexOf("@dataclass")).matchAll(/"(\w+)": (\d+)/g)].map(([, key, value]) => [key, Number(value)]));
  const names = { emailAddress: "email_snapshot", homeAddress: "home_address_snapshot", contactNumber: "contact_number_snapshot", delayOther: "delay_other", significantLearningOther: "significant_learning_other" };
  const models = readFileSync(new URL("../../be/compass/exit_interviews/models.py", import.meta.url), "utf8");
  const typed = { studentName: "student_name_snapshot", civilStatus: "civil_status_snapshot", course: "course_snapshot", major: "major_snapshot" };
  for (const [key, maximum] of Object.entries(exitInterviewTextLimits)) {
    const backend = names[key] ?? key.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
    const expected = key in typed ? Number(models.match(new RegExp(`${typed[key]} = models.CharField\\(max_length=(\\d+)`))[1]) : server[backend];
    assert.equal(maximum, expected, key);
  }
});
for (const legacy of [false, true]) test(`${legacy ? "legacy null-revision" : "UCN F9"} fields expose verified limits and preserve saved values and ratings`, () => {
  const detail = { ...exitRecord(codes, selfCodes, legacy), program_completion: "WITH_SOME_DELAY", extra_terms_count: 1, delay_reasons: ["OTHER"], significant_learning_experiences: ["OTHER"] };
  const form = exitInterviewFormFromDetail(detail);
  const before = exitInterviewDraftPayload(form);
  const html = exitHtml(detail, form => {
    for (const [key, maximum] of Object.entries(exitInterviewTextLimits)) form[key] = "X".repeat(maximum + 1);
    return form;
  });
  for (const [key, maximum] of Object.entries(exitInterviewTextLimits)) {
    if (!legacy && key === "programChairComments") continue;
    const [id, element] = textFields[key] ?? [`exit-comment-${key}`, "textarea"];
    assert.match(fieldTag(html, id, element), new RegExp(`maxLength="${maximum}"`, "i"));
    assert.match(fieldTag(html, id, element), new RegExp(`aria-describedby="[^"]*${id}-limit`));
    assert.ok(html.includes("X".repeat(maximum + 1)));
    assert.ok(html.includes(`longer than ${maximum.toLocaleString("en-US")} characters`));
  }
  assert.equal(before.college_feedback_ratings.length, legacy ? 26 : 23);
  assert.equal(before.self_assessment_ratings.length, 15);
  assert.ok(before.college_feedback_ratings.every(rating => rating.rating === 0));
  if (legacy) assert.equal(before.program_chair_comments, "SYNTHETIC LEGACY CHAIR CONTENT");
  assert.equal(exitInterviewDraftPayload(form).college_feedback_ratings.length, legacy ? 26 : 23);
});
test("conditional Exit fields and limit descriptions appear only when applicable", () => {
  const detail = exitRecord(codes, selfCodes);
  const html = exitHtml(detail);
  assert.doesNotMatch(html, /id="exit-delay-other-detail"|id="exit-learning-other-detail"/);
  assert.doesNotMatch(fieldTag(html, "exit-major", "input"), /aria-describedby/);
  const atLimit = exitHtml(detail, form => ({ ...form, major: "M".repeat(180) }));
  assert.match(atLimit, /You’ve reached the 180-character limit/);
  assert.match(fieldTag(atLimit, "exit-major", "input"), /aria-describedby="exit-major-limit"/);
  assert.doesNotMatch(fieldTag(html, "exit-age", "input"), /maxLength/i);
});

for (const issues of [[], [{ section: "personal", targetId: "inventory-sex", message: "Choose a sex response." }]]) {
  test(`Inventory review uses plain guidance with ${issues.length} unanswered questions`, () => {
    const html = render(h(ReviewSection, { draft: {}, academicYear: "2026-2027", formRevision: "UCN F5", issues, programLookupReady: true, onSelectIssue() {} }));
    assert.match(html, /Before you submit/);
    assert.doesNotMatch(html, /Submission readiness|No required-field issues|Official PDF capacity/);
    assert.match(html, /You can’t edit your answers after submitting/);
    assert.equal(html.includes("Complete these answers"), issues.length > 0);
    assert.equal(html.includes("Choose a sex response."), issues.length > 0);
    if (issues.length === 0) assert.doesNotMatch(html, /role="status"/);
  });
}
