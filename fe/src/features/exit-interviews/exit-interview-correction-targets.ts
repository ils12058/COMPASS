import {
  CollegeFeedbackItemValue,
  ExitInterviewCorrectionTarget,
  ProgramCompletionValue,
  SelfAssessmentItemValue,
} from "@/lib/api/generated/model";
import {
  COLLEGE_FEEDBACK_CATEGORIES,
  exitRatingRowId,
  SELF_ASSESSMENT_ITEMS,
  type ExitInterviewFormState,
} from "@/features/exit-interviews/exit-interview-presentation";

// FORM-CORR-1: what each backend Exit Interview correction-target code means in the form. The
// backend owns the codes (be/compass/exit_interviews/correction_targets.py), checks every request
// against the record's saved Form Revision, and returns them in catalog order. This map only names
// a code for people and says where the Student finds it. It is keyed by the enum *values*: the
// generated object keys drop the dots.
//
// A target asks the Student to look at an answer again. It is not a validation error and says
// nothing about the answer, including a College Feedback rating of 0, which has no defined meaning.

export type ExitInterviewCorrectionSectionId =
  | "general_information"
  | "program_completion_and_plans"
  | "self_assessment"
  | "college_feedback"
  | "suggestions";

// The form's own section titles and heading ids.
export const exitInterviewCorrectionSections: readonly {
  id: ExitInterviewCorrectionSectionId;
  title: string;
  headingId: string;
}[] = [
  { id: "general_information", title: "General information", headingId: "exit-interview-general-information" },
  { id: "program_completion_and_plans", title: "Section I — Program completion and plans", headingId: "exit-interview-program-completion" },
  { id: "self_assessment", title: "Section II — Self-Assessment", headingId: "exit-interview-self-assessment" },
  { id: "college_feedback", title: "Section III — College Feedback", headingId: "exit-interview-college-feedback" },
  { id: "suggestions", title: "Suggestions / Recommendations", headingId: "exit-interview-suggestions" },
];

export type ExitInterviewCorrectionCondition = {
  // Whether the anchor is rendered for these answers.
  visible: (form: ExitInterviewFormState) => boolean;
  // The question that reveals it.
  fallback: string;
  hint: string;
};

export type ExitInterviewCorrectionTargetDefinition = {
  section: ExitInterviewCorrectionSectionId;
  // The form group the answer sits in; it organizes the reviewer's choices.
  group: string;
  // The answer's name within its group, as the form shows it.
  label: string;
  // The full plain-language name: "College Feedback — Guidance Counselor — Efficiency".
  title: string;
  scope: "section" | "answer";
  // The element that receives focus (a control, a fieldset, or a rating row).
  anchor: string;
  condition?: ExitInterviewCorrectionCondition;
  // The College Feedback rating item the code names, or whose category the comment belongs to.
  feedbackItem?: CollegeFeedbackItemValue;
  feedbackCategoryPrefix?: string;
};

type Definition = ExitInterviewCorrectionTargetDefinition;

export function exitInterviewSectionReviewId(section: ExitInterviewCorrectionSectionId): string {
  const heading = exitInterviewCorrectionSections.find((item) => item.id === section)!.headingId;
  return `${heading}-review`;
}

export const exitInterviewReviewHintText = {
  section: "You were asked to review this section.",
  answer: "You were asked to review this answer.",
} as const;

export function exitInterviewReviewHintId(host: string): string {
  return `${host}-review`;
}

const sectionTitle = (section: ExitInterviewCorrectionSectionId) =>
  exitInterviewCorrectionSections.find((item) => item.id === section)!.title;

function sectionTarget(section: ExitInterviewCorrectionSectionId): Definition {
  return {
    section,
    group: "Whole section",
    label: "Whole section",
    title: `${sectionTitle(section)} (whole section)`,
    scope: "section",
    anchor: exitInterviewSectionReviewId(section),
  };
}

function general(label: string, anchor: string): Definition {
  return { section: "general_information", group: "General information", label, title: `General information — ${label}`, scope: "answer", anchor };
}

const delayed: ExitInterviewCorrectionCondition = {
  visible: (form) => form.programCompletion === ProgramCompletionValue.WITH_SOME_DELAY,
  fallback: "exit-program-completion",
  hint: "You were asked to review the delay details. They appear when you choose With some delay.",
};

const selfAssessmentLabels = new Map<string, string>(SELF_ASSESSMENT_ITEMS.map((item) => [item.code, item.label]));

function selfAssessment(code: SelfAssessmentItemValue): Definition {
  const label = selfAssessmentLabels.get(code) ?? code;
  return {
    section: "self_assessment",
    group: "Self-Assessment",
    label,
    title: `Self-Assessment — ${label}`,
    scope: "answer",
    anchor: exitRatingRowId("self", code),
  };
}

const feedbackCategories = new Map(COLLEGE_FEEDBACK_CATEGORIES.map((category) => [category.commentKey, category]));
const feedbackItems = new Map(
  COLLEGE_FEEDBACK_CATEGORIES.flatMap((category) => category.items.map((item) => [item.code, { category, item }] as const)),
);

function feedbackRating(code: CollegeFeedbackItemValue): Definition {
  const { category, item } = feedbackItems.get(code)!;
  return {
    section: "college_feedback",
    group: category.label,
    label: item.label,
    title: `College Feedback — ${category.label} — ${item.label}`,
    scope: "answer",
    anchor: exitRatingRowId("college", code),
    feedbackItem: code,
  };
}

function feedbackComment(commentKey: (typeof COLLEGE_FEEDBACK_CATEGORIES)[number]["commentKey"], prefix: string): Definition {
  const category = feedbackCategories.get(commentKey)!;
  return {
    section: "college_feedback",
    group: category.label,
    label: category.commentLabel,
    title: `College Feedback — ${category.commentLabel}`,
    scope: "answer",
    anchor: `exit-comment-${commentKey}`,
    feedbackCategoryPrefix: prefix,
  };
}

const C = CollegeFeedbackItemValue;
const S = SelfAssessmentItemValue;

export const exitInterviewCorrectionTargets = {
  "section.general_information": sectionTarget("general_information"),
  "general.student_name": general("Student name", "exit-student-name"),
  "general.age": general("Age", "exit-age"),
  "general.civil_status": general("Civil Status", "exit-civil-status"),
  "general.course": general("Course", "exit-course"),
  "general.major": general("Major", "exit-major"),
  "general.email_address": general("Email Address", "exit-email-address"),
  "general.contact_number": general("Contact Number", "exit-contact-number"),
  "general.home_address": general("Home Address", "exit-home-address"),

  "section.program_completion_and_plans": sectionTarget("program_completion_and_plans"),
  "completion.program_completion": {
    section: "program_completion_and_plans", group: "Program completion", label: "Program completion",
    title: "Program completion", scope: "answer", anchor: "exit-program-completion",
  },
  "completion.extra_terms_count": {
    section: "program_completion_and_plans", group: "Program completion", label: "Number of extra terms",
    title: "Program completion — Number of extra terms", scope: "answer", anchor: "exit-extra-terms", condition: delayed,
  },
  "completion.delay_reasons": {
    section: "program_completion_and_plans", group: "Program completion", label: "Reason for delay",
    title: "Program completion — Reason for delay", scope: "answer", anchor: "exit-delay-reasons", condition: delayed,
  },
  "learning.significant_learning_experiences": {
    section: "program_completion_and_plans", group: "Significant learning experiences", label: "Significant learning experiences",
    title: "Significant learning experiences", scope: "answer", anchor: "exit-learning-experiences",
  },
  "career.work": {
    section: "program_completion_and_plans", group: "Career plans", label: "Work",
    title: "Career plans — Work", scope: "answer", anchor: "exit-career-work-plans",
  },
  "career.study": {
    section: "program_completion_and_plans", group: "Career plans", label: "Study",
    title: "Career plans — Study", scope: "answer", anchor: "exit-career-study-plans",
  },

  "section.self_assessment": sectionTarget("self_assessment"),
  "self_assessment.PRIDE_CONFIDENCE_CNSC": selfAssessment(S.PRIDE_CONFIDENCE_CNSC),
  "self_assessment.ACADEMIC_RECREATION_BALANCE": selfAssessment(S.ACADEMIC_RECREATION_BALANCE),
  "self_assessment.HOLISTIC_PERSONAL_WELL_BEING": selfAssessment(S.HOLISTIC_PERSONAL_WELL_BEING),
  "self_assessment.INTEGRATE_KNOWLEDGE_EXPERIENCE": selfAssessment(S.INTEGRATE_KNOWLEDGE_EXPERIENCE),
  "self_assessment.CAREER_GOAL_CLARITY": selfAssessment(S.CAREER_GOAL_CLARITY),
  "self_assessment.SELF_ESTEEM": selfAssessment(S.SELF_ESTEEM),
  "self_assessment.SELF_AWARENESS": selfAssessment(S.SELF_AWARENESS),
  "self_assessment.COPE_WITH_PRESSURES": selfAssessment(S.COPE_WITH_PRESSURES),
  "self_assessment.DEAL_WITH_DIFFERENT_WALKS": selfAssessment(S.DEAL_WITH_DIFFERENT_WALKS),
  "self_assessment.LEADERSHIP": selfAssessment(S.LEADERSHIP),
  "self_assessment.COMMUNICATION_SKILLS": selfAssessment(S.COMMUNICATION_SKILLS),
  "self_assessment.CIVIC_MINDEDNESS": selfAssessment(S.CIVIC_MINDEDNESS),
  "self_assessment.INITIATIVE": selfAssessment(S.INITIATIVE),
  "self_assessment.DECISION_MAKING": selfAssessment(S.DECISION_MAKING),
  "self_assessment.RELATIONSHIP_WITH_GOD": selfAssessment(S.RELATIONSHIP_WITH_GOD),

  "section.college_feedback": sectionTarget("college_feedback"),
  "college_feedback.DEAN_AVAILABILITY": feedbackRating(C.DEAN_AVAILABILITY),
  "college_feedback.DEAN_OPEN_MINDEDNESS": feedbackRating(C.DEAN_OPEN_MINDEDNESS),
  "college_feedback.DEAN_CONCERN_FOR_STUDENTS": feedbackRating(C.DEAN_CONCERN_FOR_STUDENTS),
  "college_feedback.DEAN_COMMITMENT": feedbackRating(C.DEAN_COMMITMENT),
  "college_feedback.DEAN_APPROACHABILITY": feedbackRating(C.DEAN_APPROACHABILITY),
  "college_feedback.comments.dean": feedbackComment("deanComments", "DEAN_"),
  "college_feedback.PROGRAM_CHAIR_AVAILABILITY": feedbackRating(C.PROGRAM_CHAIR_AVAILABILITY),
  "college_feedback.PROGRAM_CHAIR_APPROACHABILITY": feedbackRating(C.PROGRAM_CHAIR_APPROACHABILITY),
  "college_feedback.PROGRAM_CHAIR_CONCERN_FOR_STUDENTS": feedbackRating(C.PROGRAM_CHAIR_CONCERN_FOR_STUDENTS),
  "college_feedback.comments.program_chair": feedbackComment("programChairComments", "PROGRAM_CHAIR_"),
  "college_feedback.FACULTY_AVAILABILITY": feedbackRating(C.FACULTY_AVAILABILITY),
  "college_feedback.FACULTY_APPROACHABILITY": feedbackRating(C.FACULTY_APPROACHABILITY),
  "college_feedback.FACULTY_KNOWLEDGE_SUBJECT_MATTER": feedbackRating(C.FACULTY_KNOWLEDGE_SUBJECT_MATTER),
  "college_feedback.FACULTY_TEACHING_SKILLS": feedbackRating(C.FACULTY_TEACHING_SKILLS),
  "college_feedback.comments.faculty": feedbackComment("facultyComments", "FACULTY_"),
  "college_feedback.CURRICULUM_RELEVANCE_SUBJECTS": feedbackRating(C.CURRICULUM_RELEVANCE_SUBJECTS),
  "college_feedback.CURRICULUM_SYSTEMATIC_SEQUENCING": feedbackRating(C.CURRICULUM_SYSTEMATIC_SEQUENCING),
  "college_feedback.CURRICULUM_COMPLETENESS": feedbackRating(C.CURRICULUM_COMPLETENESS),
  "college_feedback.comments.curriculum": feedbackComment("curriculumComments", "CURRICULUM_"),
  "college_feedback.GUIDANCE_COUNSELOR_AVAILABILITY": feedbackRating(C.GUIDANCE_COUNSELOR_AVAILABILITY),
  "college_feedback.GUIDANCE_COUNSELOR_APPROACHABILITY": feedbackRating(C.GUIDANCE_COUNSELOR_APPROACHABILITY),
  "college_feedback.GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS": feedbackRating(C.GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS),
  "college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY": feedbackRating(C.GUIDANCE_COUNSELOR_EFFICIENCY),
  "college_feedback.comments.guidance_counselor": feedbackComment("guidanceCounselorComments", "GUIDANCE_COUNSELOR_"),
  "college_feedback.OFFICE_STAFF_SERVICE_ORIENTED": feedbackRating(C.OFFICE_STAFF_SERVICE_ORIENTED),
  "college_feedback.OFFICE_STAFF_AVAILABILITY": feedbackRating(C.OFFICE_STAFF_AVAILABILITY),
  "college_feedback.OFFICE_STAFF_CONCERN_FOR_STUDENTS": feedbackRating(C.OFFICE_STAFF_CONCERN_FOR_STUDENTS),
  "college_feedback.OFFICE_STAFF_APPROACHABILITY": feedbackRating(C.OFFICE_STAFF_APPROACHABILITY),
  "college_feedback.comments.office_staff": feedbackComment("officeStaffComments", "OFFICE_STAFF_"),
  "college_feedback.FACILITIES_MAINTENANCE_CONDITION": feedbackRating(C.FACILITIES_MAINTENANCE_CONDITION),
  "college_feedback.FACILITIES_AVAILABILITY": feedbackRating(C.FACILITIES_AVAILABILITY),
  "college_feedback.FACILITIES_COMPLETENESS": feedbackRating(C.FACILITIES_COMPLETENESS),
  "college_feedback.comments.facilities": feedbackComment("facilitiesComments", "FACILITIES_"),

  "section.suggestions": sectionTarget("suggestions"),
  "suggestions.suggestions_recommendations": {
    section: "suggestions", group: "Suggestions / Recommendations", label: "Suggestions / Recommendations",
    title: "Suggestions / Recommendations", scope: "answer", anchor: "exit-suggestions-recommendations",
  },
} satisfies Record<ExitInterviewCorrectionTarget, Definition>;

// Catalog order, which the backend also stores and returns.
export const exitInterviewCorrectionTargetOrder: readonly ExitInterviewCorrectionTarget[] = Object.values(ExitInterviewCorrectionTarget);

// The backend's request limit (MAX_CORRECTION_TARGETS). The backend still enforces it.
export const MAX_EXIT_INTERVIEW_CORRECTION_TARGETS = 30;

export function isExitInterviewCorrectionTarget(value: string): value is ExitInterviewCorrectionTarget {
  return Object.hasOwn(exitInterviewCorrectionTargets, value);
}

// "College Feedback — Guidance Counselor — Efficiency". Never the code itself.
export function exitInterviewCorrectionTargetTitle(code: ExitInterviewCorrectionTarget): string {
  return exitInterviewCorrectionTargets[code].title;
}

// The targets that exist on one record's saved answer contract, mirroring the backend's
// allowed_correction_targets: a rating only when the record has that item (UCN F9 has no Program
// Chair items; a legacy null-revision record has all 26), and a comment only when its category has
// at least one of those items. The backend checks this again.
export function allowedExitInterviewCorrectionTargets(
  collegeFeedbackItemCodes: readonly string[],
): ExitInterviewCorrectionTarget[] {
  const items = new Set(collegeFeedbackItemCodes);
  return exitInterviewCorrectionTargetOrder.filter((code) => {
    const definition: Definition = exitInterviewCorrectionTargets[code];
    if (definition.feedbackItem) return items.has(definition.feedbackItem);
    if (definition.feedbackCategoryPrefix) {
      const prefix = definition.feedbackCategoryPrefix;
      return [...items].some((item) => item.startsWith(prefix));
    }
    return true;
  });
}

// Codes this build can name, in catalog order without repeats, and how many it could not. A build
// older than the backend may receive a newer code; it is never shown raw.
export function readExitInterviewCorrectionTargets(values: readonly string[] | null | undefined): {
  targets: ExitInterviewCorrectionTarget[];
  unknown: number;
} {
  const known = new Set<ExitInterviewCorrectionTarget>();
  let unknown = 0;
  for (const value of values ?? []) {
    if (isExitInterviewCorrectionTarget(value)) known.add(value);
    else unknown += 1;
  }
  return { targets: exitInterviewCorrectionTargetOrder.filter((code) => known.has(code)), unknown };
}

export function sortExitInterviewCorrectionTargets(values: Iterable<ExitInterviewCorrectionTarget>): ExitInterviewCorrectionTarget[] {
  const selected = new Set(values);
  return exitInterviewCorrectionTargetOrder.filter((code) => selected.has(code));
}

// --- Form hints ---------------------------------------------------------------------------------

export type ExitInterviewReviewHints = {
  // Hint text per host, rendered by that host as `${host}-review`.
  hints: ReadonlyMap<string, string>;
  // The hint ids each control or row adds to aria-describedby.
  describedBy: ReadonlyMap<string, string>;
  sections: ReadonlySet<ExitInterviewCorrectionSectionId>;
};

export const emptyExitInterviewReviewHints: ExitInterviewReviewHints = {
  hints: new Map(),
  describedBy: new Map(),
  sections: new Set(),
};

// Where each requested review shows in the form for the current answers. A delay detail that is
// hidden because Program completion changed is pointed out at Program completion instead.
export function exitInterviewReviewHints(
  targets: readonly ExitInterviewCorrectionTarget[],
  form: ExitInterviewFormState,
): ExitInterviewReviewHints {
  if (!targets.length) return emptyExitInterviewReviewHints;
  const hints = new Map<string, string[]>();
  const sections = new Set<ExitInterviewCorrectionSectionId>();
  const add = (host: string, text: string) => {
    const texts = hints.get(host) ?? [];
    if (!texts.includes(text)) texts.push(text);
    hints.set(host, texts);
  };
  for (const code of sortExitInterviewCorrectionTargets(targets)) {
    const definition: Definition = exitInterviewCorrectionTargets[code];
    if (definition.scope === "section") {
      sections.add(definition.section);
      continue;
    }
    const condition = definition.condition;
    if (!condition || condition.visible(form)) add(definition.anchor, exitInterviewReviewHintText.answer);
    else add(condition.fallback, condition.hint);
  }
  return {
    hints: new Map([...hints].map(([host, texts]) => [host, texts.join(" ")])),
    describedBy: new Map([...hints.keys()].map((host) => [host, exitInterviewReviewHintId(host)])),
    sections,
  };
}

// --- Navigation ---------------------------------------------------------------------------------

// Element ids to try, best first. The last is the section heading, so a target always leads
// somewhere even if its control cannot take focus (for example while the draft is saving).
export function exitInterviewCorrectionFocusOrder(code: ExitInterviewCorrectionTarget, form: ExitInterviewFormState): string[] {
  const definition: Definition = exitInterviewCorrectionTargets[code];
  const heading = exitInterviewCorrectionSections.find((item) => item.id === definition.section)!.headingId;
  const condition = definition.condition;
  const order = condition && !condition.visible(form) ? [condition.fallback] : [definition.anchor, ...(condition ? [condition.fallback] : [])];
  return [...order, heading];
}

const focusableSelector = "input:not(:disabled), select:not(:disabled), textarea:not(:disabled), button:not(:disabled)";

function focusTargetWithin(element: HTMLElement): HTMLElement | null {
  if (element.matches("input, select, textarea, button, [tabindex]")) return element;
  // A radio group or rating row is entered at its checked answer, as the Tab key would, so the
  // saved value (including 0) is what the Student lands on.
  return element.querySelector<HTMLElement>('input[type="radio"]:checked:not(:disabled)')
    ?? element.querySelector<HTMLElement>(focusableSelector)
    ?? (element.matches("h2, h3") ? element : null);
}

// Scrolls the target into view and moves focus to it. Never changes an answer. Returns the id that
// received focus.
export function focusExitInterviewCorrectionTarget(ids: readonly string[], root: Document = document): string | null {
  let scrolled = false;
  for (const id of ids) {
    const element = root.getElementById(id);
    if (!element) continue;
    const target = focusTargetWithin(element);
    // A section heading takes programmatic focus only.
    if (target && target.matches("h2, h3") && !target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    if (!scrolled) {
      element.scrollIntoView({ block: "center" });
      scrolled = true;
    }
    target?.focus({ preventScroll: true });
    if (target && root.activeElement === target) return id;
  }
  return null;
}
