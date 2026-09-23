import {
  AnnualIncomeStatusValue,
  CivilStatusCategoryValue,
  CourseChoiceReasonValue,
  CurrentReligionCategoryValue,
  FamilyMemberKindValue,
  GeographicLocationKindValue,
  ImmunizationValue,
  InventoryStatusValue,
  LivingArrangementValue,
  OccupationCategoryValue,
  PostGraduationFieldValue,
  PWDStatusValue,
  TransportationFrequencyCategoryValue,
  type InventoryPayload,
  type InventoryResponse,
} from "@/lib/api/generated/model";
import type { InventorySectionId } from "@/features/inventory/inventory-presentation";

export type InventorySubmissionIssue = {
  section: InventorySectionId;
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

export function getInventorySubmissionIssues(
  input: InventoryPayload,
  activeProgramIds: ReadonlySet<string> | undefined,
): InventorySubmissionIssue[] {
  const payload = normalizeInventoryPayload(input);
  const issues: InventorySubmissionIssue[] = [];
  const add = (section: InventorySectionId, message: string) => issues.push({ section, message });

  if (!payload.sex) add("personal", "Choose a sex response.");
  if (!payload.date_of_birth) add("personal", "Enter a date of birth.");
  if (!payload.civil_status_category) add("personal", "Choose a civil-status response.");
  if (
    payload.civil_status_category === CivilStatusCategoryValue.OTHER &&
    !payload.civil_status?.trim()
  ) add("personal", "Describe the other civil-status response.");
  if (!payload.current_religion_category) add("personal", "Choose a current-religion response.");
  if (
    payload.current_religion_category === CurrentReligionCategoryValue.OTHER &&
    !payload.current_religion?.trim()
  ) add("personal", "Describe the current religion.");

  const currentLocation = (payload.geographic_locations ?? []).find(
    (location) => location.kind === GeographicLocationKindValue.CURRENT,
  );
  if (!currentLocation) {
    add("personal", "Choose a response for your current structured location.");
  } else if (
    !currentLocation.not_specified &&
    (!currentLocation.region_psgc_code || !currentLocation.city_municipality_psgc_code)
  ) {
    add("personal", "Select a region and city or municipality for your current location.");
  }

  if (!payload.parent_status_category) add("family", "Choose a parent-status category.");
  const support = payload.support_profile;
  if (!support?.four_ps_status) add("family", "Choose a 4Ps response.");
  if (!support?.indigenous_peoples_status) add("family", "Choose an Indigenous Peoples response.");
  if (!support?.mother_life_status) add("family", "Choose a response for your mother's life status.");
  if (!support?.father_life_status) add("family", "Choose a response for your father's life status.");

  for (const kind of [FamilyMemberKindValue.FATHER, FamilyMemberKindValue.MOTHER]) {
    const member = (payload.family_members ?? []).find((item) => item.kind === kind);
    const label = kind === FamilyMemberKindValue.FATHER ? "Father" : "Mother";
    if (!member?.occupation_category) {
      add("family", `Choose an occupation category for ${label.toLowerCase()}.`);
    }
    if (!member?.annual_income_status) {
      add("family", `Choose an annual-income response for ${label.toLowerCase()}.`);
    }
    if (
      member?.annual_income_status === AnnualIncomeStatusValue.REPORTED &&
      !member.annual_income_previous_year?.trim()
    ) {
      add("family", `Enter the reported previous-year income for ${label.toLowerCase()}.`);
    }
  }

  if (!payload.living_arrangement) add("health", "Choose a living arrangement.");
  if (!payload.pwd_status) add("health", "Choose a disability-status response.");
  if (payload.pwd_status === PWDStatusValue.PWD && !payload.physical_disadvantage?.trim()) {
    add("health", "Describe the physical disadvantage or accommodation context.");
  }
  if (
    (payload.immunizations ?? []).includes(ImmunizationValue.OTHER) &&
    !payload.immunization_other?.trim()
  ) add("health", "Describe the other immunization.");

  if (
    !payload.program_id ||
    (activeProgramIds !== undefined && !activeProgramIds.has(payload.program_id))
  ) {
    add("education", "Choose a currently active Program.");
  }
  if (!payload.year_level || payload.year_level < 1 || payload.year_level > 10) {
    add("education", "Choose a Year Level from 1 through 10.");
  }

  if (
    (payload.course_choice_reasons ?? []).includes(CourseChoiceReasonValue.OTHER) &&
    !payload.course_choice_other?.trim()
  ) add("interests", "Describe the other reason for your course choice.");
  if (
    payload.intended_work_field === PostGraduationFieldValue.OTHER &&
    !payload.intended_work_other?.trim()
  ) add("plans", "Describe the other intended work field.");

  return issues;
}

export function isInventorySubmitted(status: string): boolean {
  return status === InventoryStatusValue.SUBMITTED;
}
