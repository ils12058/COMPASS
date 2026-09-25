import type {
  ExitInterviewDetailResponse,
  ExitInterviewDraftPayload,
  SelfAssessmentItemValue as SelfAssessmentCode,
  CollegeFeedbackItemValue as CollegeFeedbackCode,
} from "@/lib/api/generated/model";
import {
  CareerModeValue,
  CollegeFeedbackItemValue,
  DelayReasonValue,
  ProgramCompletionValue,
  SelfAssessmentItemValue,
  SignificantLearningValue,
  StudyCareerChoiceValue,
  WorkCareerChoiceValue,
} from "@/lib/api/generated/model";

export const SELF_ASSESSMENT_ITEMS: readonly {
  code: SelfAssessmentCode;
  label: string;
}[] = [
  {
    code: SelfAssessmentItemValue.PRIDE_CONFIDENCE_CNSC,
    label: "Pride and confidence in being from CNSC",
  },
  {
    code: SelfAssessmentItemValue.ACADEMIC_RECREATION_BALANCE,
    label: "Ability to maintain balance between academics & recreational activities",
  },
  {
    code: SelfAssessmentItemValue.HOLISTIC_PERSONAL_WELL_BEING,
    label: "Awareness of the importance of holistic personal well-being",
  },
  {
    code: SelfAssessmentItemValue.INTEGRATE_KNOWLEDGE_EXPERIENCE,
    label: "Ability to integrate knowledge with experience",
  },
  { code: SelfAssessmentItemValue.CAREER_GOAL_CLARITY, label: "Clarity of career goals" },
  { code: SelfAssessmentItemValue.SELF_ESTEEM, label: "Self Esteem" },
  { code: SelfAssessmentItemValue.SELF_AWARENESS, label: "Self-Awareness" },
  { code: SelfAssessmentItemValue.COPE_WITH_PRESSURES, label: "Ability to cope with pressures" },
  {
    code: SelfAssessmentItemValue.DEAL_WITH_DIFFERENT_WALKS,
    label: "Ability to deal comfortably with people from different walks of life",
  },
  { code: SelfAssessmentItemValue.LEADERSHIP, label: "Leadership" },
  { code: SelfAssessmentItemValue.COMMUNICATION_SKILLS, label: "Communication Skills" },
  { code: SelfAssessmentItemValue.CIVIC_MINDEDNESS, label: "Civic Mindedness" },
  { code: SelfAssessmentItemValue.INITIATIVE, label: "Initiative" },
  { code: SelfAssessmentItemValue.DECISION_MAKING, label: "Decision Making" },
  { code: SelfAssessmentItemValue.RELATIONSHIP_WITH_GOD, label: "Relationship with God" },
];

export const COLLEGE_FEEDBACK_CATEGORIES: readonly {
  code: string;
  label: string;
  commentField:
    | "dean_comments"
    | "program_chair_comments"
    | "faculty_comments"
    | "curriculum_comments"
    | "guidance_counselor_comments"
    | "office_staff_comments"
    | "facilities_comments";
  commentKey:
    | "deanComments"
    | "programChairComments"
    | "facultyComments"
    | "curriculumComments"
    | "guidanceCounselorComments"
    | "officeStaffComments"
    | "facilitiesComments";
  commentLabel: string;
  items: readonly { code: CollegeFeedbackCode; label: string }[];
}[] = [
  {
    code: "DEAN",
    label: "Dean",
    commentField: "dean_comments",
    commentKey: "deanComments",
    commentLabel: "Comments about the Dean",
    items: [
      { code: CollegeFeedbackItemValue.DEAN_AVAILABILITY, label: "Availability" },
      { code: CollegeFeedbackItemValue.DEAN_OPEN_MINDEDNESS, label: "Open Mindedness" },
      { code: CollegeFeedbackItemValue.DEAN_CONCERN_FOR_STUDENTS, label: "Concern for Students" },
      { code: CollegeFeedbackItemValue.DEAN_COMMITMENT, label: "Commitment" },
      { code: CollegeFeedbackItemValue.DEAN_APPROACHABILITY, label: "Approachability" },
    ],
  },
  {
    code: "PROG CHAIR",
    label: "Program Chair",
    commentField: "program_chair_comments",
    commentKey: "programChairComments",
    commentLabel: "Comments about the Program Chair",
    items: [
      { code: CollegeFeedbackItemValue.PROGRAM_CHAIR_AVAILABILITY, label: "Availability" },
      { code: CollegeFeedbackItemValue.PROGRAM_CHAIR_APPROACHABILITY, label: "Approachability" },
      { code: CollegeFeedbackItemValue.PROGRAM_CHAIR_CONCERN_FOR_STUDENTS, label: "Concern for Students" },
    ],
  },
  {
    code: "FACULTY",
    label: "Faculty",
    commentField: "faculty_comments",
    commentKey: "facultyComments",
    commentLabel: "Comments about the Faculty",
    items: [
      { code: CollegeFeedbackItemValue.FACULTY_AVAILABILITY, label: "Availability" },
      { code: CollegeFeedbackItemValue.FACULTY_APPROACHABILITY, label: "Approachability" },
      { code: CollegeFeedbackItemValue.FACULTY_KNOWLEDGE_SUBJECT_MATTER, label: "Knowledge of subject matter" },
      { code: CollegeFeedbackItemValue.FACULTY_TEACHING_SKILLS, label: "Teaching Skills" },
    ],
  },
  {
    code: "CURRICULUM",
    label: "Curriculum",
    commentField: "curriculum_comments",
    commentKey: "curriculumComments",
    commentLabel: "Comments about the Curriculum",
    items: [
      { code: CollegeFeedbackItemValue.CURRICULUM_RELEVANCE_SUBJECTS, label: "Relevance of subjects" },
      { code: CollegeFeedbackItemValue.CURRICULUM_SYSTEMATIC_SEQUENCING, label: "Systematic Sequencing of Subjects" },
      { code: CollegeFeedbackItemValue.CURRICULUM_COMPLETENESS, label: "Completeness" },
    ],
  },
  {
    code: "GUIDANCE COUNSELOR",
    label: "Guidance Counselor",
    commentField: "guidance_counselor_comments",
    commentKey: "guidanceCounselorComments",
    commentLabel: "Comments about the Guidance Counselor",
    items: [
      { code: CollegeFeedbackItemValue.GUIDANCE_COUNSELOR_AVAILABILITY, label: "Availability" },
      { code: CollegeFeedbackItemValue.GUIDANCE_COUNSELOR_APPROACHABILITY, label: "Approachability" },
      { code: CollegeFeedbackItemValue.GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS, label: "Concern for Students" },
      { code: CollegeFeedbackItemValue.GUIDANCE_COUNSELOR_EFFICIENCY, label: "Efficiency" },
    ],
  },
  {
    code: "OFFICE STAFF",
    label: "Office Staff",
    commentField: "office_staff_comments",
    commentKey: "officeStaffComments",
    commentLabel: "Comments about the Office Staff",
    items: [
      { code: CollegeFeedbackItemValue.OFFICE_STAFF_SERVICE_ORIENTED, label: "Service Oriented" },
      { code: CollegeFeedbackItemValue.OFFICE_STAFF_AVAILABILITY, label: "Availability" },
      { code: CollegeFeedbackItemValue.OFFICE_STAFF_CONCERN_FOR_STUDENTS, label: "Concern for Students" },
      { code: CollegeFeedbackItemValue.OFFICE_STAFF_APPROACHABILITY, label: "Approachability" },
    ],
  },
  {
    code: "FACILITIES",
    label: "Facilities",
    commentField: "facilities_comments",
    commentKey: "facilitiesComments",
    commentLabel: "Comments about the Facilities",
    items: [
      { code: CollegeFeedbackItemValue.FACILITIES_MAINTENANCE_CONDITION, label: "Maintenance and Condition" },
      { code: CollegeFeedbackItemValue.FACILITIES_AVAILABILITY, label: "Availability" },
      { code: CollegeFeedbackItemValue.FACILITIES_COMPLETENESS, label: "Completeness" },
    ],
  },
];

export const SELF_ASSESSMENT_SCALE = [
  { value: 5, label: "Much enhanced" },
  { value: 4, label: "Enhanced" },
  { value: 3, label: "No Difference" },
  { value: 2, label: "Became Worse" },
  { value: 1, label: "I don't know" },
] as const;

export const COLLEGE_FEEDBACK_SCALE = [
  { value: 5, label: "Highly Satisfactory" },
  { value: 4, label: "Satisfactory" },
  { value: 3, label: "Average" },
  { value: 2, label: "Unsatisfactory" },
  { value: 1, label: "Very Unsatisfactory" },
] as const;

export const DELAY_REASONS = [
  { value: DelayReasonValue.TRANSFEREE, label: "Transferee" },
  { value: DelayReasonValue.ACADEMIC_FAILURES, label: "Academic Failures" },
  { value: DelayReasonValue.OTHER, label: "Others (pls. specify)" },
] as const;

export const SIGNIFICANT_LEARNING_CHOICES = [
  { value: SignificantLearningValue.INDEPENDENCE, label: "Independence" },
  { value: SignificantLearningValue.INTERPERSONAL_RELATIONS, label: "Interpersonal Relations" },
  { value: SignificantLearningValue.INTELLECTUAL_GROWTH, label: "Intellectual Growth" },
  { value: SignificantLearningValue.SPIRITUAL_GROWTH, label: "Spiritual Growth" },
  { value: SignificantLearningValue.RESPONSIBILITY, label: "Responsibility" },
  { value: SignificantLearningValue.WORKING_UNDER_PRESSURE, label: "Working under pressure" },
  { value: SignificantLearningValue.TIME_MANAGEMENT, label: "Time Management" },
  { value: SignificantLearningValue.SETTING_PRIORITIES, label: "Setting priorities" },
  { value: SignificantLearningValue.OTHER, label: "Others, pls. specify" },
] as const;

export const WORK_CHOICES = [
  { value: WorkCareerChoiceValue.RELATED_FIELD, label: "in a field related to my course" },
  { value: WorkCareerChoiceValue.UNRELATED_FIELD, label: "in a field unrelated to my course" },
  { value: WorkCareerChoiceValue.FAMILY_BUSINESS, label: "work in a family business" },
  { value: WorkCareerChoiceValue.OWN_BUSINESS, label: "set up my own business" },
  { value: WorkCareerChoiceValue.WORK_ABROAD, label: "work abroad" },
  { value: WorkCareerChoiceValue.NO_DEFINITE_PLAN, label: "no definite career plan yet" },
] as const;

export const STUDY_CHOICES = [
  { value: StudyCareerChoiceValue.RELATED_FIELD, label: "in a field related to my course" },
  { value: StudyCareerChoiceValue.UNRELATED_FIELD, label: "in a field unrelated to my course" },
] as const;

export const CAREER_MODES = [
  { value: CareerModeValue.WORK, label: "Work" },
  { value: CareerModeValue.STUDY, label: "Study" },
] as const;

export type ExitInterviewFormState = {
  studentName: string;
  age: string;
  civilStatus: string;
  course: string;
  major: string;
  emailAddress: string;
  homeAddress: string;
  contactNumber: string;
  programCompletion: "" | (typeof ProgramCompletionValue)[keyof typeof ProgramCompletionValue];
  extraTermsCount: string;
  delayReasons: (typeof DelayReasonValue)[keyof typeof DelayReasonValue][];
  delayOther: string;
  significantLearningExperiences: (typeof SignificantLearningValue)[keyof typeof SignificantLearningValue][];
  significantLearningOther: string;
  careerModes: (typeof CareerModeValue)[keyof typeof CareerModeValue][];
  workChoices: (typeof WorkCareerChoiceValue)[keyof typeof WorkCareerChoiceValue][];
  studyChoices: (typeof StudyCareerChoiceValue)[keyof typeof StudyCareerChoiceValue][];
  selfRatings: Record<string, string>;
  collegeRatings: Record<string, string>;
  deanComments: string;
  programChairComments: string;
  facultyComments: string;
  curriculumComments: string;
  guidanceCounselorComments: string;
  officeStaffComments: string;
  facilitiesComments: string;
  suggestionsRecommendations: string;
};

function ratingValues<T extends { item_code: string; rating: number }>(
  rows: readonly T[],
  codes: readonly string[],
): Record<string, string> {
  const byCode = new Map(rows.map((row) => [row.item_code, String(row.rating)]));
  return Object.fromEntries(codes.map((code) => [code, byCode.get(code) ?? ""]));
}

export function exitInterviewFormFromDetail(
  detail: ExitInterviewDetailResponse,
): ExitInterviewFormState {
  const collegeCodes = COLLEGE_FEEDBACK_CATEGORIES.flatMap((category) =>
    category.items.map((item) => item.code),
  );

  return {
    studentName: detail.student_name ?? "",
    age: detail.age === null || detail.age === undefined ? "" : String(detail.age),
    civilStatus: detail.civil_status ?? "",
    course: detail.course ?? "",
    major: detail.major ?? "",
    emailAddress: detail.email_address ?? "",
    homeAddress: detail.home_address ?? "",
    contactNumber: detail.contact_number ?? "",
    programCompletion: detail.program_completion ?? "",
    extraTermsCount:
      detail.extra_terms_count === null || detail.extra_terms_count === undefined
        ? ""
        : String(detail.extra_terms_count),
    delayReasons: [...(detail.delay_reasons ?? [])],
    delayOther: detail.delay_other ?? "",
    significantLearningExperiences: [...(detail.significant_learning_experiences ?? [])],
    significantLearningOther: detail.significant_learning_other ?? "",
    careerModes: [...(detail.career_modes ?? [])],
    workChoices: [...(detail.work_choices ?? [])],
    studyChoices: [...(detail.study_choices ?? [])],
    selfRatings: ratingValues(
      detail.self_assessment_ratings,
      SELF_ASSESSMENT_ITEMS.map((item) => item.code),
    ),
    collegeRatings: ratingValues(detail.college_feedback_ratings, collegeCodes),
    deanComments: detail.dean_comments ?? "",
    programChairComments: detail.program_chair_comments ?? "",
    facultyComments: detail.faculty_comments ?? "",
    curriculumComments: detail.curriculum_comments ?? "",
    guidanceCounselorComments: detail.guidance_counselor_comments ?? "",
    officeStaffComments: detail.office_staff_comments ?? "",
    facilitiesComments: detail.facilities_comments ?? "",
    suggestionsRecommendations: detail.suggestions_recommendations ?? "",
  };
}

export function exitInterviewDraftPayload(
  form: ExitInterviewFormState,
): ExitInterviewDraftPayload {
  const delayIsApplicable = form.programCompletion === ProgramCompletionValue.WITH_SOME_DELAY;
  const hasDelayOther = delayIsApplicable && form.delayReasons.includes(DelayReasonValue.OTHER);
  const hasLearningOther = form.significantLearningExperiences.includes(SignificantLearningValue.OTHER);
  const hasWork = form.careerModes.includes(CareerModeValue.WORK);
  const hasStudy = form.careerModes.includes(CareerModeValue.STUDY);
  const collegeItems = COLLEGE_FEEDBACK_CATEGORIES.flatMap((category) => category.items);

  return {
    student_name: form.studentName,
    age: form.age.trim() ? Number(form.age) : null,
    civil_status: form.civilStatus,
    course: form.course,
    major: form.major,
    email_address: form.emailAddress,
    home_address: form.homeAddress,
    contact_number: form.contactNumber,
    program_completion: form.programCompletion || null,
    extra_terms_count:
      delayIsApplicable && form.extraTermsCount.trim()
        ? Number(form.extraTermsCount)
        : null,
    delay_reasons: delayIsApplicable ? [...form.delayReasons] : [],
    delay_other: hasDelayOther ? form.delayOther : "",
    significant_learning_experiences: [...form.significantLearningExperiences],
    significant_learning_other: hasLearningOther ? form.significantLearningOther : "",
    career_modes: [...form.careerModes],
    work_choices: hasWork ? [...form.workChoices] : [],
    study_choices: hasStudy ? [...form.studyChoices] : [],
    self_assessment_ratings: SELF_ASSESSMENT_ITEMS.flatMap(({ code }) => {
      const value = form.selfRatings[code];
      return value ? [{ item_code: code, rating: Number(value) }] : [];
    }),
    college_feedback_ratings: collegeItems.flatMap(({ code }) => {
      const value = form.collegeRatings[code];
      return value ? [{ item_code: code, rating: Number(value) }] : [];
    }),
    dean_comments: form.deanComments,
    program_chair_comments: form.programChairComments,
    faculty_comments: form.facultyComments,
    curriculum_comments: form.curriculumComments,
    guidance_counselor_comments: form.guidanceCounselorComments,
    office_staff_comments: form.officeStaffComments,
    facilities_comments: form.facilitiesComments,
    suggestions_recommendations: form.suggestionsRecommendations,
  };
}

export function answeredCount(items: readonly { code: string }[], values: Record<string, string>) {
  return items.reduce((count, item) => count + (values[item.code] ? 1 : 0), 0);
}

export function formatExitInterviewDateTime(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
