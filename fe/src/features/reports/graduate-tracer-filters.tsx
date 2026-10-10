"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FilterField, FilterToolbar } from "@/components/ui/filter-toolbar";
import { Notice } from "@/components/ui/notice";
import {
  graduateTracerFilterQuery,
  validateGraduateTracerDraft,
  type GraduateTracerDraft,
} from "@/features/reports/report-filters";

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
    setDraft({ submitted_from: "", submitted_to: "" });
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
      <form aria-label="Submission period" onSubmit={submit}>
        <FilterToolbar
          fieldsClassName="sm:grid-cols-2 lg:grid-cols-[minmax(12rem,18rem)_minmax(12rem,18rem)]"
          actions={
            <>
              <Button type="button" variant="secondary" onClick={reset}>
                Reset
              </Button>
              <Button type="submit">Apply filters</Button>
            </>
          }
        >
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
