import type {
  GraduateTracerDetailResponse,
  GraduateTracerDraftPayload,
  GraduateTracerEducationPayload,
  GraduateTracerProfessionalExamPayload,
  GraduateTracerTrainingPayload,
  GTSAdvancedStudyReasonValue,
  GTSBusinessLineValue,
  GTSCivilStatusValue,
  GTSDegreeReasonValue,
  GTSEarningBracketValue,
  GTSEmploymentStateValue,
  GTSFirstJobDurationValue,
  GTSFirstJobSourceValue,
  GTSJobLevelValue,
  GTSJobReasonValue,
  GTSPlaceOfWorkValue,
  GTSPresentEmploymentStatusValue,
  GTSRegionOfOriginValue,
  GTSResidenceLocationValue,
  GTSSexValue,
  GTSStayingReasonValue,
  GTSUnemploymentReasonValue,
  GTSUsefulCompetencyValue,
} from "@/lib/api/generated/model";
import {
  GTSAdvancedStudyReasonValue as AdvancedStudyReason,
  GTSBusinessLineValue as BusinessLine,
  GTSCivilStatusValue as CivilStatus,
  GTSDegreeReasonValue as DegreeReason,
  GTSEarningBracketValue as EarningBracket,
  GTSEmploymentStateValue as EmploymentState,
  GTSFirstJobDurationValue as FirstJobDuration,
  GTSFirstJobSourceValue as FirstJobSource,
  GTSJobLevelValue as JobLevel,
  GTSJobReasonValue as JobReason,
  GTSPlaceOfWorkValue as PlaceOfWork,
  GTSPresentEmploymentStatusValue as PresentEmploymentStatus,
  GTSRegionOfOriginValue as RegionOfOrigin,
  GTSResidenceLocationValue as ResidenceLocation,
  GTSSexValue as Sex,
  GTSStayingReasonValue as StayingReason,
  GTSUnemploymentReasonValue as UnemploymentReason,
  GTSUsefulCompetencyValue as UsefulCompetency,
} from "@/lib/api/generated/model";

export type GraduateTracerFormDraft = Omit<
  GraduateTracerDraftPayload,
  "education" | "professional_exams" | "trainings"
> & {
  education: EducationFormRow[];
  professional_exams: ProfessionalExamFormRow[];
  trainings: TrainingFormRow[];
};

export type EducationFormRow = Omit<GraduateTracerEducationPayload, "year_graduated"> & {
  year_graduated: string;
  formKey: string;
};

export type ProfessionalExamFormRow = GraduateTracerProfessionalExamPayload & { formKey: string };
export type TrainingFormRow = GraduateTracerTrainingPayload & { formKey: string };

export type Choice<T extends string> = { value: T; label: string };

export const CIVIL_STATUS_CHOICES: Choice<GTSCivilStatusValue>[] = [
  { value: CivilStatus.SINGLE, label: "Single" },
  { value: CivilStatus.SEPARATED, label: "Separated" },
  { value: CivilStatus.WIDOW_WIDOWER, label: "Widow or Widower" },
  { value: CivilStatus.MARRIED, label: "Married" },
  { value: CivilStatus.SINGLE_PARENT, label: "Single Parent" },
];

export const SEX_CHOICES: Choice<GTSSexValue>[] = [
  { value: Sex.MALE, label: "Male" },
  { value: Sex.FEMALE, label: "Female" },
];

export const REGION_CHOICES: Choice<GTSRegionOfOriginValue>[] = [
  { value: RegionOfOrigin.REGION_1, label: "Region 1" },
  { value: RegionOfOrigin.REGION_2, label: "Region 2" },
  { value: RegionOfOrigin.REGION_3, label: "Region 3" },
  { value: RegionOfOrigin.REGION_4, label: "Region 4" },
  { value: RegionOfOrigin.REGION_5, label: "Region 5" },
  { value: RegionOfOrigin.REGION_6, label: "Region 6" },
  { value: RegionOfOrigin.REGION_7, label: "Region 7" },
  { value: RegionOfOrigin.REGION_8, label: "Region 8" },
  { value: RegionOfOrigin.REGION_9, label: "Region 9" },
  { value: RegionOfOrigin.REGION_10, label: "Region 10" },
  { value: RegionOfOrigin.REGION_11, label: "Region 11" },
  { value: RegionOfOrigin.REGION_12, label: "Region 12" },
  { value: RegionOfOrigin.NCR, label: "NCR" },
  { value: RegionOfOrigin.CAR, label: "CAR" },
  { value: RegionOfOrigin.ARMM, label: "ARMM" },
  { value: RegionOfOrigin.CARAGA, label: "CARAGA" },
];

export const RESIDENCE_LOCATION_CHOICES: Choice<GTSResidenceLocationValue>[] = [
  { value: ResidenceLocation.CITY, label: "City" },
  { value: ResidenceLocation.MUNICIPALITY, label: "Municipality" },
];

export const DEGREE_REASON_CHOICES: Choice<GTSDegreeReasonValue>[] = [
  { value: DegreeReason.HIGH_GRADES_RELATED_COURSE, label: "High grades in the course or subject area(s) related to the course" },
  { value: DegreeReason.GOOD_GRADES_HIGH_SCHOOL, label: "Good grades in high school" },
  { value: DegreeReason.PARENTS_RELATIVES, label: "Influence of parents or relatives" },
  { value: DegreeReason.PEER_INFLUENCE, label: "Peer Influence" },
  { value: DegreeReason.ROLE_MODEL, label: "Inspired by a role model" },
  { value: DegreeReason.PASSION_PROFESSION, label: "Strong passion for the profession" },
  { value: DegreeReason.IMMEDIATE_EMPLOYMENT, label: "Prospect for immediate employment" },
  { value: DegreeReason.STATUS_PRESTIGE, label: "Status or prestige of the profession" },
  { value: DegreeReason.COURSE_AVAILABILITY, label: "Availability of course offering in chosen institution" },
  { value: DegreeReason.CAREER_ADVANCEMENT, label: "Prospect of career advancement" },
  { value: DegreeReason.AFFORDABLE, label: "Affordable for the family" },
  { value: DegreeReason.ATTRACTIVE_COMPENSATION, label: "Prospect of attractive compensation" },
  { value: DegreeReason.EMPLOYMENT_ABROAD, label: "Opportunity for employment abroad" },
  { value: DegreeReason.NO_PARTICULAR_CHOICE, label: "No particular choice or no better idea" },
];

export const ADVANCED_STUDY_REASON_CHOICES: Choice<GTSAdvancedStudyReasonValue>[] = [
  { value: AdvancedStudyReason.PROMOTION, label: "For promotion" },
  { value: AdvancedStudyReason.PROFESSIONAL_DEVELOPMENT, label: "For professional development" },
  { value: AdvancedStudyReason.OTHER, label: "Others" },
];

export const EMPLOYMENT_STATE_CHOICES: Choice<GTSEmploymentStateValue>[] = [
  { value: EmploymentState.EMPLOYED, label: "Yes" },
  { value: EmploymentState.NOT_EMPLOYED, label: "No" },
  { value: EmploymentState.NEVER_EMPLOYED, label: "Never Employed" },
];

export const UNEMPLOYMENT_REASON_CHOICES: Choice<GTSUnemploymentReasonValue>[] = [
  { value: UnemploymentReason.ADVANCE_STUDY, label: "Advance or further study" },
  { value: UnemploymentReason.FAMILY_CONCERN, label: "Family concern and decided not to find a job" },
  { value: UnemploymentReason.HEALTH_RELATED, label: "Health-related reason(s)" },
  { value: UnemploymentReason.LACK_WORK_EXPERIENCE, label: "Lack of work experience" },
  { value: UnemploymentReason.NO_JOB_OPPORTUNITY, label: "No job opportunity" },
  { value: UnemploymentReason.DID_NOT_LOOK, label: "Did not look for a job" },
  { value: UnemploymentReason.OTHER, label: "Other reason(s)" },
];

export const PRESENT_EMPLOYMENT_STATUS_CHOICES: Choice<GTSPresentEmploymentStatusValue>[] = [
  { value: PresentEmploymentStatus.REGULAR_PERMANENT, label: "Regular or Permanent" },
  { value: PresentEmploymentStatus.TEMPORARY, label: "Temporary" },
  { value: PresentEmploymentStatus.CASUAL, label: "Casual" },
  { value: PresentEmploymentStatus.CONTRACTUAL, label: "Contractual" },
  { value: PresentEmploymentStatus.SELF_EMPLOYED, label: "Self-employed" },
];

export const BUSINESS_LINE_CHOICES: Choice<GTSBusinessLineValue>[] = [
  { value: BusinessLine.AGRICULTURE_HUNTING_FORESTRY, label: "Agriculture, Hunting and Forestry" },
  { value: BusinessLine.FISHING, label: "Fishing" },
  { value: BusinessLine.MINING_QUARRYING, label: "Mining and Quarrying" },
  { value: BusinessLine.MANUFACTURING, label: "Manufacturing" },
  { value: BusinessLine.ELECTRICITY_GAS_WATER, label: "Electricity, Gas and Water Supply" },
  { value: BusinessLine.CONSTRUCTION, label: "Construction" },
  { value: BusinessLine.WHOLESALE_RETAIL_REPAIR, label: "Wholesale and Retail Trade, repair of motor vehicles, motorcycles and personal and household goods" },
  { value: BusinessLine.HOTELS_RESTAURANTS, label: "Hotels and Restaurants" },
  { value: BusinessLine.TRANSPORT_STORAGE_COMMUNICATION, label: "Transport Storage and Communication" },
  { value: BusinessLine.FINANCIAL_INTERMEDIATION, label: "Financial Intermediation" },
  { value: BusinessLine.REAL_ESTATE_RENTING_BUSINESS, label: "Real Estate, Renting and Business Activities" },
  { value: BusinessLine.PUBLIC_ADMIN_DEFENSE_SOCIAL_SECURITY, label: "Public Administration and Defense; Compulsory Social Security" },
  { value: BusinessLine.EDUCATION, label: "Education" },
  { value: BusinessLine.HEALTH_SOCIAL_WORK, label: "Health and Social Work" },
  { value: BusinessLine.OTHER_COMMUNITY_SOCIAL_PERSONAL, label: "Other Community, Social and Personal Service Activities" },
  { value: BusinessLine.PRIVATE_HOUSEHOLDS_EMPLOYED_PERSONS, label: "Private Households with Employed Persons" },
  { value: BusinessLine.EXTRA_TERRITORIAL_ORGANIZATIONS, label: "Extra-territorial Organizations and Bodies" },
];

export const PLACE_OF_WORK_CHOICES: Choice<GTSPlaceOfWorkValue>[] = [
  { value: PlaceOfWork.LOCAL, label: "Local" },
  { value: PlaceOfWork.ABROAD, label: "Abroad" },
];

export const STAYING_REASON_CHOICES: Choice<GTSStayingReasonValue>[] = [
  { value: StayingReason.SALARIES_BENEFITS, label: "Salaries and benefits" },
  { value: StayingReason.CAREER_CHALLENGE, label: "Career challenge" },
  { value: StayingReason.RELATED_SPECIAL_SKILL, label: "Related to special skill" },
  { value: StayingReason.RELATED_COURSE, label: "Related to course or program of study" },
  { value: StayingReason.PROXIMITY_RESIDENCE, label: "Proximity to residence" },
  { value: StayingReason.PEER_INFLUENCE, label: "Peer influence" },
  { value: StayingReason.FAMILY_INFLUENCE, label: "Family influence" },
  { value: StayingReason.OTHER, label: "Other reason(s)" },
];

export const JOB_REASON_CHOICES: Choice<GTSJobReasonValue>[] = [
  { value: JobReason.SALARIES_BENEFITS, label: "Salaries & benefits" },
  { value: JobReason.CAREER_CHALLENGE, label: "Career challenge" },
  { value: JobReason.RELATED_SPECIAL_SKILLS, label: "Related to special skills" },
  { value: JobReason.PROXIMITY_RESIDENCE, label: "Proximity to residence" },
  { value: JobReason.OTHER, label: "Other" },
];

export const FIRST_JOB_DURATION_CHOICES: Choice<GTSFirstJobDurationValue>[] = [
  { value: FirstJobDuration.LESS_THAN_MONTH, label: "Less than a month" },
  { value: FirstJobDuration.ONE_TO_SIX_MONTHS, label: "1 to 6 months" },
  { value: FirstJobDuration.SEVEN_TO_ELEVEN_MONTHS, label: "7 to 11 months" },
  { value: FirstJobDuration.ONE_TO_LT_TWO_YEARS, label: "1 year to less than 2 years" },
  { value: FirstJobDuration.TWO_TO_LT_THREE_YEARS, label: "2 years to less than 3 years" },
  { value: FirstJobDuration.THREE_TO_LT_FOUR_YEARS, label: "3 years to less than 4 years" },
  { value: FirstJobDuration.OTHER, label: "Others" },
];

export const FIRST_JOB_SOURCE_CHOICES: Choice<GTSFirstJobSourceValue>[] = [
  { value: FirstJobSource.ADVERTISEMENT, label: "Response to an advertisement" },
  { value: FirstJobSource.WALK_IN, label: "As walk-in applicant" },
  { value: FirstJobSource.RECOMMENDED, label: "Recommended by someone" },
  { value: FirstJobSource.FRIENDS, label: "Information from friends" },
  { value: FirstJobSource.SCHOOL_PLACEMENT, label: "Arranged by school's job placement officer" },
  { value: FirstJobSource.FAMILY_BUSINESS, label: "Family business" },
  { value: FirstJobSource.JOB_FAIR_PESO, label: "Job Fair or Public Employment Service Office (PESO)" },
  { value: FirstJobSource.OTHER, label: "Others" },
];

export const JOB_LEVEL_CHOICES: Choice<GTSJobLevelValue>[] = [
  { value: JobLevel.RANK_CLERICAL, label: "Rank or Clerical" },
  { value: JobLevel.PROFESSIONAL_TECHNICAL_SUPERVISORY, label: "Professional, Technical or Supervisory" },
  { value: JobLevel.MANAGERIAL_EXECUTIVE, label: "Managerial or Executive" },
  { value: JobLevel.SELF_EMPLOYED, label: "Self-employed" },
];

export const EARNING_BRACKET_CHOICES: Choice<GTSEarningBracketValue>[] = [
  { value: EarningBracket.BELOW_5000, label: "Below P5,000.00" },
  { value: EarningBracket.FROM_5000_TO_LT_10000, label: "P5,000.00 to less than P10,000.00" },
  { value: EarningBracket.FROM_10000_TO_LT_15000, label: "P10,000.00 to less than P15,000.00" },
  { value: EarningBracket.FROM_15000_TO_LT_20000, label: "P15,000.00 to less than P20,000.00" },
  { value: EarningBracket.FROM_20000_TO_LT_25000, label: "P20,000.00 to less than P25,000.00" },
  { value: EarningBracket.FROM_25000_UP, label: "P25,000.00 and above" },
];

export const USEFUL_COMPETENCY_CHOICES: Choice<GTSUsefulCompetencyValue>[] = [
  { value: UsefulCompetency.COMMUNICATION, label: "Communication skills" },
  { value: UsefulCompetency.HUMAN_RELATIONS, label: "Human Relations skills" },
  { value: UsefulCompetency.ENTREPRENEURIAL, label: "Entrepreneurial skills" },
  { value: UsefulCompetency.INFORMATION_TECHNOLOGY, label: "Information Technology skills" },
  { value: UsefulCompetency.PROBLEM_SOLVING, label: "Problem-solving skills" },
  { value: UsefulCompetency.CRITICAL_THINKING, label: "Critical Thinking skills" },
  { value: UsefulCompetency.OTHER, label: "Other skills" },
];

export const FORM_SECTIONS = [
  { id: "graduate-tracer-general", label: "A. General Information" },
  { id: "graduate-tracer-education", label: "B. Educational Background" },
  { id: "graduate-tracer-training", label: "C. Training / Advance Studies" },
  { id: "graduate-tracer-employment", label: "D. Employment Data" },
  { id: "graduate-tracer-curriculum", label: "Curriculum Suggestions" },
] as const;

export function graduateTracerDraftFromDetail(
  detail: GraduateTracerDetailResponse,
): GraduateTracerFormDraft {
  const {
    id,
    student_id,
    instrument_schema_version,
    status,
    created_at,
    updated_at,
    submitted_at,
    ...draft
  } = detail;
  void [id, student_id, instrument_schema_version, status, created_at, updated_at, submitted_at];

  return {
    ...draft,
    education: (detail.education ?? []).map((row, index) => ({
      ...row,
      year_graduated: String(row.year_graduated),
      formKey: `${detail.id}-education-${index}`,
    })),
    professional_exams: (detail.professional_exams ?? []).map((row, index) => ({
      ...row,
      date_taken: row.date_taken ?? "",
      rating: row.rating ?? "",
      formKey: `${detail.id}-exam-${index}`,
    })),
    trainings: (detail.trainings ?? []).map((row, index) => ({
      ...row,
      duration_and_credits: row.duration_and_credits ?? "",
      institution: row.institution ?? "",
      formKey: `${detail.id}-training-${index}`,
    })),
  };
}

export function graduateTracerPayloadFromDraft(
  draft: GraduateTracerFormDraft,
): GraduateTracerDraftPayload {
  return {
    ...draft,
    education: draft.education.map((row) => {
      const { formKey, ...payload } = row;
      void formKey;
      return { ...payload, year_graduated: Number(row.year_graduated) };
    }),
    professional_exams: draft.professional_exams.map((row) => {
      const { formKey, ...payload } = row;
      void formKey;
      return { ...payload, date_taken: row.date_taken?.trim() || null };
    }),
    trainings: draft.trainings.map((row) => {
      const { formKey, ...payload } = row;
      void formKey;
      return payload;
    }),
  };
}

export function normalizeGraduateTracerDraft(
  draft: GraduateTracerFormDraft,
): GraduateTracerFormDraft {
  const next = { ...draft };
  if (next.current_employment_state === EmploymentState.NOT_EMPLOYED || next.current_employment_state === EmploymentState.NEVER_EMPLOYED) {
    next.present_employment_status = undefined;
    next.self_employed_college_skills = undefined;
    next.present_occupation = undefined;
    next.employer_business_line = undefined;
    next.place_of_work = undefined;
    next.first_job_after_college = undefined;
    next.reasons_for_staying_on_job = [];
    next.reasons_for_staying_other = undefined;
    next.first_job_related_to_course = undefined;
    next.reasons_for_accepting_first_job = [];
    next.reasons_for_accepting_other = undefined;
    next.reasons_for_changing_job = [];
    next.reasons_for_changing_other = undefined;
    next.first_job_duration = undefined;
    next.first_job_duration_other = undefined;
    next.first_job_source = undefined;
    next.first_job_source_other = undefined;
    next.time_to_first_job = undefined;
    next.time_to_first_job_other = undefined;
    next.first_job_level = undefined;
    next.current_job_level = undefined;
    next.initial_gross_monthly_earning = undefined;
    next.curriculum_relevant_to_first_job = undefined;
    next.useful_competencies = [];
    next.useful_competencies_other = undefined;
  } else if (next.current_employment_state === EmploymentState.EMPLOYED) {
    next.unemployment_reasons = [];
    next.unemployment_other_reason = undefined;
  }

  if (next.present_employment_status !== PresentEmploymentStatus.SELF_EMPLOYED) {
    next.self_employed_college_skills = undefined;
  }

  if (next.first_job_after_college === false) {
    next.reasons_for_staying_on_job = [];
    next.reasons_for_staying_other = undefined;
    next.first_job_related_to_course = undefined;
    next.reasons_for_accepting_first_job = [];
    next.reasons_for_accepting_other = undefined;
  } else if (next.first_job_related_to_course === false) {
    next.reasons_for_accepting_first_job = [];
    next.reasons_for_accepting_other = undefined;
  }

  if (next.curriculum_relevant_to_first_job === false) {
    next.useful_competencies = [];
    next.useful_competencies_other = undefined;
  }

  if (!next.advanced_study_reasons?.includes(AdvancedStudyReason.OTHER)) next.advanced_study_other_reason = undefined;
  if (!next.unemployment_reasons?.includes(UnemploymentReason.OTHER)) next.unemployment_other_reason = undefined;
  if (!next.reasons_for_staying_on_job?.includes(StayingReason.OTHER)) next.reasons_for_staying_other = undefined;
  if (!next.reasons_for_accepting_first_job?.includes(JobReason.OTHER)) next.reasons_for_accepting_other = undefined;
  if (!next.reasons_for_changing_job?.includes(JobReason.OTHER)) next.reasons_for_changing_other = undefined;
  if (!next.useful_competencies?.includes(UsefulCompetency.OTHER)) next.useful_competencies_other = undefined;
  if (next.first_job_duration !== FirstJobDuration.OTHER) next.first_job_duration_other = undefined;
  if (next.time_to_first_job !== FirstJobDuration.OTHER) next.time_to_first_job_other = undefined;
  if (next.first_job_source !== FirstJobSource.OTHER) next.first_job_source_other = undefined;

  return next;
}

export function choiceLabel<T extends string>(
  value: T | null | undefined,
  choices: readonly Choice<T>[],
): string {
  if (!value) return "Not provided";
  return choices.find((choice) => choice.value === value)?.label ?? "Not provided";
}

export function choiceListLabel<T extends string>(
  values: readonly T[] | undefined,
  choices: readonly Choice<T>[],
): string {
  const labels = choices.filter((choice) => values?.includes(choice.value)).map((choice) => choice.label);
  return labels.length ? labels.join(", ") : "Not provided";
}

export function yesNoLabel(value: boolean | null | undefined): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Not provided";
}

export function formatGraduateTracerDate(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "Not provided";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(date);
}

export function formatGraduateTracerDateTime(value: string | null | undefined): string {
  if (!value) return "Not provided";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not provided";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function getGraduateTracerDraftRowIssues(draft: GraduateTracerFormDraft): string[] {
  const issues: string[] = [];
  draft.education.forEach((row, index) => {
    if (!row.degree_and_specialization.trim() || !row.college_or_university.trim() || !row.year_graduated.trim()) {
      issues.push(`Degree ${index + 1} needs a degree, college or university, and graduation year. Complete it or remove the row before saving.`);
      return;
    }
    const year = Number(row.year_graduated);
    if (!Number.isInteger(year) || year < 1900 || year > new Date().getFullYear()) {
      issues.push(`Degree ${index + 1} needs a valid graduation year from 1900 through the current year.`);
    }
  });
  draft.professional_exams.forEach((row, index) => {
    if (!row.examination_name.trim()) issues.push(`Examination ${index + 1} needs a name before saving.`);
    if (row.date_taken && row.date_taken > new Date().toISOString().slice(0, 10)) {
      issues.push(`Examination ${index + 1} date cannot be in the future.`);
    }
  });
  draft.trainings.forEach((row, index) => {
    if (!row.title.trim()) issues.push(`Training ${index + 1} needs a title before saving.`);
  });
  return issues;
}

export type SubmissionIssue = { section: string; message: string };

export function getGraduateTracerSubmissionIssues(draft: GraduateTracerFormDraft): SubmissionIssue[] {
  const issues: SubmissionIssue[] = [];
  const add = (section: string, message: string) => issues.push({ section, message });
  if (!draft.name?.trim()) add("graduate-tracer-general", "Enter your name.");
  if (!draft.civil_status) add("graduate-tracer-general", "Select your civil status.");
  if (!draft.sex) add("graduate-tracer-general", "Select your sex.");
  if (!draft.birth_date) add("graduate-tracer-general", "Enter your birthday.");
  else if (draft.birth_date > new Date().toISOString().slice(0, 10)) add("graduate-tracer-general", "Birthday cannot be in the future.");
  if (!draft.region_of_origin) add("graduate-tracer-general", "Select your region of origin.");
  if (!draft.province?.trim()) add("graduate-tracer-general", "Enter your province.");
  if (!draft.residence_location) add("graduate-tracer-general", "Select City or Municipality.");
  if (draft.email?.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft.email.trim())) add("graduate-tracer-general", "Enter a valid email address or leave the field blank.");

  if (draft.education.length === 0) add("graduate-tracer-education", "Add at least one baccalaureate degree.");
  if (draft.advanced_study_reasons?.includes(AdvancedStudyReason.OTHER) && !draft.advanced_study_other_reason?.trim()) add("graduate-tracer-training", "Specify the other reason for attending advance study.");
  if (draft.current_employment_state === EmploymentState.NOT_EMPLOYED || draft.current_employment_state === EmploymentState.NEVER_EMPLOYED) {
    if (!draft.unemployment_reasons?.length) add("graduate-tracer-employment", "Select at least one reason for not being employed.");
    if (draft.unemployment_reasons?.includes(UnemploymentReason.OTHER) && !draft.unemployment_other_reason?.trim()) add("graduate-tracer-employment", "Specify the other reason for not being employed.");
  } else if (draft.current_employment_state === EmploymentState.EMPLOYED) {
    if (!draft.present_employment_status) add("graduate-tracer-employment", "Select your present employment status.");
    if (draft.present_employment_status === PresentEmploymentStatus.SELF_EMPLOYED && !draft.self_employed_college_skills?.trim()) add("graduate-tracer-employment", "Describe the college skills you apply in your self-employed work.");
    if (!draft.present_occupation?.trim()) add("graduate-tracer-employment", "Enter your present occupation.");
    if (!draft.employer_business_line) add("graduate-tracer-employment", "Select the major line of business.");
    if (!draft.place_of_work) add("graduate-tracer-employment", "Select where you work.");
    if (draft.first_job_after_college === undefined || draft.first_job_after_college === null) add("graduate-tracer-employment", "Answer whether this is your first job after college.");
    if (draft.first_job_after_college === true) {
      if (!draft.reasons_for_staying_on_job?.length) add("graduate-tracer-employment", "Select at least one reason for staying on the job.");
      if (draft.reasons_for_staying_on_job?.includes(StayingReason.OTHER) && !draft.reasons_for_staying_other?.trim()) add("graduate-tracer-employment", "Specify the other reason for staying on the job.");
      if (draft.first_job_related_to_course === undefined || draft.first_job_related_to_course === null) add("graduate-tracer-employment", "Answer whether your first job was related to your college course.");
    }
    if (draft.reasons_for_accepting_first_job?.includes(JobReason.OTHER) && !draft.reasons_for_accepting_other?.trim()) add("graduate-tracer-employment", "Specify the other reason for accepting the first job.");
    if (draft.reasons_for_changing_job?.includes(JobReason.OTHER) && !draft.reasons_for_changing_other?.trim()) add("graduate-tracer-employment", "Specify the other reason for changing jobs.");
    if (!draft.first_job_duration) add("graduate-tracer-employment", "Select how long you stayed in your first job.");
    if (draft.first_job_duration === FirstJobDuration.OTHER && !draft.first_job_duration_other?.trim()) add("graduate-tracer-employment", "Specify the first-job duration.");
    if (!draft.first_job_source) add("graduate-tracer-employment", "Select how you found your first job.");
    if (draft.first_job_source === FirstJobSource.OTHER && !draft.first_job_source_other?.trim()) add("graduate-tracer-employment", "Specify how you found your first job.");
    if (!draft.time_to_first_job) add("graduate-tracer-employment", "Select how long it took to land your first job.");
    if (draft.time_to_first_job === FirstJobDuration.OTHER && !draft.time_to_first_job_other?.trim()) add("graduate-tracer-employment", "Specify how long it took to land your first job.");
    if (!draft.first_job_level || !draft.current_job_level) add("graduate-tracer-employment", "Select both first-job and current-job levels.");
    if (!draft.initial_gross_monthly_earning) add("graduate-tracer-employment", "Select the initial gross monthly earning bracket.");
    if (draft.curriculum_relevant_to_first_job === undefined || draft.curriculum_relevant_to_first_job === null) add("graduate-tracer-employment", "Answer whether your college curriculum was relevant to your first job.");
    if (draft.curriculum_relevant_to_first_job === true) {
      if (!draft.useful_competencies?.length) add("graduate-tracer-employment", "Select at least one useful competency.");
      if (draft.useful_competencies?.includes(UsefulCompetency.OTHER) && !draft.useful_competencies_other?.trim()) add("graduate-tracer-employment", "Specify the other useful competency.");
    }
  } else {
    add("graduate-tracer-employment", "Select your current employment state.");
  }
  return issues;
}
