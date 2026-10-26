import type {
  AcademicClassification, CampusSummary, CollegeSummary, ProgramSummary,
  CatalogCreateCampusRequest, CatalogCreateCollegeRequest, CatalogCreateProgramRequest,
  CatalogRenameRequest, CatalogPolicyRequest, CatalogStatusRequest,
  YearLevelPolicyStatus,
} from "@/lib/api/generated/model";
import { yearLevelLabel } from "@/lib/year-level";

export type CatalogKind = "campus" | "college" | "program";
export type CatalogTarget =
  | { kind: "campus"; record: CampusSummary }
  | { kind: "college"; record: CollegeSummary }
  | { kind: "program"; record: ProgramSummary };
export type CatalogIntent =
  | { mode: "create"; kind: "campus"; parent?: never }
  | { mode: "create"; kind: "college"; parent: Extract<CatalogTarget, { kind: "campus" }> }
  | { mode: "create"; kind: "program"; parent: Extract<CatalogTarget, { kind: "college" }> }
  | { mode: "rename" | "status"; target: CatalogTarget }
  | { mode: "policy"; target: Extract<CatalogTarget, { kind: "program" }> };

// Local entry values, not a second wire schema. Empty status requires an explicit initial choice.
export type CatalogDraft = {
  code: string; name: string; basis: string; active: "" | "active" | "inactive";
  classification: AcademicClassification | null;
  policyStatus: YearLevelPolicyStatus;
  levels: number[];
};
export type CatalogCommand =
  | { operation: "createCampus"; data: CatalogCreateCampusRequest }
  | { operation: "createCollege"; data: CatalogCreateCollegeRequest }
  | { operation: "createProgram"; data: CatalogCreateProgramRequest }
  | { operation: "rename"; target: CatalogTarget; data: CatalogRenameRequest }
  | { operation: "status"; target: CatalogTarget; data: CatalogStatusRequest }
  | { operation: "policy"; target: Extract<CatalogTarget, { kind: "program" }>; data: CatalogPolicyRequest };

export function classificationLabel(value: AcademicClassification | null | undefined) {
  return value === "BACHELORS" ? "Bachelor's" : value === "MASTERS" ? "Master's" : value === "DOCTORAL" ? "Doctoral" : "Classification pending";
}
export function levelsLabel(levels: readonly number[] | null | undefined, status?: YearLevelPolicyStatus | null) {
  if (status !== "CONFIGURED" || !levels?.length) return "Year Level policy pending";
  const labels = levels.map((value) => yearLevelLabel(value).replace(" Year", ""));
  const contiguous = levels.every((value, index) => index === 0 || value === levels[index - 1] + 1);
  if (levels.length > 1 && contiguous) return `${labels[0]}–${labels.at(-1)} Year`;
  return `${labels.length === 1 ? labels[0] : labels.length === 2 ? labels.join(" and ") : `${labels.slice(0, -1).join(", ")} and ${labels.at(-1)}`} Year`;
}
export function academicProgramLabel(program: ProgramSummary) {
  return `${classificationLabel(program.academic_classification)} · ${levelsLabel(program.applicable_year_levels, program.year_level_policy_status)}`;
}
export function parentLabel(target: CatalogTarget): string {
  if (target.kind === "campus") return "Institution campus";
  if (target.kind === "college") return `${target.record.campus.name} (${target.record.campus.code})`;
  return `${target.record.college.campus.name} / ${target.record.college.name} (${target.record.college.code})`;
}
export function initialDraft(intent: CatalogIntent): CatalogDraft {
  const target = intent.mode === "create" ? undefined : intent.target;
  const program = target?.kind === "program" ? target.record : undefined;
  return {
    code: "", name: target?.record.name ?? "", basis: "",
    active: intent.mode === "status" ? (intent.target.record.is_active ? "inactive" : "active") : "",
    classification: program?.academic_classification ?? null,
    policyStatus: program?.year_level_policy_status ?? "PENDING_POLICY",
    levels: [...(program?.applicable_year_levels ?? [])],
  };
}
export function policyValues(draft: CatalogDraft): Pick<CatalogPolicyRequest, "academic_classification" | "year_level_policy_status" | "applicable_year_levels"> {
  return {
    academic_classification: draft.classification,
    year_level_policy_status: draft.policyStatus,
    applicable_year_levels: draft.policyStatus === "PENDING_POLICY" ? null : [...new Set(draft.levels)].sort((a, b) => a - b),
  };
}
export function draftError(intent: CatalogIntent, draft: CatalogDraft, current?: CatalogTarget): string | null {
  const plain = (value: string) => value.trim().length > 0 && value.trim().length <= 160 && !/\p{C}/u.test(value);
  if (!plain(draft.basis)) return "Enter an institutional basis/reference of 1–160 characters without control characters.";
  if ((intent.mode === "create" || intent.mode === "rename") && !plain(draft.name)) return "Enter an official name of 1–160 characters without control characters.";
  if (intent.mode === "create" && !/^[A-Z0-9][A-Z0-9_-]{0,31}$/.test(draft.code.trim().toUpperCase())) return "Use a code of 1–32 letters, digits, hyphens or underscores, starting with a letter or digit.";
  if (intent.mode === "create" && !draft.active) return "Choose the initial status.";
  if (intent.mode === "rename" && current?.record.name.trim() === draft.name.trim()) return "The official name has not changed.";
  if (intent.mode === "status" && current?.record.is_active === (draft.active === "active")) return "The status has already changed. Close this editor and review the current actions.";
  const policy = intent.mode === "policy" || (intent.mode === "create" && intent.kind === "program");
  if (policy && draft.policyStatus === "CONFIGURED" && (!draft.classification || !draft.levels.length || draft.levels.some((v) => !Number.isInteger(v) || v < 1 || v > 10))) return "Configured policy needs a known classification and at least one Year Level from 1–10.";
  if (policy && draft.active === "active" && (draft.policyStatus !== "CONFIGURED" || !draft.classification)) return "An active Program needs a complete configured academic policy. Choose inactive for a pending draft.";
  if (intent.mode === "policy" && current?.kind === "program") {
    const proposed = policyValues(draft);
    if (current.record.academic_classification === proposed.academic_classification && current.record.year_level_policy_status === proposed.year_level_policy_status && JSON.stringify(current.record.applicable_year_levels) === JSON.stringify(proposed.applicable_year_levels)) return "The academic policy has not changed.";
  }
  return null;
}
export function makeCommand(intent: CatalogIntent, draft: CatalogDraft, current?: CatalogTarget): CatalogCommand {
  const common = { name: draft.name.trim(), basis: draft.basis.trim() };
  if (intent.mode === "create") {
    const data = { ...common, code: draft.code.trim().toUpperCase(), is_active: draft.active === "active" };
    if (intent.kind === "campus") return { operation: "createCampus", data };
    if (intent.kind === "college") return { operation: "createCollege", data: { ...data, campus_id: intent.parent.record.id } };
    return { operation: "createProgram", data: { ...data, college_id: intent.parent.record.id, ...policyValues(draft) } };
  }
  if (!current || current.record.id !== intent.target.record.id || current.kind !== intent.target.kind) throw new Error("Current Catalog target is required");
  const version = { basis: common.basis, expected_resource_version: current.record.resource_version };
  if (intent.mode === "rename") return { operation: "rename", target: current, data: { ...version, name: common.name } };
  if (intent.mode === "status") return { operation: "status", target: current, data: { ...version, is_active: draft.active === "active" } };
  if (current.kind !== "program") throw new Error("Program is required");
  return { operation: "policy", target: current, data: { ...version, ...policyValues(draft) } };
}

export type BrowseFilters = { search: string; status: string; campus: string; college: string };
export function filterHierarchy(campuses: CampusSummary[], colleges: CollegeSummary[], programs: ProgramSummary[], filters: BrowseFilters) {
  const search = filters.search.trim().toLocaleLowerCase();
  const textMatches = (record: CampusSummary) => !search || `${record.name} ${record.code}`.toLocaleLowerCase().includes(search);
  const statusMatches = (record: CampusSummary) => !filters.status || record.is_active === (filters.status === "active");
  return campuses.filter((campus) => !filters.campus || campus.id === filters.campus).flatMap((campus) => {
    const children = colleges.filter((college) => college.campus.id === campus.id && (!filters.college || college.id === filters.college)).flatMap((college) => {
      const ownMatch = textMatches(college) && statusMatches(college);
      const ancestorText = textMatches(campus) || textMatches(college);
      const items = programs.filter((program) => program.college.id === college.id && statusMatches(program) && (textMatches(program) || ancestorText));
      return ownMatch || items.length ? [{ college, programs: items, contextOnly: !ownMatch }] : [];
    });
    const ownMatch = !filters.college && textMatches(campus) && statusMatches(campus);
    return ownMatch || children.length ? [{ campus, colleges: children, contextOnly: !ownMatch }] : [];
  });
}
