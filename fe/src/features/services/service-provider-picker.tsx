"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { servicesErrorMessage } from "@/features/services/services-shared";
import { useServicesListProviderCandidates } from "@/lib/api/generated/services/services";

export type SelectedCounselor = {
  id: string;
  displayName: string;
  // False for an already-selected Counselor whose account has since become inactive.
  isActive: boolean;
};

// Chooses the Counselors qualified for a Service from all active Counselors. It never filters
// by College: College responsibility routes Students by default but does not limit choice.
export function ServiceProviderPicker({
  selected,
  onChange,
  disabled = false,
}: {
  selected: SelectedCounselor[];
  onChange: (next: SelectedCounselor[]) => void;
  disabled?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const candidates = useServicesListProviderCandidates(
    { ...(query ? { search: query } : {}), page, page_size: 10 },
    { query: { retry: false } },
  );
  const selectedIds = new Set(selected.map((item) => item.id));

  useEffect(() => {
    const trimmed = search.trim();
    if (trimmed === query) return;
    const timer = window.setTimeout(() => {
      setQuery(trimmed);
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query, search]);

  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <div>
        <p className="text-sm font-semibold text-ink">Selected Counselors</p>
        {selected.length === 0 ? (
          <p className="mt-2 text-sm text-muted">No Counselors selected yet.</p>
        ) : (
          <ul aria-label="Selected Counselors" className="mt-2 divide-y divide-border rounded-sm border border-border">
            {selected.map((counselor) => (
              <li key={counselor.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                <span className="text-sm text-ink">
                  {counselor.displayName}
                  {!counselor.isActive ? (
                    <span className="block text-xs text-muted">Inactive account · not eligible</span>
                  ) : null}
                </span>
                <Button
                  type="button"
                  variant="quiet"
                  disabled={disabled}
                  onClick={() => onChange(selected.filter((item) => item.id !== counselor.id))}
                >
                  Remove<span className="sr-only"> {counselor.displayName}</span>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <Label htmlFor="service-provider-search">Find active Counselors</Label>
        <Input
          id="service-provider-search"
          type="search"
          className="mt-2"
          value={search}
          maxLength={160}
          placeholder="Search by name"
          autoComplete="off"
          onChange={(event) => setSearch(event.target.value)}
        />
        {candidates.isPending ? (
          <div aria-busy="true" className="mt-3 space-y-2">
            <span className="sr-only">Loading Counselors…</span>
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : candidates.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {servicesErrorMessage(candidates.error, "Counselors could not be loaded.")}{" "}
            <button type="button" className="font-semibold underline" onClick={() => void candidates.refetch()}>
              Retry
            </button>
          </p>
        ) : candidates.data.data.items.length === 0 ? (
          <p className="mt-3 text-sm text-muted">
            {query ? "No active Counselors match this search." : "No active Counselors are available."}
          </p>
        ) : (
          <>
            <ul aria-label="Active Counselors" className="mt-3 divide-y divide-border rounded-sm border border-border">
              {candidates.data.data.items.map((candidate) => {
                const chosen = selectedIds.has(candidate.id);
                return (
                  <li key={candidate.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                    <span className="text-sm text-ink">{candidate.display_name}</span>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={disabled || chosen}
                      onClick={() =>
                        onChange([
                          ...selected,
                          { id: candidate.id, displayName: candidate.display_name, isActive: true },
                        ])
                      }
                    >
                      {chosen ? "Selected" : "Add"}
                      <span className="sr-only"> {candidate.display_name}</span>
                    </Button>
                  </li>
                );
              })}
            </ul>
            <CanonicalPagination
              className="mt-2"
              page={candidates.data.data.page}
              hasNext={candidates.data.data.has_next}
              disabled={candidates.isFetching}
              label="Counselor pages"
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    </div>
  );
}
