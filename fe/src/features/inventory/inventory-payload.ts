import {
  AnnualIncomeStatusValue,
  CivilStatusCategoryValue,
  CourseChoiceReasonValue,
  CurrentReligionCategoryValue,
  FamilyMemberKindValue,
  GeographicLocationKindValue,
  ImmunizationValue,
  LivingArrangementValue,
  OccupationCategoryValue,
  PostGraduationFieldValue,
  PWDStatusValue,
  TransportationFrequencyCategoryValue,
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
    geographic_locations: (payload.geographic_locations ?? []).map((location) =>
      location.not_specified
        ? { kind: location.kind, not_specified: true }
        : location,
    ),
    family_members: (payload.family_members ?? []).map((member) => ({
      ...member,
      ...(member.annual_income_status === AnnualIncomeStatusValue.REPORTED
        ? {}
        : { annual_income_previous_year: null }),
      ...(member.occupation_category === OccupationCategoryValue.NONE ||
      member.occupation_category === OccupationCategoryValue.NOT_SPECIFIED
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
  if (next.pwd_status !== PWDStatusValue.PWD) {
    next.physical_disadvantage = "";
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

export function getInventorySubmissionIssues(
  input: InventoryPayload,
  activeProgramIds: ReadonlySet<string> | undefined,
  programs?: readonly ProgramSummary[],
): InventorySubmissionIssue[] {
  const payload = normalizeInventoryPayload(input);
  const issues: InventorySubmissionIssue[] = [];
  const add = (section: InventorySectionId, targetId: string, message: string) =>
    issues.push({ section, targetId, message });

  if (!payload.sex) add("personal", "inventory-sex", "Choose a sex response.");
  if (!payload.date_of_birth) add("personal", "inventory-date-of-birth", "Enter a date of birth.");
  if (!payload.civil_status_category) add("personal", "inventory-civil-status", "Choose a civil-status response.");
  if (
    payload.civil_status_category === CivilStatusCategoryValue.OTHER &&
    !payload.civil_status?.trim()
  ) add("personal", "inventory-civil-status-other", "Describe the other civil-status response.");
  if (!payload.current_religion_category) add("personal", "inventory-current-religion-category", "Choose a current-religion response.");
  if (
    payload.current_religion_category === CurrentReligionCategoryValue.OTHER &&
    !payload.current_religion?.trim()
  ) add("personal", "inventory-current-religion-other", "Describe the current religion.");

  const currentLocation = (payload.geographic_locations ?? []).find(
    (location) => location.kind === GeographicLocationKindValue.CURRENT,
  );
  if (!currentLocation) {
    add("personal", "inventory-current-location-choice", "Choose how to provide your current location.");
  } else if (!currentLocation.not_specified && !currentLocation.region_psgc_code) {
    add("personal", "inventory-current-region", "Select a region for your current location.");
  } else if (!currentLocation.not_specified && !currentLocation.city_municipality_psgc_code) {
    add("personal", "inventory-current-city", "Select a city or municipality for your current location.");
  }

  if (!payload.parent_status_category) add("family", "inventory-parent-status-category", "Choose a parent-status category.");
  const support = payload.support_profile;
  if (!support?.four_ps_status) add("family", "inventory-four-ps", "Choose a 4Ps response.");
  if (!support?.indigenous_peoples_status) add("family", "inventory-indigenous-peoples", "Choose an Indigenous Peoples response.");
  if (!support?.mother_life_status) add("family", "inventory-mother-life-status", "Choose a response for your mother's life status.");
  if (!support?.father_life_status) add("family", "inventory-father-life-status", "Choose a response for your father's life status.");

  for (const kind of [FamilyMemberKindValue.FATHER, FamilyMemberKindValue.MOTHER]) {
    const member = (payload.family_members ?? []).find((item) => item.kind === kind);
    const label = kind === FamilyMemberKindValue.FATHER ? "Father" : "Mother";
    const prefix = `inventory-family-${kind.toLowerCase()}`;
    if (!member?.occupation_category) {
      add("family", `${prefix}-occupation-category`, `Choose an occupation category for ${label.toLowerCase()}.`);
    }
    if (!member?.annual_income_status) {
      add("family", `${prefix}-income-status`, `Choose an annual-income response for ${label.toLowerCase()}.`);
    }
  }

  if (!payload.living_arrangement) add("health", "inventory-living-arrangement", "Choose a living arrangement.");
  if (!payload.pwd_status) add("health", "inventory-pwd-status", "Choose a disability-status response.");
  if (payload.pwd_status === PWDStatusValue.PWD && !payload.physical_disadvantage?.trim()) {
    add("health", "inventory-physical-disadvantage", "Describe the physical disadvantage or accommodation context.");
  }
  if (
    (payload.immunizations ?? []).includes(ImmunizationValue.OTHER) &&
    !payload.immunization_other?.trim()
  ) add("health", "inventory-immunization-other", "Describe the other immunization.");

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

  if (
    (payload.course_choice_reasons ?? []).includes(CourseChoiceReasonValue.OTHER) &&
    !payload.course_choice_other?.trim()
  ) add("interests", "inventory-course-choice-other", "Describe the other reason for your course choice.");
  for (const entry of payload.transportation_entries ?? []) {
    if (!entry.frequency_category) {
      const mode = (transportationModeLabels.get(entry.mode) ?? entry.mode).toLowerCase();
      add("organizations", `inventory-transport-${entry.mode.toLowerCase()}-frequency-category`, `Choose how often you use the ${mode}.`);
    }
  }

  if (
    payload.intended_work_field === PostGraduationFieldValue.OTHER &&
    !payload.intended_work_other?.trim()
  ) add("plans", "inventory-intended-work-other", "Describe the other intended work field.");

  // Every rule that blocks saving also blocks submission. List the issues in section order so the
  // review follows the form.
  const sectionOrder = (section: InventorySectionId) =>
    inventorySections.findIndex((item) => item.id === section);
  return [...issues, ...getInventoryDraftIssues(payload)].sort(
    (left, right) => sectionOrder(left.section) - sectionOrder(right.section),
  );
}
