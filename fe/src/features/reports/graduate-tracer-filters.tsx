"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Notice } from "@/components/ui/notice";
import {
  graduateTracerFilterQuery,
  validateGraduateTracerDraft,
  type GraduateTracerDraft,
} from "@/features/reports/report-filters";
import { useGraduateTracerGetClassificationOptions } from "@/lib/api/generated/graduate-tracer/graduate-tracer";

export function GraduateTracerFilters({
  initialDraft,
  initialErrors,
}: {
  initialDraft: GraduateTracerDraft;
  initialErrors: string[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [draft, setDraft] = useState(initialDraft);
  const [draftError, setDraftError] = useState<string | null>(null);

  const optionsQuery = useGraduateTracerGetClassificationOptions();
  const colleges = optionsQuery.data?.data.colleges ?? [];
  const programs = optionsQuery.data?.data.programs ?? [];

  const visiblePrograms = draft.college_id
    ? programs.filter((program) => program.college_id === draft.college_id)
    : programs;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validated = validateGraduateTracerDraft(draft);
    if (!validated.valid) {
      setDraftError(validated.errors.join(" "));
      return;
    }
    const query = graduateTracerFilterQuery(draft);
    router.push(query ? pathname + "?" + query : pathname, { scroll: false });
  }

  function reset() {
    setDraft({
      submitted_from: "",
      submitted_to: "",
      college_id: "",
      program_id: "",
      graduation_year: "",
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
      {optionsQuery.isError ? (
        <Notice role="alert" tone="danger" className="mb-3">
          Academic classification options could not be loaded.
        </Notice>
      ) : null}
      <form aria-label="Graduate Tracer report filters" onSubmit={submit}>
        <FilterToolbar
          fieldsClassName="sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
          actions={
            <>
              <Button type="button" variant="secondary" onClick={reset}>
                Reset
              </Button>
              <Button type="submit">Apply filters</Button>
            </>
          }
        >
          <FilterField label="College" htmlFor="graduate-tracer-college">
            <Select
              id="graduate-tracer-college"
              value={draft.college_id}
              disabled={optionsQuery.isPending}
              onChange={(event) => {
                const newCollegeId = event.target.value;
                setDraftError(null);
                setDraft((current) => {
                  const programStillValid =
                    !newCollegeId ||
                    !current.program_id ||
                    programs.some(
                      (p) =>
                        p.id === current.program_id &&
                        p.college_id === newCollegeId,
                    );
                  return {
                    ...current,
                    college_id: newCollegeId,
                    program_id: programStillValid ? current.program_id : "",
                  };
                });
              }}
            >
              <option value="">All Colleges</option>
              {colleges.map((college) => (
                <option key={college.id} value={college.id}>
                  {college.code} — {college.name}
                </option>
              ))}
            </Select>
          </FilterField>
          <FilterField label="Program" htmlFor="graduate-tracer-program">
            <Select
              id="graduate-tracer-program"
              value={draft.program_id}
              disabled={optionsQuery.isPending}
              onChange={(event) => {
                setDraftError(null);
                setDraft((current) => ({
                  ...current,
                  program_id: event.target.value,
                }));
              }}
            >
              <option value="">
                {draft.college_id
                  ? "All Programs in selected College"
                  : "All Programs"}
              </option>
              {visiblePrograms.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.code} — {program.name}
                </option>
              ))}
            </Select>
          </FilterField>
          <FilterField label="Graduation Year" htmlFor="graduate-tracer-graduation-year">
            <Input
              id="graduate-tracer-graduation-year"
              type="number"
              min={1900}
              max={new Date().getFullYear()}
              placeholder="e.g. 2024"
              value={draft.graduation_year}
              onChange={(event) => {
                setDraftError(null);
                setDraft((current) => ({
                  ...current,
                  graduation_year: event.target.value,
                }));
              }}
            />
          </FilterField>
          <FilterField label="Submitted From" htmlFor="graduate-tracer-submitted-from">
            <Input
              id="graduate-tracer-submitted-from"
              type="date"
              value={draft.submitted_from}
              onChange={(event) => {
                setDraftError(null);
                setDraft((current) => ({
                  ...current,
                  submitted_from: event.target.value,
                }));
              }}
            />
          </FilterField>
          <FilterField label="Submitted To" htmlFor="graduate-tracer-submitted-to">
            <Input
              id="graduate-tracer-submitted-to"
              type="date"
              value={draft.submitted_to}
              onChange={(event) => {
                setDraftError(null);
                setDraft((current) => ({
                  ...current,
                  submitted_to: event.target.value,
                }));
              }}
            />
          </FilterField>
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
