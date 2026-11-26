import { yearLevelLabel } from "@/lib/year-level";

export interface AcademicUnit {
  code: string;
  name: string;
}

export interface VerifiableStudentPlacement {
  college?: AcademicUnit | null;
  program?: AcademicUnit | null;
  year_level?: number | null;
}

export interface CourseYearBlockMismatch {
  programMismatch: boolean;
  yearLevelMismatch: boolean;
  detectedYearLevel: number | null;
  message: string;
}

const WORDED_YEARS: Record<string, number> = {
  first: 1,
  second: 2,
  third: 3,
  fourth: 4,
  fifth: 5,
  sixth: 6,
};

const ROMAN_YEARS: Record<string, number> = {
  II: 2,
  III: 3,
  IV: 4,
  V: 5,
};

const PROGRAM_NAME_STOPWORDS = new Set([
  "BACHELOR",
  "MASTER",
  "DOCTOR",
  "ASSOCIATE",
  "DIPLOMA",
  "OF",
  "IN",
  "THE",
  "AND",
  "FOR",
  "WITH",
  "MAJOR",
  "SCIENCE",
  "ARTS",
  "DEGREE",
  "PROGRAM",
  "COURSE",
]);

const NON_DEGREE_FOLLOWERS = new Set([
  "BLOCK",
  "BLK",
  "YEAR",
  "YR",
  "SECTION",
  "SEC",
  "SEM",
  "SEMESTER",
  "ROOM",
  "RM",
  "GROUP",
  "GRP",
]);

export function formatAcademicUnit(unit: AcademicUnit | null | undefined): string | null {
  if (!unit) return null;
  const code = unit.code.trim();
  const name = unit.name.trim();
  if (code && name && code.toUpperCase() !== name.toUpperCase()) {
    return `${code} — ${name}`;
  }
  return name || code || null;
}

export function formatStudentPlacementSummary(
  student: VerifiableStudentPlacement | null | undefined,
): string {
  if (!student) return "";
  const parts: string[] = [];
  const program = formatAcademicUnit(student.program);
  if (program) parts.push(program);
  if (student.year_level !== null && student.year_level !== undefined) {
    parts.push(yearLevelLabel(student.year_level));
  }
  return parts.join(" · ");
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function singleValue(values: Set<number>): number | null {
  return values.size === 1 ? [...values][0] : null;
}

export function extractTypedYearLevel(input: string): number | null {
  const trimmed = input.trim();
  if (!trimmed) return null;

  const explicit = new Set<number>();
  for (const match of trimmed.matchAll(/\b(1st|2nd|3rd|[4-9]th|10th)\s*(?:yr\.?|year)?\b/gi)) {
    const level = Number.parseInt(match[1], 10);
    if (level >= 1 && level <= 10) explicit.add(level);
  }
  for (const match of trimmed.matchAll(/\b(first|second|third|fourth|fifth|sixth)\s+(?:yr\.?|year)\b/gi)) {
    const level = WORDED_YEARS[match[1].toLowerCase()];
    if (level) explicit.add(level);
  }
  for (const match of trimmed.matchAll(/\b(?:year|yr\.?)\s*[-:#]?\s*([1-9]|10)\b/gi)) {
    const level = Number.parseInt(match[1], 10);
    if (level >= 1 && level <= 10) explicit.add(level);
  }
  if (explicit.size > 0) return singleValue(explicit);

  // Ignore numbers attached to block/section/room labels before reading compact year digits.
  const withoutLabels = trimmed.replace(
    /\b(?:block|blk|section|sec|room|rm|group|grp)\.?\s*[-:#]?\s*\d+\b/gi,
    " ",
  );

  const compact = new Set<number>();
  for (const match of withoutLabels.matchAll(
    /(?:^|[\s/\-,])([1-6])(?:\s*[-]?\s*[A-Za-z](?![A-Za-z])|(?=$|[\s/\-,]))/g,
  )) {
    compact.add(Number.parseInt(match[1], 10));
  }
  for (const match of withoutLabels.matchAll(
    /(?:^|[\s/\-])(II|III|IV|V)(?=$|[\s/\-,]|-[A-Za-z]\b)/g,
  )) {
    const level = ROMAN_YEARS[match[1]];
    if (level) compact.add(level);
  }

  return singleValue(compact);
}

function significantProgramWords(name: string): string[] {
  return name
    .toUpperCase()
    .split(/[^A-Z0-9]+/)
    .filter((word) => word.length >= 2 && !PROGRAM_NAME_STOPWORDS.has(word));
}

function inputMatchesProgram(input: string, program: AcademicUnit): boolean {
  const upper = input.toUpperCase();
  const code = program.code.trim().toUpperCase();
  const name = program.name.trim().toUpperCase();

  if (code) {
    // Exact code token (also allows compact form like BSIS3A).
    const codeToken = new RegExp(`(?<![A-Z0-9])${escapeRegex(code)}(?![A-Z])`);
    if (codeToken.test(upper)) return true;

    // Allow spaced/hyphenated degree prefix, e.g. "BS IS" or "BS-IT" for "BSIS"/"BSIT".
    if (/^(BS|BA|AB)[A-Z]{2,}$/.test(code)) {
      const prefix = code.slice(0, 2);
      const rest = code.slice(2);
      const spaced = new RegExp(
        `(?<![A-Z0-9])${prefix}[\\s-]+(?:IN\\s+)?${escapeRegex(rest)}[A-Z]*(?![A-Z])`,
      );
      if (spaced.test(upper)) return true;
    }

    // For hyphenated program codes like "BSBA-FM", accept "BSBA FM" or bare "BSBA" without a conflicting suffix.
    if (code.includes("-")) {
      const spacedCode = code.replace(/-/g, "[\\s-]+");
      if (new RegExp(`(?<![A-Z0-9])${spacedCode}(?![A-Z])`).test(upper)) return true;
      const base = code.split("-")[0];
      const baseOnly = new RegExp(`(?<![A-Z0-9])${escapeRegex(base)}(?![A-Z-])`);
      if (baseOnly.test(upper)) return true;
    }
  }

  if (name) {
    const normalizedInput = upper.replace(/[^A-Z0-9]+/g, " ").trim();
    const normalizedName = name.replace(/[^A-Z0-9]+/g, " ").trim();
    if (normalizedName && normalizedInput.includes(normalizedName)) return true;

    const words = significantProgramWords(name);
    if (words.length > 0) {
      const inputWords = normalizedInput.split(/\s+/);
      const allPresent = words.every((word) =>
        inputWords.some(
          (candidate) =>
            candidate === word ||
            (candidate.length >= 4 && word.startsWith(candidate)) ||
            (word.length >= 4 && candidate.startsWith(word)),
        ),
      );
      if (allPresent) return true;
    }
  }

  return false;
}

function hasExplicitDegreeMention(input: string, college: AcademicUnit | null | undefined): boolean {
  const upper = input.toUpperCase();
  const collegeCode = college?.code.trim().toUpperCase() || "";

  // Full degree phrasing like "Bachelor of Science in Civil Engineering".
  if (/\b(?:BACHELOR|MASTER|DOCTOR|ASSOCIATE)\s+(?:OF|IN)\s+[A-Z]{2,}/.test(upper)) {
    return true;
  }

  // Spaced prefix forms like "BS Nursing", "BS IT", "BA English", "AB Political".
  for (const match of upper.matchAll(/\b(?:BS|BA|AB)\s+(?:IN\s+)?([A-Z]{2,16})\b/g)) {
    const follower = match[1];
    if (!NON_DEGREE_FOLLOWERS.has(follower) && follower !== collegeCode) {
      return true;
    }
  }

  // Joined degree acronyms (standard PH/COMPASS program codes).
  const joinedPatterns = [
    /(?<![A-Z0-9])(BS[A-Z]{1,10}(?:-[A-Z]{1,8})?)(?![A-Z])/g,
    /(?<![A-Z0-9])(BA(?:ELS|SOC|COMM|POLSCI|PSYCH|ECON|HIST|LIT|PHIL|ENG|FIL)(?:-[A-Z]{1,8})?)(?![A-Z])/g,
    /(?<![A-Z0-9])(AB(?:ELS|SOC|COMM|POLSCI|PSYCH|ECON|HIST|LIT|PHIL|ENG|FIL)(?:-[A-Z]{1,8})?)(?![A-Z])/g,
    /(?<![A-Z0-9])(BPA|BEED|BSED|BTLED|BTVTED|BPED|BCAED|MBA|MPA|MIT|MAED|DBA|DPA|EDD|PHD|LLB|DVM|DMD)(?:-[A-Z]{1,8})?(?![A-Z])/g,
  ];
  for (const pattern of joinedPatterns) {
    for (const match of upper.matchAll(pattern)) {
      if (match[1] !== collegeCode) return true;
    }
  }

  return false;
}

export function detectCourseYearBlockMismatch(
  courseYearBlock: string,
  student: VerifiableStudentPlacement | null | undefined,
  options?: { action?: "submit" | "record" },
): CourseYearBlockMismatch | null {
  const trimmed = courseYearBlock.trim();
  if (!trimmed || !student) return null;

  const program = student.program ?? null;
  const programMismatch =
    program !== null &&
    !inputMatchesProgram(trimmed, program) &&
    hasExplicitDegreeMention(trimmed, student.college);

  const actualYearLevel = student.year_level ?? null;
  const detectedYearLevel = actualYearLevel !== null ? extractTypedYearLevel(trimmed) : null;
  const yearLevelMismatch =
    actualYearLevel !== null &&
    detectedYearLevel !== null &&
    detectedYearLevel !== actualYearLevel;

  if (!programMismatch && !yearLevelMismatch) return null;

  const mismatches: string[] = [];
  if (programMismatch && program) {
    mismatches.push(`Program (${formatAcademicUnit(program)})`);
  }
  if (yearLevelMismatch && actualYearLevel !== null) {
    mismatches.push(`Year level (${yearLevelLabel(actualYearLevel)})`);
  }

  const action = options?.action ?? "submit";
  const continuation =
    action === "record"
      ? "Confirm this is the right Student or edit Course / Year / Block before recording. You can still record this Referral if this is intentional."
      : "Confirm this is the right Student or edit Course/Year/Block before submitting. You can still submit if this is intentional.";

  return {
    programMismatch,
    yearLevelMismatch,
    detectedYearLevel,
    message: `You entered "${trimmed}", which differs from the Student's recorded ${mismatches.join(" and ")}. ${continuation}`,
  };
}
