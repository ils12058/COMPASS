"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { organizationErrorMessage } from "@/features/organization/components/organization-action";
import { useOrganizationListEligiblePeople } from "@/lib/api/generated/organization/organization";
import type { OrganizationListEligiblePeopleParams } from "@/lib/api/generated/model";

export function PeoplePicker({
  id,
  label,
  role,
  enabled,
  value,
  onChange,
}: {
  id: string;
  label: string;
  role: OrganizationListEligiblePeopleParams["role"];
  enabled: boolean;
  value: string;
  onChange: (id: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const people = useOrganizationListEligiblePeople(
    {
      role,
      page,
      page_size: 8,
      ...(search ? { search } : {}),
    },
    { query: { enabled, retry: false } },
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSearch(draft.trim());
  }

  return (
    <fieldset className="min-w-0">
      <legend className="text-sm font-semibold text-ink">{label}</legend>
      <form className="mt-3 flex gap-2" onSubmit={submit}>
        <div className="min-w-0 flex-1">
          <Label className="sr-only" htmlFor={id}>
            Search by name or email
          </Label>
          <Input
            id={id}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Search by name or email"
            maxLength={200}
          />
        </div>
        <Button variant="secondary" type="submit">
          Search
        </Button>
      </form>

      {people.isPending ? (
        <div className="mt-3 space-y-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : people.isError ? (
        <div role="alert" className="mt-3 text-sm text-danger">
          <p>
            {organizationErrorMessage(
              people.error,
              "People could not be loaded.",
            )}
          </p>
          <Button
            variant="secondary"
            className="mt-3"
            onClick={() => void people.refetch()}
          >
            Retry
          </Button>
        </div>
      ) : people.data.data.items.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          No eligible people match this search.
        </p>
      ) : (
        <>
          <div className="mt-3 max-h-56 overflow-y-auto border-y border-border">
            {people.data.data.items.map((person) => (
              <label
                key={person.id}
                className="flex min-h-11 cursor-pointer items-center gap-3 border-t border-border px-2 py-2 first:border-t-0"
              >
                <input
                  type="radio"
                  name={id}
                  value={person.id}
                  checked={value === person.id}
                  onChange={() => onChange(person.id)}
                />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink">
                    {person.full_name}
                  </span>
                  <span className="block truncate text-xs text-muted">
                    {person.institutional_id
                      ? `${person.institutional_id} · ${person.email}`
                      : person.email}
                  </span>
                </span>
              </label>
            ))}
          </div>
          {page > 1 || people.data.data.has_next ? (
            <div className="mt-3 flex items-center justify-between gap-3">
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Previous
              </Button>
              <span className="text-xs text-muted">
                Page {people.data.data.page}
              </span>
              <Button
                variant="secondary"
                disabled={!people.data.data.has_next}
                onClick={() => setPage((current) => current + 1)}
              >
                Next
              </Button>
            </div>
          ) : null}
        </>
      )}
    </fieldset>
  );
}
