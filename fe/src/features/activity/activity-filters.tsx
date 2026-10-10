"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useId, useState, type ReactNode, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export function enumValue<T extends string>(value: string | null, values: readonly T[]): T | undefined {
  return values.find((option) => option === value);
}

export function activityTypeLabel(value: string): string {
  const words = value.replaceAll(".", " ").replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function activityUrl(
  pathname: string,
  search: string,
  changes: Record<string, string | null>,
  resetPage = true,
): string {
  const next = new URLSearchParams(search);
  for (const [key, value] of Object.entries(changes)) {
    if (value) next.set(key, value);
    else next.delete(key);
  }
  if (resetPage) next.delete("page");
  return next.size ? `${pathname}?${next}` : pathname;
}

export function useActivitySearchParams() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const parsed = Number(searchParams.get("page"));
  const page = Number.isSafeInteger(parsed) && parsed > 0 && parsed <= 100_000 ? parsed : 1;
  function update(changes: Record<string, string | null>, resetPage = true) {
    router.push(activityUrl(pathname, searchParams.toString(), changes, resetPage), { scroll: false });
  }
  return {
    searchParams,
    page,
    update,
    setPage: (next: number) => update({ page: next > 1 ? String(next) : null }, false),
  };
}

// UI field configuration only; each feature supplies values/options from its generated contract.
export type ActivityFilterField = {
  name: string;
  label: string;
  options?: readonly { value: string; label: string }[];
  type?: "date" | "text";
};

export function ActivityFilterTools({
  applied,
  fields,
  onApply,
  extra,
}: {
  applied: Record<string, string | undefined>;
  fields: readonly ActivityFilterField[];
  onApply: (changes: Record<string, string | null>) => void;
  extra?: ReactNode;
}) {
  const id = useId();
  const [draft, setDraft] = useState(applied);
  const dateError = Boolean(draft.date_from && draft.date_to && draft.date_from > draft.date_to);
  const filterCount = fields.filter((field) => Boolean(applied[field.name])).length;
  const filtered = Boolean(applied.search) || filterCount > 0;
  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submitter = event.nativeEvent instanceof SubmitEvent ? event.nativeEvent.submitter : null;
    const clear = submitter instanceof HTMLButtonElement && submitter.name === "clear_filters";
    if (!clear && dateError) return;
    if (clear) setDraft({});
    onApply(Object.fromEntries(
      ["search", ...fields.map((field) => field.name)].map((name) => [
        name,
        clear ? null : draft[name]?.trim() || null,
      ]),
    ));
  }
  return (
    <form role="search" aria-label="Find activity" onSubmit={apply}>
      <FloatingListTools
        submits
        invalid={dateError}
        filterCount={filterCount}
        filters={
          <>
          {fields.map((field) => (
            <FilterField key={field.name} label={field.label} htmlFor={`${id}-${field.name}`}>
              {field.options ? (
                <Select
                  id={`${id}-${field.name}`}
                  name={field.name}
                  value={draft[field.name] ?? ""}
                  onChange={(event) => setDraft({ ...draft, [field.name]: event.target.value })}
                >
                  <option value="">All {field.label.toLowerCase()}</option>
                  {field.options.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </Select>
              ) : (
                <Input
                  id={`${id}-${field.name}`}
                  name={field.name}
                  type={field.type ?? "text"}
                  maxLength={field.type === "date" ? undefined : 100}
                  value={draft[field.name] ?? ""}
                  onChange={(event) => setDraft({ ...draft, [field.name]: event.target.value })}
                  aria-invalid={field.type === "date" && dateError ? true : undefined}
                  aria-describedby={field.type === "date" && dateError ? `${id}-date-error` : undefined}
                />
              )}
            </FilterField>
          ))}
          {dateError ? (
            <p id={`${id}-date-error`} role="alert" className="text-sm text-danger sm:col-span-2">
              Date from must not be after Date to.
            </p>
          ) : null}
          {extra}
          </>
        }
        clear={filtered ? (
          <Button type="submit" name="clear_filters" variant="quiet">Clear filters</Button>
        ) : undefined}
      >
        <ListSearchField
          id={`${id}-search`}
          label="Search activity"
          name="search"
          maxLength={100}
          value={draft.search ?? ""}
          onChange={(event) => setDraft({ ...draft, search: event.target.value })}
          placeholder="Search activity"
        />
      </FloatingListTools>
    </form>
  );
}
