// FORM-CORR-1 PR 3: Exit Interview correction targets in the frontend. The backend owns the catalog
// and checks every request against the record's saved Form Revision; these checks keep the frontend
// map exhaustive, keep UCN F9 and legacy records distinct, prove each code leads to a rendered
// control, and keep targets advisory. Every record here is synthetic.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ExitInterviewCorrectionHistory } from "../src/features/exit-interviews/exit-interview-correction-history.tsx";
import { ExitInterviewCorrectionTargetChooser } from "../src/features/exit-interviews/exit-interview-correction-target-chooser.tsx";
import {
  allowedExitInterviewCorrectionTargets,
  emptyExitInterviewReviewHints,
  exitInterviewCorrectionFocusOrder,
  exitInterviewCorrectionSections,
  exitInterviewCorrectionTargetOrder,
  exitInterviewCorrectionTargets,
  exitInterviewCorrectionTargetTitle,
  exitInterviewReviewHintId,
  exitInterviewReviewHints,
  exitInterviewSectionReviewId,
  MAX_EXIT_INTERVIEW_CORRECTION_TARGETS,
  readExitInterviewCorrectionTargets,
  sortExitInterviewCorrectionTargets,
} from "../src/features/exit-interviews/exit-interview-correction-targets.ts";
import { ExitInterviewFormSections } from "../src/features/exit-interviews/exit-interview-form-sections.tsx";
import {
  COLLEGE_FEEDBACK_CATEGORIES,
  exitInterviewDraftPayload,
  exitInterviewFormFromDetail,
  exitRatingRowId,
} from "../src/features/exit-interviews/exit-interview-presentation.ts";
import { ExitInterviewReviewProvider } from "../src/features/exit-interviews/exit-interview-review-context.tsx";

const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const openingTag = (html, id) => html.match(new RegExp(`<[a-z0-9]+[^>]*\\sid="${escape(id)}"[^>]*>`))?.[0];
const describedBy = (tag) => (tag?.match(/aria-describedby="([^"]*)"/)?.[1] ?? "").split(" ").filter(Boolean);
const ids = (html) => [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);

const codes = Object.keys(exitInterviewCorrectionTargets);
const legacyItems = COLLEGE_FEEDBACK_CATEGORIES.flatMap((category) => category.items.map((item) => item.code));
const f9Items = legacyItems.filter((code) => !code.startsWith("PROGRAM_CHAIR_"));

function detail(overrides = {}) {
  return {
    id: "exit-corr", academic_year: { id: "year", label: "2026-2027" }, status: "DRAFT", can_edit: true,
    student: { id: "student", display_name: "Maria Santos", institutional_id: "TEST-01" }, student_name: "Maria Santos",
    inventory_id: "inventory", created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-02T00:00:00Z",
    first_submitted_at: "2026-10-01T06:00:00Z", last_submitted_at: "2026-10-01T06:00:00Z",
    form_revision: null, college_feedback_item_codes: legacyItems,
    program_completion: "WITH_SOME_DELAY", extra_terms_count: 1, delay_reasons: ["TRANSFEREE"],
    self_assessment_ratings: [{ item_code: "SELF_ESTEEM", rating: 4 }],
    college_feedback_ratings: [{ item_code: "GUIDANCE_COUNSELOR_EFFICIENCY", rating: 0 }],
    reopen_events: [], ...overrides,
  };
}

function renderForm(form, targets) {
  return renderToStaticMarkup(h(ExitInterviewReviewProvider, { value: exitInterviewReviewHints(targets, form) }, h(ExitInterviewFormSections, {
    form, disabled: false,
    onTextChange() {}, onProgramCompletionChange() {}, onToggleDelayReason() {}, onToggleLearning() {},
    onToggleCareerMode() {}, onToggleWorkChoice() {}, onToggleStudyChoice() {}, onRatingChange() {},
  })));
}

// --- Catalog parity with the backend ------------------------------------------------------------

function backendCatalog() {
  const source = readFileSync(new URL("../../be/compass/exit_interviews/correction_targets.py", import.meta.url), "utf8");
  const body = source.slice(source.indexOf("class ExitInterviewCorrectionTarget(StrEnum):"), source.indexOf("_T = ExitInterviewCorrectionTarget"));
  return [...body.matchAll(/"([a-z_]+\.[A-Za-z_.]+)"/g)].map((match) => match[1]);
}

test("the frontend map names exactly the backend catalog, in catalog order, keyed by enum value", () => {
  const backend = backendCatalog();
  assert.equal(backend.length, 68);
  assert.deepEqual([...codes].sort(), [...backend].sort());
  assert.deepEqual([...exitInterviewCorrectionTargetOrder], backend);
  const limit = readFileSync(new URL("../../be/compass/exit_interviews/correction_targets.py", import.meta.url), "utf8").match(/MAX_CORRECTION_TARGETS = (\d+)/)?.[1];
  assert.equal(MAX_EXIT_INTERVIEW_CORRECTION_TARGETS, Number(limit));
});

test("every code has a unique plain title taken from the form's own labels", () => {
  const titles = codes.map((code) => exitInterviewCorrectionTargetTitle(code));
  assert.equal(new Set(titles).size, codes.length);
  for (const title of titles) assert.doesNotMatch(title, /[._]|[A-Z]{2,}_/, `${title} reads as words, not a code`);
  assert.equal(exitInterviewCorrectionTargetTitle("completion.program_completion"), "Program completion");
  assert.equal(exitInterviewCorrectionTargetTitle("self_assessment.SELF_ESTEEM"), "Self-Assessment — Self Esteem");
  assert.equal(exitInterviewCorrectionTargetTitle("college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY"), "College Feedback — Guidance Counselor — Efficiency");
  assert.equal(exitInterviewCorrectionTargetTitle("college_feedback.comments.program_chair"), "College Feedback — Comments about the Program Chair");
  assert.equal(exitInterviewCorrectionTargetTitle("section.self_assessment"), "Section II — Self-Assessment (whole section)");
  // Rating rows use the same id the form gives them.
  assert.equal(exitInterviewCorrectionTargets["college_feedback.DEAN_AVAILABILITY"].anchor, exitRatingRowId("college", "DEAN_AVAILABILITY"));
});

// --- Saved Form Revision ------------------------------------------------------------------------

test("UCN F9 allows 64 targets with 23 ratings and no Program Chair; legacy allows all 68 with 26", () => {
  const f9 = allowedExitInterviewCorrectionTargets(f9Items);
  assert.equal(f9.length, 64);
  assert.equal(f9.filter((code) => exitInterviewCorrectionTargets[code].feedbackItem).length, 23);
  assert.ok(!f9.some((code) => /PROGRAM_CHAIR|program_chair/.test(code)), "No Program Chair rating or comment on F9");
  assert.equal(f9.filter((code) => code.startsWith("college_feedback.comments.")).length, 6);

  const legacy = allowedExitInterviewCorrectionTargets(legacyItems);
  assert.equal(legacy.length, 68);
  assert.equal(legacy.filter((code) => exitInterviewCorrectionTargets[code].feedbackItem).length, 26);
  assert.ok(legacy.includes("college_feedback.comments.program_chair"));
  assert.ok(legacy.includes("college_feedback.PROGRAM_CHAIR_CONCERN_FOR_STUDENTS"));
  assert.deepEqual(legacy, [...exitInterviewCorrectionTargetOrder], "Allowed targets keep catalog order");
});

test("the chooser offers only the record's form, collapsed, with nothing selected", () => {
  const f9 = renderToStaticMarkup(h(ExitInterviewCorrectionTargetChooser, { allowed: allowedExitInterviewCorrectionTargets(f9Items), value: [], onChange() {} }));
  assert.equal([...f9.matchAll(/type="checkbox"/g)].length, 64);
  assert.doesNotMatch(f9, /Program Chair/);
  assert.doesNotMatch(f9, /checked=""/);
  assert.doesNotMatch(f9, /<details[^>]*open/);
  assert.equal([...f9.matchAll(/<details/g)].length, 5);
  assert.match(f9, /Answers to review \(optional\)/);
  assert.match(f9, /Choose the parts of the form the Student should look at again\. They will see these with your instructions\./);
  assert.match(f9, /None\. The Student will see only your reason\./);

  const legacy = renderToStaticMarkup(h(ExitInterviewCorrectionTargetChooser, { allowed: allowedExitInterviewCorrectionTargets(legacyItems), value: [], onChange() {} }));
  assert.equal([...legacy.matchAll(/type="checkbox"/g)].length, 68);
  assert.match(legacy, /<legend[^>]*>Program Chair<\/legend>/);
  assert.match(legacy, /Comments about the Program Chair/);
});

test("the chooser lists the selection with Remove buttons and stops at 30", () => {
  const allowed = allowedExitInterviewCorrectionTargets(f9Items);
  const some = renderToStaticMarkup(h(ExitInterviewCorrectionTargetChooser, { allowed, value: ["completion.program_completion", "college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY"], onChange() {} }));
  assert.match(some, /aria-label="Remove College Feedback — Guidance Counselor — Efficiency"/);
  assert.match(some, /aria-label="Remove Program completion"/);
  const thirty = allowed.slice(0, 30);
  const full = renderToStaticMarkup(h(ExitInterviewCorrectionTargetChooser, { allowed, value: thirty, onChange() {} }));
  assert.match(full, /30 of 30 selected\. Remove one to choose another\./);
  const unchecked = [...full.matchAll(/<input type="checkbox"[^>]*>/g)].map((match) => match[0]).filter((tag) => !tag.includes('checked=""'));
  assert.equal(unchecked.length, 34);
  assert.ok(unchecked.every((tag) => tag.includes('disabled=""')));
  const pending = renderToStaticMarkup(h(ExitInterviewCorrectionTargetChooser, { allowed, value: [], onChange() {}, disabled: true }));
  assert.match(pending, /^<fieldset disabled=""/);
});

// --- Every anchor is a rendered control ---------------------------------------------------------

test("every allowed target's anchor is rendered and described by its hint, on legacy and F9 forms", () => {
  for (const items of [legacyItems, f9Items]) {
    const form = exitInterviewFormFromDetail(detail({ college_feedback_item_codes: items }));
    const allowed = allowedExitInterviewCorrectionTargets(items);
    const html = renderForm(form, allowed);
    assert.doesNotMatch(html, /aria-invalid/, "Review targets never mark answers invalid");
    for (const code of allowed) {
      const definition = exitInterviewCorrectionTargets[code];
      const anchor = openingTag(html, definition.anchor);
      assert.ok(anchor, `${code}: #${definition.anchor} is rendered`);
      if (definition.scope === "section") {
        assert.match(anchor, /tabindex="-1"/, `${code}: the section note takes focus`);
        continue;
      }
      const hintId = exitInterviewReviewHintId(definition.anchor);
      assert.ok(describedBy(anchor).includes(hintId), `${code}: #${definition.anchor} is described by its hint`);
      assert.ok(openingTag(html, hintId), `${code}: #${hintId} is rendered`);
    }
    for (const hint of html.matchAll(/<span id="[^"]+-review"[^>]*>([^<]*)<\/span>/g)) {
      assert.doesNotMatch(hint[0], /text-danger|role="alert"/);
      assert.doesNotMatch(hint[1], /incorrect|invalid|wrong|error/i);
    }
    const rendered = ids(html);
    assert.deepEqual(rendered.filter((id, index) => rendered.indexOf(id) !== index), [], "ids are unique");
  }
  // F9 renders no Program Chair row, so none could ever be a dead target.
  const f9 = renderForm(exitInterviewFormFromDetail(detail({ college_feedback_item_codes: f9Items })), []);
  assert.equal(openingTag(f9, exitRatingRowId("college", "PROGRAM_CHAIR_AVAILABILITY")), undefined);
  assert.equal(openingTag(f9, "exit-comment-programChairComments"), undefined);
});

test("the new group ids exist, and program completion is a named radio group", () => {
  const html = renderForm(exitInterviewFormFromDetail(detail()), []);
  for (const id of ["exit-program-completion", "exit-delay-reasons", "exit-learning-experiences", "exit-career-work-plans", "exit-career-study-plans"]) {
    assert.match(openingTag(html, id) ?? "", /^<fieldset/, `#${id} identifies the question's fieldset`);
  }
  assert.match(html, /<fieldset id="exit-program-completion"[^>]*><legend[^>]*>Program completion<\/legend>/);
});

test("hidden delay details are pointed out at Program completion, never by changing an answer", () => {
  const onSchedule = exitInterviewFormFromDetail(detail({ program_completion: "ACCORDING_TO_SCHEDULE", extra_terms_count: null, delay_reasons: [] }));
  const targets = ["completion.program_completion", "completion.extra_terms_count", "completion.delay_reasons"];
  const hints = exitInterviewReviewHints(targets, onSchedule);
  assert.equal(
    hints.hints.get("exit-program-completion"),
    "You were asked to review this answer. You were asked to review the delay details. They appear when you choose With some delay.",
  );
  assert.equal(hints.hints.get("exit-extra-terms"), undefined);
  assert.deepEqual(exitInterviewCorrectionFocusOrder("completion.extra_terms_count", onSchedule), ["exit-program-completion", "exit-interview-program-completion"]);
  const html = renderForm(onSchedule, targets);
  assert.equal(openingTag(html, "exit-extra-terms"), undefined);
  assert.ok(describedBy(openingTag(html, "exit-program-completion")).includes("exit-program-completion-review"));
  const schedule = [...html.matchAll(/<input[^>]*name="exit-program-completion"[^>]*>/g)].map((match) => match[0]).find((tag) => tag.includes('value="ACCORDING_TO_SCHEDULE"'));
  assert.match(schedule, /checked=""/, "The saved answer is untouched");

  const delayedForm = exitInterviewFormFromDetail(detail());
  assert.deepEqual(exitInterviewCorrectionFocusOrder("completion.extra_terms_count", delayedForm), ["exit-extra-terms", "exit-program-completion", "exit-interview-program-completion"]);
  assert.deepEqual(exitInterviewCorrectionFocusOrder("section.college_feedback", delayedForm), [exitInterviewSectionReviewId("college_feedback"), "exit-interview-college-feedback"]);
});

// --- Rating 0 -----------------------------------------------------------------------------------

test("a targeted rating of 0 stays 0, keeps its plain header, and gains no meaning", () => {
  const form = exitInterviewFormFromDetail(detail());
  assert.equal(form.collegeRatings.GUIDANCE_COUNSELOR_EFFICIENCY, "0");
  const target = "college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY";
  const html = renderForm(form, [target]);
  const rowId = exitRatingRowId("college", "GUIDANCE_COUNSELOR_EFFICIENCY");
  const row = html.slice(html.indexOf(`id="${rowId}"`), html.indexOf("</tr>", html.indexOf(`id="${rowId}"`)));
  assert.match(row, /You were asked to review this answer\./);
  const zero = [...row.matchAll(/<input[^>]*>/g)].map((match) => match[0]).find((tag) => tag.includes('value="0"'));
  assert.match(zero, /checked=""/, "The saved 0 stays checked");
  assert.equal([...row.matchAll(/checked=""/g)].length, 1);
  assert.equal([...row.matchAll(/<input[^>]*aria-describedby="[^"]*-review"/g)].length, 6, "Every choice in the row hears the one hint");
  assert.equal([...row.matchAll(/You were asked to review this answer\./g)].length, 1, "The hint is shown once per row");
  assert.match(row, /Efficiency: 0<\/span>/, "0 keeps its unlabeled accessible value");
  assert.doesNotMatch(html, /Not applicable|N\/A|No answer/i);
  // The payload sends the 0 unchanged and carries no target.
  const payload = exitInterviewDraftPayload(form);
  assert.deepEqual(payload.college_feedback_ratings, [{ item_code: "GUIDANCE_COUNSELOR_EFFICIENCY", rating: 0 }]);
  assert.doesNotMatch(JSON.stringify(payload), /targets|reopen|college_feedback\.GUIDANCE/);
});

test("F9 and legacy answer contracts stay distinct after a reopen with targets", () => {
  const event = { id: "e", reason: "Synthetic.", reopened_at: "2026-10-02T00:00:00Z", reopened_by: { id: "r", display_name: "Reviewer" }, targets: ["college_feedback.comments.dean"] };
  const f9 = exitInterviewDraftPayload(exitInterviewFormFromDetail(detail({ college_feedback_item_codes: f9Items, reopen_events: [event] })));
  const legacy = exitInterviewDraftPayload(exitInterviewFormFromDetail(detail({ college_feedback_item_codes: legacyItems, reopen_events: [event] })));
  assert.equal(exitInterviewFormFromDetail(detail({ college_feedback_item_codes: f9Items })).collegeFeedbackItemCodes.length, 23);
  assert.equal(exitInterviewFormFromDetail(detail({ college_feedback_item_codes: legacyItems })).collegeFeedbackItemCodes.length, 26);
  assert.ok(!("targets" in f9) && !("reopen_events" in legacy));
});

// --- Reading targets and the Student's notice -----------------------------------------------------

test("received targets are named in catalog order; unknown codes are counted, never shown", () => {
  assert.deepEqual(readExitInterviewCorrectionTargets(undefined), { targets: [], unknown: 0 });
  assert.deepEqual(
    readExitInterviewCorrectionTargets(["suggestions.suggestions_recommendations", "general.age", "general.age", "general.future"]),
    { targets: ["general.age", "suggestions.suggestions_recommendations"], unknown: 1 },
  );
  assert.deepEqual(sortExitInterviewCorrectionTargets(["section.suggestions", "general.major"]), ["general.major", "section.suggestions"]);
  assert.equal(exitInterviewReviewHints([], exitInterviewFormFromDetail(detail())), emptyExitInterviewReviewHints);
});

const reopen = (id, name, reason, at, targets) => ({ id, reason, reopened_at: at, reopened_by: { id: `reviewer-${id}`, display_name: name }, ...(targets ? { targets } : {}) });

test("a reason-only correction and older events look exactly as before", () => {
  const events = [reopen("first", "Head Example", "Earlier synthetic reason.", "2026-10-05T02:00:00Z"), reopen("latest", "Carlo Counselor", "Clarify the second answer.", "2026-10-06T03:00:00Z", [])];
  const html = renderToStaticMarkup(h(ExitInterviewCorrectionHistory, { events, emphasizeLatest: true, onSelectTarget() {} }));
  assert.match(html, /Correction requested/);
  assert.match(html, /Carlo Counselor reopened this Exit Interview for correction\./);
  assert.match(html, /Clarify the second answer\./);
  assert.doesNotMatch(html, /Answers to review|<button/);
});

test("the pending request lists actionable answers; history lists them as plain text", () => {
  const targets = ["completion.program_completion", "self_assessment.SELF_ESTEEM", "college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY", "general.unreleased"];
  const events = [
    reopen("first", "Head Example", "Earlier synthetic reason.", "2026-10-05T02:00:00Z", ["general.major"]),
    reopen("latest", "Carlo Counselor", "Please review these answers.", "2026-10-06T03:00:00Z", targets),
  ];
  const editable = renderToStaticMarkup(h(ExitInterviewCorrectionHistory, { events, emphasizeLatest: true, onSelectTarget() {} }));
  const notice = editable.slice(0, editable.indexOf("Correction history"));
  for (const label of ["Program completion", "Self-Assessment — Self Esteem", "College Feedback — Guidance Counselor — Efficiency"]) {
    assert.ok(notice.includes(`>${label}</button>`), `${label} is a button in the pending notice`);
  }
  assert.match(notice, /1 more part of the form/);
  assert.ok(notice.indexOf("Please review these answers.") < notice.indexOf("Answers to review"));
  const history = editable.slice(editable.indexOf("Correction history"));
  assert.doesNotMatch(history, /<button/, "Completed and earlier requests are never actionable");
  assert.match(history, /General information — Major/);
  for (const code of [...targets, "general.major"]) assert.ok(!editable.includes(code), `never shows ${code}`);

  // A reviewer, or a Student whose draft cannot be edited, sees plain text everywhere.
  const readOnly = renderToStaticMarkup(h(ExitInterviewCorrectionHistory, { events, emphasizeLatest: true }));
  assert.doesNotMatch(readOnly, /<button/);
  assert.match(readOnly, /Self-Assessment — Self Esteem/);
  const reviewer = renderToStaticMarkup(h(ExitInterviewCorrectionHistory, { events }));
  assert.doesNotMatch(reviewer, /Correction requested|<button/);
  assert.match(reviewer, /College Feedback — Guidance Counselor — Efficiency/);
});

test("section ids in the map match the form's section headings", () => {
  const html = renderForm(exitInterviewFormFromDetail(detail()), []);
  for (const section of exitInterviewCorrectionSections) {
    assert.match(openingTag(html, section.headingId) ?? "", /^<h[23]/, `#${section.headingId} is the section heading`);
    assert.ok(html.includes(`>${section.title}</h`), `${section.title} is the heading text`);
  }
});
