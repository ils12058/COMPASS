import {
  AnnualIncomeStatusValue,
  CivilStatusCategoryValue,
  CourseChoiceReasonValue,
  CurrentReligionCategoryValue,
  EducationLevelValue,
  FamilyMemberKindValue,
  GeographicLocationKindValue,
  ImmunizationValue,
  LivingArrangementValue,
  OccupationCategoryValue,
  ParentLifeStatusValue,
  PostGraduationFieldValue,
  TransportationFrequencyCategoryValue,
  type FamilyMemberPayload,
  type ProgramSummary,
  type InventoryPayload,
  type InventoryResponse,
} from "@/lib/api/generated/model";
import { inventorySections, transportationModes, type InventorySectionId } from "@/features/inventory/inventory-presentation";
import { isFutureInstitutionalDateInput } from "@/lib/institutional-time";

export type InventorySubmissionIssue = {
  section: InventorySectionId;
  targetId: string;
  message: string;
};

export function toInventoryPayload(inventory: InventoryResponse): InventoryPayload {
  const {
    id,
    academic_year,
    status,
    program,
    form_revision,
    submitted_at,
    first_submitted_at,
    last_submitted_at,
    correction_pending,
    latest_correction,
    ...payload
  } = inventory;
  // These fields belong to the response envelope, not the writable payload.
  void [id, academic_year, status, program, form_revision, submitted_at, first_submitted_at, last_submitted_at, correction_pending, latest_correction];
  return payload;
}

export function normalizeInventoryPayload(payload: InventoryPayload): InventoryPayload {
  const next: InventoryPayload = {
    ...payload,
    geographic_locations: payload.geographic_locations ?? [],
    family_members: (payload.family_members ?? []).map((member) => ({
      ...member,
      ...(member.annual_income_status === AnnualIncomeStatusValue.REPORTED
        ? {}
        : { annual_income_previous_year: null }),
      ...(member.occupation_category === OccupationCategoryValue.NONE
        ? { occupation: "" }
        : {}),
    })),
    transportation_entries: (payload.transportation_entries ?? []).map((entry) => ({
      ...entry,
      ...(entry.frequency_category === TransportationFrequencyCategoryValue.OTHER
        ? {}
        : { frequency: "" }),
    })),
  };

  if (next.civil_status_category !== CivilStatusCategoryValue.OTHER) {
    next.civil_status = "";
  }
  if (next.current_religion_category !== CurrentReligionCategoryValue.OTHER) {
    next.current_religion = "";
  }
  if (next.living_arrangement !== LivingArrangementValue.BOARDING_HOUSE) {
    next.boarding_exclusive = null;
    next.boarding_landlord_name = "";
    next.boarding_address = "";
  }
  if (!(next.immunizations ?? []).includes(ImmunizationValue.OTHER)) {
    next.immunization_other = "";
  }
  if (!(next.course_choice_reasons ?? []).includes(CourseChoiceReasonValue.OTHER)) {
    next.course_choice_other = "";
  }
  if (next.intended_work_field !== PostGraduationFieldValue.OTHER) {
    next.intended_work_other = "";
  }
  if (next.prior_counseling_experience === false) {
    next.prior_counselor_name = "";
    next.prior_counseling_when = "";
    next.prior_counseling_where = "";
  }
  return next;
}

const familyMemberLabels: Record<FamilyMemberKindValue, string> = {
  [FamilyMemberKindValue.FATHER]: "Father",
  [FamilyMemberKindValue.MOTHER]: "Mother",
  [FamilyMemberKindValue.SPOUSE]: "Spouse",
};

const transportationModeLabels = new Map<string, string>(transportationModes);

const dailyHourFields = [
  ["daily_hours_class", "class"],
  ["daily_hours_library", "library work"],
  ["daily_hours_studying", "studying lessons"],
  ["daily_hours_rest", "rest"],
  ["daily_hours_recreation", "recreation"],
  ["daily_hours_other", "other activities"],
] as const;

// The largest value a PositiveSmallIntegerField or a small encrypted integer accepts.
const MAX_SMALL_COUNT = 32767;

type DecimalCheck = "ok" | "format" | "precision" | "range";

// Exact peso amounts and hours are kept to two decimal places. Report what is wrong with the typed
// text instead of rounding it, so the saved value is always the value the Student entered.
function checkDecimal(
  raw: string | number | null | undefined,
  { integerDigits, maximum }: { integerDigits: number; maximum?: number },
): DecimalCheck {
  const value = raw === null || raw === undefined ? "" : String(raw).trim();
  const match = /^(\d+)(?:\.(\d*))?$/.exec(value);
  if (!match) return "format";
  if ((match[2] ?? "").length > 2) return "precision";
  if (match[1].replace(/^0+(?=\d)/, "").length > integerDigits) return "range";
  if (maximum !== undefined && Number(value) > maximum) return "range";
  return "ok";
}

function isBlank(raw: string | number | null | undefined): boolean {
  return raw === null || raw === undefined || String(raw).trim() === "";
}

function isWholeCount(value: number | null | undefined): boolean {
  return value === null || value === undefined || (Number.isInteger(value) && value >= 0 && value <= MAX_SMALL_COUNT);
}

// Rules COMPASS enforces whenever the Inventory is saved, so they block saving a draft as well as
// submitting it. Birth dates are historical facts: any past date is accepted, a later one never is.
export function getInventoryDraftIssues(
  input: InventoryPayload,
  now = new Date(),
): InventorySubmissionIssue[] {
  const issues: InventorySubmissionIssue[] = [];
  const add = (section: InventorySectionId, targetId: string, message: string) =>
    issues.push({ section, targetId, message });

  if (input.date_of_birth && isFutureInstitutionalDateInput(input.date_of_birth, now)) {
    add("personal", "inventory-date-of-birth", "Date of birth cannot be in the future.");
  }

  for (const member of input.family_members ?? []) {
    const prefix = `inventory-family-${member.kind.toLowerCase()}`;
    const label = familyMemberLabels[member.kind];
    if (member.date_of_birth && isFutureInstitutionalDateInput(member.date_of_birth, now)) {
      add("family", `${prefix}-date-of-birth`, `${label}'s date of birth cannot be in the future.`);
    }
    if (member.annual_income_status !== AnnualIncomeStatusValue.REPORTED) continue;
    const amount = member.annual_income_previous_year;
    if (isBlank(amount)) {
      add("family", `${prefix}-income-amount`, `Enter the reported previous-year income for ${label.toLowerCase()}.`);
      continue;
    }
    const check = checkDecimal(amount, { integerDigits: 12 });
    if (check === "precision") {
      add("family", `${prefix}-income-amount`, `Use up to two decimal places for ${label.toLowerCase()}'s income.`);
    } else if (check === "range") {
      add("family", `${prefix}-income-amount`, `Enter a smaller amount for ${label.toLowerCase()}'s income.`);
    } else if (check === "format" || Number(amount) <= 0) {
      add("family", `${prefix}-income-amount`, `Enter an amount greater than ₱0 for ${label.toLowerCase()}'s income.`);
    }
  }

  (input.siblings ?? []).forEach((sibling, index) => {
    if (!isWholeCount(sibling.age)) {
      add("background", `inventory-sibling-${index}-age`, `Enter sibling ${index + 1}'s age as a whole number.`);
    }
  });

  if (!isWholeCount(input.present_place_people_count)) {
    add("health", "inventory-present-place-people", "Enter a whole number for the people in your present living place.");
  }
  if (!isWholeCount(input.room_sharing_people_count)) {
    add("health", "inventory-room-sharing-people", "Enter a whole number for the people sharing your room.");
  }

  for (const [key, activity] of dailyHourFields) {
    const hours = input[key];
    if (isBlank(hours)) continue;
    const check = checkDecimal(hours, { integerDigits: 2, maximum: 24 });
    if (check === "precision") {
      add("interests", `inventory-${key.replaceAll("_", "-")}`, `Use up to two decimal places for ${activity} hours.`);
    } else if (check !== "ok") {
      add("interests", `inventory-${key.replaceAll("_", "-")}`, `Enter ${activity} hours from 0 to 24.`);
    }
  }

  for (const entry of input.transportation_entries ?? []) {
    const prefix = `inventory-transport-${entry.mode.toLowerCase()}`;
    const mode = (transportationModeLabels.get(entry.mode) ?? entry.mode).toLowerCase();
    if (entry.frequency_category === TransportationFrequencyCategoryValue.OTHER && !entry.frequency?.trim()) {
      add("organizations", `${prefix}-frequency-other`, `Describe how often you use the ${mode}.`);
    }
    if (isBlank(entry.fare)) continue;
    const check = checkDecimal(entry.fare, { integerDigits: 8 });
    if (check === "precision") {
      add("organizations", `${prefix}-fare`, `Use up to two decimal places for the ${mode} fare.`);
    } else if (check === "range") {
      add("organizations", `${prefix}-fare`, `Enter a smaller ${mode} fare.`);
    } else if (check === "format") {
      add("organizations", `${prefix}-fare`, `Enter the ${mode} fare as ₱0 or more.`);
    }
  }

  return issues;
}

function isUnansweredChoice(value: string | null | undefined): boolean {
  return isBlank(value);
}

function isNoneAnswer(value: string | null | undefined): boolean {
  return typeof value === "string" && value.trim().toLowerCase() === "none";
}

const absentParentLifeStatuses = new Set<string>([
  ParentLifeStatusValue.DECEASED,
  ParentLifeStatusValue.UNKNOWN,
]);

const requiredEducationLevels = [
  [EducationLevelValue.ELEMENTARY, "elementary"],
  [EducationLevelValue.JUNIOR_HIGH, "junior high school"],
  [EducationLevelValue.SENIOR_HIGH, "senior high school"],
] as const;

// Every blank on the official F5 form is required at submission. Drafts keep their earlier, looser
// rules; a text answer may say "None" where that is truthful, but there is no opt-out choice.
export function getInventorySubmissionIssues(
  input: InventoryPayload,
  activeProgramIds: ReadonlySet<string> | undefined,
  programs?: readonly ProgramSummary[],
): InventorySubmissionIssue[] {
  const payload = normalizeInventoryPayload(input);
  const issues: InventorySubmissionIssue[] = [];
  const add = (section: InventorySectionId, targetId: string, message: string) =>
    issues.push({ section, targetId, message });
  const requireText = (
    section: InventorySectionId,
    targetId: string,
    value: string | number | null | undefined,
    message: string,
  ) => {
    if (isBlank(value)) add(section, targetId, message);
  };
  const requireChoice = (
    section: InventorySectionId,
    targetId: string,
    value: string | null | undefined,
    message: string,
  ) => {
    if (isUnansweredChoice(value)) add(section, targetId, message);
  };

  // Page 1 — personal data.
  requireText("personal", "inventory-full-name", payload.full_name, "Add your full name.");
  requireText("personal", "inventory-nickname", payload.nickname, "Add your nickname.");
  requireText("personal", "inventory-student-number", payload.student_number, "Add your student number.");
  requireText("personal", "inventory-date-of-birth", payload.date_of_birth, "Enter a date of birth.");
  requireText("personal", "inventory-place-of-birth", payload.place_of_birth, "Add your place of birth.");
  requireText("personal", "inventory-nationality", payload.nationality, "Add your nationality.");
  requireChoice("personal", "inventory-sex", payload.sex, "Choose a sex response.");
  requireText(
    "personal",
    "inventory-birth-order",
    payload.birth_order_among_siblings,
    "Add your birth order among siblings.",
  );
  requireChoice(
    "personal",
    "inventory-civil-status",
    payload.civil_status_category,
    "Choose a civil-status response.",
  );
  if (
    payload.civil_status_category === CivilStatusCategoryValue.OTHER &&
    !payload.civil_status?.trim()
  ) add("personal", "inventory-civil-status-other", "Describe the other civil-status response.");
  requireText("personal", "inventory-current-address", payload.current_address, "Add your current address.");
  requireText(
    "personal",
    "inventory-permanent-address",
    payload.permanent_address,
    "Add your permanent address.",
  );
  requireText("personal", "inventory-contact-number", payload.contact_number, "Add your contact number.");
  requireText("personal", "inventory-email", payload.email_address, "Add your email address.");
  requireText(
    "personal",
    "inventory-languages-home",
    payload.languages_spoken_at_home,
    "Add the languages spoken at home.",
  );
  requireText(
    "personal",
    "inventory-languages-fluent",
    payload.languages_most_fluent,
    "Add the languages you are most fluent in.",
  );
  requireText(
    "personal",
    "inventory-religion-birth",
    payload.religion_from_birth,
    "Add your religion from birth.",
  );
  requireChoice(
    "personal",
    "inventory-current-religion-category",
    payload.current_religion_category,
    "Choose a current-religion response.",
  );
  if (
    payload.current_religion_category === CurrentReligionCategoryValue.OTHER &&
    !payload.current_religion?.trim()
  ) add("personal", "inventory-current-religion-other", "Describe the current religion.");

  const currentLocation = (payload.geographic_locations ?? []).find(
    (location) => location.kind === GeographicLocationKindValue.CURRENT,
  );
  if (!currentLocation?.region_psgc_code) {
    add("personal", "inventory-current-region", "Choose your current region.");
  }
  if (!currentLocation?.city_municipality_psgc_code) {
    add("personal", "inventory-current-city", "Choose your current city or municipality.");
  }

  // Page 1 — family and support.
  if (!(payload.parent_statuses ?? []).length) {
    add("family", "inventory-parent-statuses", "Tick at least one circumstance that applies to your parents.");
  }
  requireText("family", "inventory-guardian-name", payload.guardian_name, "Add your guardian's name.");
  requireText(
    "family",
    "inventory-guardian-relationship",
    payload.guardian_relationship,
    "Add your guardian's relationship to you.",
  );
  requireText("family", "inventory-guardian-address", payload.guardian_address, "Add your guardian's address.");
  requireText(
    "family",
    "inventory-guardian-contact",
    payload.guardian_contact_number,
    "Add your guardian's contact number.",
  );
  requireText(
    "family",
    "inventory-emergency-name",
    payload.emergency_contact_name,
    "Add your emergency contact's name.",
  );
  requireText(
    "family",
    "inventory-emergency-number",
    payload.emergency_contact_number,
    "Add your emergency contact's number.",
  );

  const support = payload.support_profile;
  requireChoice("family", "inventory-four-ps", support?.four_ps_status, "Choose your 4Ps status.");
  requireChoice(
    "family",
    "inventory-indigenous-peoples",
    support?.indigenous_peoples_status,
    "Choose whether you are an Indigenous Peoples member.",
  );
  requireChoice(
    "family",
    "inventory-mother-life-status",
    support?.mother_life_status,
    "Choose whether your mother is living, deceased, or unknown.",
  );
  requireChoice(
    "family",
    "inventory-father-life-status",
    support?.father_life_status,
    "Choose whether your father is living, deceased, or unknown.",
  );

  const memberRequirements = (
    kind: FamilyMemberKindValue,
    member: FamilyMemberPayload | undefined,
    label: string,
  ) => {
    const prefix = `inventory-family-${kind.toLowerCase()}`;
    if (!member) {
      add(
        "family",
        kind === FamilyMemberKindValue.SPOUSE ? "inventory-spouse-add" : `${prefix}-name`,
        `Add your ${label.toLowerCase()}'s details.`,
      );
      return;
    }
    requireText("family", `${prefix}-name`, member.name, `Add your ${label.toLowerCase()}'s name.`);
    requireText(
      "family",
      `${prefix}-date-of-birth`,
      member.date_of_birth,
      `Add your ${label.toLowerCase()}'s date of birth.`,
    );
    requireText(
      "family",
      `${prefix}-place-of-birth`,
      member.place_of_birth,
      `Add your ${label.toLowerCase()}'s place of birth.`,
    );
    requireText(
      "family",
      `${prefix}-current-address`,
      member.current_address,
      `Add your ${label.toLowerCase()}'s current address.`,
    );
    requireText(
      "family",
      `${prefix}-permanent-address`,
      member.permanent_address,
      `Add your ${label.toLowerCase()}'s permanent address.`,
    );
    requireText(
      "family",
      `${prefix}-contact`,
      member.contact_number,
      `Add your ${label.toLowerCase()}'s contact number.`,
    );
    requireText(
      "family",
      `${prefix}-email`,
      member.email_address,
      `Add your ${label.toLowerCase()}'s email address. Write None if there is none.`,
    );
    requireText(
      "family",
      `${prefix}-education`,
      member.educational_attainment,
      `Add your ${label.toLowerCase()}'s educational attainment.`,
    );
    requireChoice(
      "family",
      `${prefix}-occupation-category`,
      member.occupation_category,
      `Choose your ${label.toLowerCase()}'s occupation.`,
    );
    if (member.occupation_category === OccupationCategoryValue.OTHER && !member.occupation?.trim()) {
      add("family", `${prefix}-occupation`, `Describe your ${label.toLowerCase()}'s occupation.`);
    }
    requireChoice(
      "family",
      `${prefix}-income-status`,
      member.annual_income_status,
      `Choose your ${label.toLowerCase()}'s annual income.`,
    );
    requireText(
      "family",
      `${prefix}-business-address`,
      member.business_address,
      `Add your ${label.toLowerCase()}'s business address. Write None if there is none.`,
    );
    requireText(
      "family",
      `${prefix}-business-telephone`,
      member.business_telephone,
      `Add your ${label.toLowerCase()}'s business telephone. Write None if there is none.`,
    );
    requireText(
      "family",
      `${prefix}-languages`,
      member.languages_spoken,
      `Add the languages your ${label.toLowerCase()} speaks.`,
    );
    requireText(
      "family",
      `${prefix}-religion-raised`,
      member.religion_raised_with,
      `Add the religion you were raised with by your ${label.toLowerCase()}.`,
    );
    requireText(
      "family",
      `${prefix}-current-religion`,
      member.current_religion,
      `Add your ${label.toLowerCase()}'s current religion.`,
    );
  };

  for (const kind of [FamilyMemberKindValue.FATHER, FamilyMemberKindValue.MOTHER]) {
    const lifeStatus =
      kind === FamilyMemberKindValue.FATHER
        ? support?.father_life_status
        : support?.mother_life_status;
    // A deceased or unknown-life-status parent's details cannot be truthfully answered.
    if (lifeStatus && absentParentLifeStatuses.has(lifeStatus)) continue;
    const member = (payload.family_members ?? []).find((item) => item.kind === kind);
    memberRequirements(
      kind,
      member,
      kind === FamilyMemberKindValue.FATHER ? "Father" : "Mother",
    );
  }
  if (payload.civil_status_category === CivilStatusCategoryValue.MARRIED) {
    const spouse = (payload.family_members ?? []).find(
      (item) => item.kind === FamilyMemberKindValue.SPOUSE,
    );
    memberRequirements(FamilyMemberKindValue.SPOUSE, spouse, "Spouse");
  }

  // Page 2 — siblings, unique features, living arrangement, health.
  const siblings = payload.siblings ?? [];
  if (!siblings.some((sibling) => sibling.is_self)) {
    add("background", "inventory-siblings", "Include yourself among your siblings.");
  }
  siblings.forEach((sibling, index) => {
    requireText(
      "background",
      `inventory-sibling-${index}-name`,
      sibling.name,
      "Add each sibling's name.",
    );
    requireChoice(
      "background",
      `inventory-sibling-${index}-sex`,
      sibling.sex,
      "Choose each sibling's sex.",
    );
    if (sibling.age === null || sibling.age === undefined) {
      add("background", `inventory-sibling-${index}-age`, "Add each sibling's age.");
    }
  });

  requireText(
    "background",
    "inventory-friends-in-school",
    payload.friends_in_school,
    "Add your friends in school.",
  );
  requireText(
    "background",
    "inventory-friends-outside-school",
    payload.friends_outside_school,
    "Add your friends outside school.",
  );
  requireText(
    "background",
    "inventory-special-interest",
    payload.special_interest,
    "Add your special interests.",
  );
  requireText(
    "background",
    "inventory-special-skills",
    payload.special_skills_talents,
    "Add your special skills or talents.",
  );
  requireText(
    "background",
    "inventory-hobbies",
    payload.hobbies_recreation,
    "Add your hobbies and recreation.",
  );
  requireText("background", "inventory-ambition", payload.ambition_goal, "Add your ambition or goal.");
  requireText(
    "background",
    "inventory-characteristics",
    payload.characteristics,
    "Add your characteristics.",
  );

  requireChoice(
    "health",
    "inventory-living-arrangement",
    payload.living_arrangement,
    "Choose a living arrangement.",
  );
  if (payload.present_place_people_count === null || payload.present_place_people_count === undefined) {
    add("health", "inventory-present-place-people", "Add how many people live in your present place.");
  }
  if (payload.room_sharing_people_count === null || payload.room_sharing_people_count === undefined) {
    add("health", "inventory-room-sharing-people", "Add how many people share your room.");
  }
  if (payload.living_arrangement === LivingArrangementValue.BOARDING_HOUSE) {
    if (payload.boarding_exclusive === null || payload.boarding_exclusive === undefined) {
      add("health", "inventory-boarding-exclusive", "Answer whether your boarding room is exclusive to you.");
    }
    requireText(
      "health",
      "inventory-boarding-landlord",
      payload.boarding_landlord_name,
      "Add your boarding-house landlord's name.",
    );
    requireText(
      "health",
      "inventory-boarding-address",
      payload.boarding_address,
      "Add your boarding-house address.",
    );
  }

  requireText(
    "health",
    "inventory-accidents",
    payload.accidents_experienced,
    "Describe the accidents you have experienced. Write None if none.",
  );
  if (!isNoneAnswer(payload.accidents_experienced)) {
    requireText(
      "health",
      "inventory-accidents-effect",
      payload.accidents_effect,
      "Describe the effect of the accidents you experienced.",
    );
  }
  requireText(
    "health",
    "inventory-operations",
    payload.operations_experienced,
    "Describe the operations you have experienced. Write None if none.",
  );
  if (!isNoneAnswer(payload.operations_experienced)) {
    requireText(
      "health",
      "inventory-operations-effect",
      payload.operations_effect,
      "Describe the effect of the operations you experienced.",
    );
  }
  requireText("health", "inventory-height", payload.height, "Add your height.");
  requireText("health", "inventory-weight", payload.weight, "Add your weight.");
  requireText(
    "health",
    "inventory-physical-disadvantage",
    payload.physical_disadvantage,
    "Describe any physical disadvantage. Write None if none.",
  );
  requireChoice("health", "inventory-pwd-status", payload.pwd_status, "Choose your PWD status.");
  requireText(
    "health",
    "inventory-illness-this-year",
    payload.illness_this_year,
    "List the illnesses you had this year. Write None if none.",
  );
  requireText(
    "health",
    "inventory-previous-illness",
    payload.previous_illness,
    "List your previous illnesses. Write None if none.",
  );
  if (
    (payload.immunizations ?? []).includes(ImmunizationValue.OTHER) &&
    !payload.immunization_other?.trim()
  ) add("health", "inventory-immunization-other", "Describe the other immunization.");

  // Page 2 — educational history and current study.
  for (const [level, label] of requiredEducationLevels) {
    const entry = (payload.education_entries ?? []).find((item) => item.level === level);
    const key = level.toLowerCase();
    requireText(
      "education",
      `inventory-education-${key}-school`,
      entry?.school_attended_address,
      `Add the school you attended for ${label} and its address.`,
    );
    requireText(
      "education",
      `inventory-education-${key}-years`,
      entry?.inclusive_years,
      `Add the inclusive years you attended ${label}.`,
    );
  }
  if (
    activeProgramIds !== undefined &&
    (!payload.program_id || !activeProgramIds.has(payload.program_id))
  ) {
    add("education", "inventory-program", "Choose a currently active program.");
  }
  if (!payload.year_level || payload.year_level < 1 || payload.year_level > 10) {
    add("education", "inventory-year-level", "Choose a Year Level from the available Program options.");
  } else {
    const selectedProgram = programs?.find((program) => program.id === payload.program_id);
    if (
      selectedProgram?.year_level_policy_status === "CONFIGURED" &&
      selectedProgram.applicable_year_levels &&
      !selectedProgram.applicable_year_levels.includes(payload.year_level)
    ) {
      add(
        "education",
        "inventory-year-level",
        "Choose a Year Level supported by the selected Program.",
      );
    }
  }
  if (payload.schedule_satisfied === null || payload.schedule_satisfied === undefined) {
    add(
      "education",
      "inventory-schedule-satisfied",
      "Answer whether you are satisfied with your present schedule.",
    );
  }
  if (payload.schedule_satisfied === false) {
    requireText(
      "education",
      "inventory-schedule-reason",
      payload.schedule_satisfaction_reason,
      "Explain why you are not satisfied with your present schedule.",
    );
  }

  // Page 3 — course choice, interests, perceptions, and plans.
  if (payload.course_first_choice === null || payload.course_first_choice === undefined) {
    add("interests", "inventory-course-first-choice", "Answer whether your enrolled course was your first choice.");
  }
  if (!(payload.course_choice_reasons ?? []).length) {
    add("interests", "inventory-course-choice-reasons", "Choose at least one reason for your course choice.");
  }
  if (
    (payload.course_choice_reasons ?? []).includes(CourseChoiceReasonValue.OTHER) &&
    !payload.course_choice_other?.trim()
  ) add("interests", "inventory-course-choice-other", "Describe the other reason for your course choice.");
  requireText(
    "interests",
    "inventory-lowest-subjects",
    payload.lowest_subjects_grades,
    "Add the subjects with your lowest grades and the grades you received.",
  );
  requireText(
    "interests",
    "inventory-highest-subjects",
    payload.highest_subjects_grades,
    "Add the subjects with your highest grades and the grades you received.",
  );
  requireText(
    "interests",
    "inventory-inclination-performing-arts",
    payload.inclination_performing_arts,
    "Add your inclination for the performing arts.",
  );
  requireText(
    "interests",
    "inventory-inclination-sports",
    payload.inclination_sports,
    "Add your inclination for sports.",
  );
  requireText(
    "interests",
    "inventory-inclination-leadership",
    payload.inclination_leadership,
    "Add your inclination for leadership.",
  );
  requireText(
    "interests",
    "inventory-other-skills-hobbies",
    payload.other_skills_hobbies,
    "Add your other skills and hobbies.",
  );
  requireText(
    "interests",
    "inventory-desired-extracurricular",
    payload.desired_extracurricular_activities,
    "Add the extracurricular activities you would like to join.",
  );
  requireText(
    "interests",
    "inventory-reading-preferences",
    payload.reading_preferences,
    "Add the books and magazines you enjoy reading. Write None if none.",
  );
  requireChoice("interests", "inventory-handedness", payload.handedness, "Choose your handedness.");
  for (const [key, activity] of dailyHourFields) {
    if (payload[key] === null || payload[key] === undefined) {
      add(
        "interests",
        `inventory-${key.replaceAll("_", "-")}`,
        `Add the hours you devote daily to ${activity}.`,
      );
    }
  }

  requireChoice(
    "plans",
    "inventory-ideal-allowance",
    payload.ideal_monthly_allowance,
    "Choose your ideal monthly allowance.",
  );
  requireChoice(
    "plans",
    "inventory-intended-work-field",
    payload.intended_work_field,
    "Choose your intended work field.",
  );
  if (
    payload.intended_work_field === PostGraduationFieldValue.OTHER &&
    !payload.intended_work_other?.trim()
  ) add("plans", "inventory-intended-work-other", "Describe the other intended work field.");
  if (payload.prior_counseling_experience === null || payload.prior_counseling_experience === undefined) {
    add("plans", "inventory-prior-counseling", "Answer whether you have had previous counseling.");
  }
  if (payload.prior_counseling_experience === true) {
    requireText(
      "plans",
      "inventory-prior-counselor",
      payload.prior_counselor_name,
      "Add your previous counselor's name.",
    );
    requireText(
      "plans",
      "inventory-prior-counseling-when",
      payload.prior_counseling_when,
      "Add when you had previous counseling.",
    );
    requireText(
      "plans",
      "inventory-prior-counseling-where",
      payload.prior_counseling_where,
      "Add where you had previous counseling.",
    );
  }
  requireText("plans", "inventory-current-concerns", payload.current_concerns, "Add your current concerns.");
  requireText("plans", "inventory-current-fears", payload.current_fears, "Add your current fears.");

  for (const entry of payload.transportation_entries ?? []) {
    if (isUnansweredChoice(entry.frequency_category)) {
      const mode = (transportationModeLabels.get(entry.mode) ?? entry.mode).toLowerCase();
      add("organizations", `inventory-transport-${entry.mode.toLowerCase()}-frequency-category`, `Choose how often you use the ${mode}.`);
    }
  }

  // Every rule that blocks saving also blocks submission. List the issues in section order so the
  // review follows the form.
  const sectionOrder = (section: InventorySectionId) =>
    inventorySections.findIndex((item) => item.id === section);
  return [...issues, ...getInventoryDraftIssues(payload)].sort(
    (left, right) => sectionOrder(left.section) - sectionOrder(right.section),
  );
}
