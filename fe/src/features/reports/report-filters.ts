import type {
  ReportsGetGraduateTracerParams,
  ReportsGetStudentProfileParams,
} from "@/lib/api/generated/model";

type SearchParamReader = {
  getAll(name: string): string[];
};

export type StudentProfileDraft = {
  academic_year_id: string;
  campus_id: string;
  college_id: string;
  program_id: string;
  year_level: string;
};

export type ParsedStudentProfileFilters = {
  draft: StudentProfileDraft;
  params: ReportsGetStudentProfileParams;
  errors: string[];
  valid: boolean;
};

export type GraduateTracerDraft = {
  submitted_from: string;
  submitted_to: string;
};

export type ParsedGraduateTracerFilters = {
  draft: GraduateTracerDraft;
  params: ReportsGetGraduateTracerParams;
  errors: string[];
  valid: boolean;
};

const UUID_PATTERN = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;

function readSingle(
  params: SearchParamReader,
  name: string,
  errors: string[],
): string {
  const values = params.getAll(name);
  if (values.length > 1) {
    errors.push("Use only one " + name.replaceAll("_", " ") + " value.");
  }
  return values[0] ?? "";
}

export function validateStudentProfileDraft(
  draft: StudentProfileDraft,
): ParsedStudentProfileFilters {
  const errors: string[] = [];
  const params: ReportsGetStudentProfileParams = {};

  for (const field of [
    "academic_year_id",
    "campus_id",
    "college_id",
    "program_id",
  ] as const) {
    const value = draft[field].trim();
    if (!value) continue;
    if (!UUID_PATTERN.test(value)) {
      errors.push(
        "Choose a valid " +
          field.replaceAll("_id", "").replaceAll("_", " ") +
          ".",
      );
      continue;
    }
    params[field] = value;
  }

  const yearLevel = draft.year_level.trim();
  if (yearLevel) {
    if (!/^(?:[1-9]|10)$/.test(yearLevel)) {
      errors.push("Year Level must be from 1 through 10.");
    } else {
      params.year_level = Number(yearLevel);
    }
  }

  return {
    draft,
    params: errors.length === 0 ? params : {},
    errors,
    valid: errors.length === 0,
  };
}

export function parseStudentProfileFilters(
  searchParams: SearchParamReader,
): ParsedStudentProfileFilters {
  const errors: string[] = [];
  const draft: StudentProfileDraft = {
    academic_year_id: readSingle(searchParams, "academic_year_id", errors),
    campus_id: readSingle(searchParams, "campus_id", errors),
    college_id: readSingle(searchParams, "college_id", errors),
    program_id: readSingle(searchParams, "program_id", errors),
    year_level: readSingle(searchParams, "year_level", errors),
  };
  const validated = validateStudentProfileDraft(draft);
  errors.push(...validated.errors);
  return {
    draft,
    params: errors.length === 0 ? validated.params : {},
    errors,
    valid: errors.length === 0,
  };
}

export function studentProfileFilterQuery(
  draft: StudentProfileDraft,
): string {
  const validated = validateStudentProfileDraft(draft);
  if (!validated.valid) return "";
  const params = new URLSearchParams();
  for (const key of [
    "academic_year_id",
    "campus_id",
    "college_id",
    "program_id",
    "year_level",
  ] as const) {
    const value = validated.params[key];
    if (value !== undefined) params.set(key, String(value));
  }
  return params.toString();
}

export function isValidDateOnly(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  if (!year || month < 1 || month > 12) return false;
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysPerMonth = [
    31,
    leapYear ? 29 : 28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
  ];
  return day >= 1 && day <= daysPerMonth[month - 1];
}

export function validateGraduateTracerDraft(
  draft: GraduateTracerDraft,
): ParsedGraduateTracerFilters {
  const errors: string[] = [];
  const submittedFrom = draft.submitted_from.trim();
  const submittedTo = draft.submitted_to.trim();
  if (submittedFrom && !isValidDateOnly(submittedFrom)) {
    errors.push("Enter a valid Submitted From date.");
  }
  if (submittedTo && !isValidDateOnly(submittedTo)) {
    errors.push("Enter a valid Submitted To date.");
  }
  if (
    isValidDateOnly(submittedFrom) &&
    isValidDateOnly(submittedTo) &&
    submittedFrom > submittedTo
  ) {
    errors.push("Submitted From must be on or before Submitted To.");
  }

  const params: ReportsGetGraduateTracerParams = {};
  if (submittedFrom && isValidDateOnly(submittedFrom)) {
    params.submitted_from = submittedFrom;
  }
  if (submittedTo && isValidDateOnly(submittedTo)) {
    params.submitted_to = submittedTo;
  }
  return {
    draft,
    params: errors.length === 0 ? params : {},
    errors,
    valid: errors.length === 0,
  };
}

export function parseGraduateTracerFilters(
  searchParams: SearchParamReader,
): ParsedGraduateTracerFilters {
  const errors: string[] = [];
  const draft: GraduateTracerDraft = {
    submitted_from: readSingle(searchParams, "submitted_from", errors),
    submitted_to: readSingle(searchParams, "submitted_to", errors),
  };
  const validated = validateGraduateTracerDraft(draft);
  errors.push(...validated.errors);
  return {
    draft,
    params: errors.length === 0 ? validated.params : {},
    errors,
    valid: errors.length === 0,
  };
}

export function graduateTracerFilterQuery(
  draft: GraduateTracerDraft,
): string {
  const validated = validateGraduateTracerDraft(draft);
  if (!validated.valid) return "";
  const params = new URLSearchParams();
  if (validated.params.submitted_from) {
    params.set("submitted_from", validated.params.submitted_from);
  }
  if (validated.params.submitted_to) {
    params.set("submitted_to", validated.params.submitted_to);
  }
  return params.toString();
}
