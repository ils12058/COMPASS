"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
    <section
      aria-labelledby="graduate-tracer-filters-heading"
      className="mt-6 border-y border-border py-5"
    >
      <h2
        id="graduate-tracer-filters-heading"
        className="font-heading text-lg font-semibold text-ink"
      >
        Submission period
      </h2>
      {initialErrors.length > 0 ? (
        <p role="alert" className="mt-3 text-sm leading-6 text-danger">
          The applied URL filters are invalid: {initialErrors.join(" ")} Reset or correct them, then apply the filters.
        </p>
      ) : null}
      <form
        className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(12rem,18rem)_minmax(12rem,18rem)_auto]"
        onSubmit={submit}
      >
        <div>
          <Label htmlFor="graduate-tracer-submitted-from">Submitted From</Label>
          <Input
            id="graduate-tracer-submitted-from"
            className="mt-2"
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
        </div>
        <div>
          <Label htmlFor="graduate-tracer-submitted-to">Submitted To</Label>
          <Input
            id="graduate-tracer-submitted-to"
            className="mt-2"
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
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <Button type="submit">Apply filters</Button>
          <Button type="button" variant="secondary" onClick={reset}>
            Reset
          </Button>
        </div>
      </form>
      {draftError ? (
        <p role="alert" className="mt-3 text-sm leading-6 text-danger">
          {draftError}
        </p>
      ) : null}
    </section>
  );
}
