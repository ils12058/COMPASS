"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { FilterToolbar } from "@/components/ui/filter-toolbar";
import { Notice } from "@/components/ui/notice";
import type {
  AcademicYearResponse,
  CampusSummary,
  CollegeSummary,
  OrganizationReference,
  ProgramSummary,
  ReportScopeCollege,
  ReportScopeResponse,
} from "@/lib/api/generated/model";
import { useOrganizationListPrograms } from "@/lib/api/generated/organization/organization";
import {
  studentProfileFilterQuery,
  validateStudentProfileDraft,
  type StudentProfileDraft,
} from "@/features/reports/report-filters";

type CampusChoice = CampusSummary | OrganizationReference;
type CollegeChoice = CollegeSummary | ReportScopeCollege;

function isActiveChoice(choice: CampusChoice | CollegeChoice | ProgramSummary) {
  return !("is_active" in choice) || choice.is_active;
}

function optionLabel(choice: CampusChoice | CollegeChoice | ProgramSummary) {
  return (
    choice.code +
    " — " +
    choice.name +
    (isActiveChoice(choice) ? "" : " (Inactive — historical identity)")
  );
}

function scopedCampusChoices(scope: ReportScopeResponse): CampusChoice[] {
  const byId = new Map<string, OrganizationReference>();
  for (const college of scope.colleges) {
    byId.set(college.campus.id, college.campus);
  }
  return [...byId.values()];
}

export function StudentProfileFilters({
  scope,
  initialDraft,
  initialErrors,
  academicYears,
  academicYearsLoading,
  academicYearsError,
  retryAcademicYears,
  campuses,
  campusesLoading,
  campusesError,
  retryCampuses,
  colleges,
  collegesLoading,
  collegesError,
  retryColleges,
}: {
  scope: ReportScopeResponse;
  initialDraft: StudentProfileDraft;
  initialErrors: string[];
  academicYears: AcademicYearResponse[];
  academicYearsLoading: boolean;
  academicYearsError: boolean;
  retryAcademicYears: () => void;
  campuses: CampusSummary[];
  campusesLoading: boolean;
  campusesError: boolean;
  retryCampuses: () => void;
  colleges: CollegeSummary[];
  collegesLoading: boolean;
  collegesError: boolean;
  retryColleges: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [draft, setDraft] = useState(initialDraft);
  const [draftError, setDraftError] = useState<string | null>(null);

  const campusChoices = scope.is_global
    ? campuses
    : scopedCampusChoices(scope);
  const collegeChoices: CollegeChoice[] = scope.is_global
    ? colleges
    : scope.colleges;
  const visibleColleges = draft.campus_id
    ? collegeChoices.filter(
        (college) => college.campus.id === draft.campus_id,
      )
    : collegeChoices;
  const selectedCollege = collegeChoices.find(
    (college) => college.id === draft.college_id,
  );
  const programs = useOrganizationListPrograms(
    draft.college_id ? { college_id: draft.college_id } : {},
    {
      query: {
        enabled: Boolean(scope && draft.college_id && selectedCollege),
        retry: false,
      },
    },
  );
  const programChoices = programs.data?.data.items ?? [];

  function updateDraft(field: keyof StudentProfileDraft, value: string) {
    setDraftError(null);
    setDraft((current) => {
      if (field === "campus_id") {
        return { ...current, campus_id: value, college_id: "", program_id: "" };
      }
      if (field === "college_id") {
        return { ...current, college_id: value, program_id: "" };
      }
      return { ...current, [field]: value };
    });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validated = validateStudentProfileDraft(draft);
    if (!validated.valid) {
      setDraftError(validated.errors.join(" "));
      return;
    }

    if (draft.campus_id) {
      if (scope.is_global && campusesError) {
        setDraftError("Campus choices could not be verified. Retry the choices and try again.");
        return;
      }
      if (!campusChoices.some((campus) => campus.id === draft.campus_id)) {
        setDraftError("Choose a campus you can report on.");
        return;
      }
    }
    if (draft.college_id) {
      if (scope.is_global && collegesError) {
        setDraftError("College choices could not be verified. Retry the choices and try again.");
        return;
      }
      if (!selectedCollege) {
        setDraftError("Choose a college you can report on.");
        return;
      }
      if (
        draft.campus_id &&
        selectedCollege.campus.id !== draft.campus_id
      ) {
        setDraftError("The selected College does not belong to the selected Campus.");
        return;
      }
    }
    if (draft.program_id) {
      if (!draft.college_id) {
        setDraftError("Select a College before choosing a Program.");
        return;
      }
      if (programs.isPending) {
        setDraftError("Program choices are still loading. Try again when they finish.");
        return;
      }
      if (programs.isError && programChoices.length === 0) {
        setDraftError("Program choices could not be verified. Retry the choices and try again.");
        return;
      }
      if (
        !programChoices.some(
          (program) =>
            program.id === draft.program_id &&
            program.college.id === draft.college_id,
        )
      ) {
        setDraftError("Choose a Program in the selected College.");
        return;
      }
    }

    const query = studentProfileFilterQuery(draft);
    router.push(query ? pathname + "?" + query : pathname, { scroll: false });
  }

  function reset() {
    setDraft({
      academic_year_id: "",
      campus_id: "",
      college_id: "",
      program_id: "",
      year_level: "",
    });
    setDraftError(null);
    router.push(pathname, { scroll: false });
  }

  return (
    <div>
      {initialErrors.length > 0 ? (
        <Notice role="alert" tone="danger" className="mb-3">
          The applied URL filters are invalid: {initialErrors.join(" ")} Reset or correct them, then apply the filters.
        </Notice>
      ) : null}
      <form aria-label="Report filters" onSubmit={submit}>
        <FilterToolbar
          fieldsClassName="sm:grid-cols-2 lg:grid-cols-3"
          actions={
            <>
              <Button type="button" variant="secondary" onClick={reset}>
                Reset
              </Button>
              <Button type="submit">Apply filters</Button>
            </>
          }
        >
        <div className="grid min-w-0 content-start gap-1.5">
          <Label htmlFor="report-academic-year">Academic Year</Label>
          <Select
            id="report-academic-year"
            value={draft.academic_year_id}
            disabled={academicYearsLoading || academicYearsError}
            onChange={(event) =>
              updateDraft("academic_year_id", event.target.value)
            }
            aria-describedby={
              academicYearsError ? "report-academic-year-state" : undefined
            }
          >
            <option value="">Current Academic Year</option>
            {academicYears.map((year) => (
              <option key={year.id} value={year.id}>
              {year.label}
              {year.is_current ? " (Current)" : ""}
              </option>
            ))}
          </Select>
          <p id="report-academic-year-state" className="text-xs text-muted">
            {academicYearsLoading
              ? "Loading academic years…"
              : academicYearsError
                ? "Academic Year choices could not be loaded."
                : "Leaving this blank resolves the current Academic Year."}
          </p>
          {academicYearsError ? (
            <Button
              className="min-h-8 w-fit px-2 text-xs"
              variant="secondary"
              type="button"
              onClick={retryAcademicYears}
            >
              Retry Academic Years
            </Button>
          ) : null}
        </div>
        <div className="grid min-w-0 content-start gap-1.5">
          <Label htmlFor="report-campus">Campus</Label>
          <Select
            id="report-campus"
            value={draft.campus_id}
            disabled={scope.is_global && (campusesLoading || campusesError)}
            onChange={(event) => updateDraft("campus_id", event.target.value)}
          >
            <option value="">
              {scope.is_global ? "All Campuses" : "All authorized Campuses"}
            </option>
            {campusChoices.map((campus) => (
              <option key={campus.id} value={campus.id}>
                {optionLabel(campus)}
              </option>
            ))}
          </Select>
          {scope.is_global && campusesError ? (
            <div id="report-campus-state" className="text-xs text-danger">
              Campus choices could not be loaded.
              <Button
                className="ml-2 min-h-8 px-2 text-xs"
                variant="quiet"
                type="button"
                onClick={retryCampuses}
              >
                Retry
              </Button>
            </div>
          ) : scope.is_global && campusesLoading ? (
            <p id="report-campus-state" role="status" className="text-xs text-muted">
              Loading campuses…
            </p>
          ) : null}
        </div>
        <div className="grid min-w-0 content-start gap-1.5">
          <Label htmlFor="report-college">College</Label>
          <Select
            id="report-college"
            value={draft.college_id}
            disabled={scope.is_global && (collegesLoading || collegesError)}
            onChange={(event) => updateDraft("college_id", event.target.value)}
          >
            <option value="">
              {draft.campus_id
                ? scope.is_global
                  ? "All Colleges on selected Campus"
                  : "All authorized Colleges on selected Campus"
                : scope.is_global
                  ? "All Colleges"
                  : "All authorized Colleges"}
            </option>
            {visibleColleges.map((college) => (
              <option key={college.id} value={college.id}>
                {optionLabel(college)}
              </option>
            ))}
          </Select>
          {scope.is_global && collegesError ? (
            <div id="report-college-state" className="text-xs text-danger">
              College choices could not be loaded.
              <Button
                className="ml-2 min-h-8 px-2 text-xs"
                variant="quiet"
                type="button"
                onClick={retryColleges}
              >
                Retry
              </Button>
            </div>
          ) : scope.is_global && collegesLoading ? (
            <p id="report-college-state" role="status" className="text-xs text-muted">
              Loading colleges…
            </p>
          ) : null}
        </div>
        <div className="grid min-w-0 content-start gap-1.5">
          <Label htmlFor="report-program">Program</Label>
          <Select
            id="report-program"
            value={draft.program_id}
            disabled={
              !selectedCollege ||
              programs.isPending ||
              (programs.isError && programChoices.length === 0)
            }
            onChange={(event) => updateDraft("program_id", event.target.value)}
            aria-describedby="report-program-state"
          >
            <option value="">
              {draft.college_id ? "All Programs in selected College" : "Select a College first"}
            </option>
            {programChoices.map((program) => (
              <option key={program.id} value={program.id}>
                {optionLabel(program)}
              </option>
            ))}
          </Select>
          <p id="report-program-state" className="text-xs text-muted">
            {!draft.college_id
              ? "Select a College first."
              : programs.isPending
                ? "Loading programs…"
                : programs.isError
                  ? "Program choices could not be refreshed."
                  : "Inactive Programs remain available for historical reports."}
          </p>
          {draft.college_id && programs.isError ? (
            <Button
              className="min-h-8 w-fit px-2 text-xs"
              variant="secondary"
              type="button"
              onClick={() => void programs.refetch()}
            >
              Retry Programs
            </Button>
          ) : null}
        </div>
        <div className="grid min-w-0 content-start gap-1.5">
          <Label htmlFor="report-year-level">Year Level</Label>
          <Select
            id="report-year-level"
            value={draft.year_level}
            onChange={(event) => updateDraft("year_level", event.target.value)}
          >
            <option value="">All Year Levels</option>
            {Array.from({ length: 10 }, (_, index) => index + 1).map((year) => (
              <option key={year} value={year}>
                {year}
                {year % 100 >= 11 && year % 100 <= 13
                  ? "th"
                  : year % 10 === 1
                    ? "st"
                    : year % 10 === 2
                      ? "nd"
                      : year % 10 === 3
                        ? "rd"
                        : "th"}{" "}
                Year
              </option>
            ))}
          </Select>
        </div>
        </FilterToolbar>
      </form>
      {draftError ? (
        <p role="alert" className="mt-3 text-sm leading-6 text-danger">
          {draftError}
        </p>
      ) : null}
    </div>
  );
}
