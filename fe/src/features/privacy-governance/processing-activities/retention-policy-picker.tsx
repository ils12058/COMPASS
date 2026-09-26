"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  FieldHint,
  privacySelectClass,
} from "@/features/privacy-governance/privacy-governance-shared";
import type { RetentionSummary } from "@/lib/api/generated/model";
import {
  getPrivacyGovernanceListRetentionPoliciesQueryKey,
  privacyGovernanceListRetentionPolicies,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

const PICKER_PAGE_SIZE = 20;
const SEARCH_MAX_LENGTH = 160;

export function RetentionPolicyPicker({
  id,
  value,
  currentPolicy,
  onChange,
}: {
  id: string;
  value: string;
  currentPolicy: RetentionSummary | null;
  onChange: (value: string) => void;
}) {
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const params = {
    is_active: true,
    page_size: PICKER_PAGE_SIZE,
    ...(search ? { search } : {}),
  };
  const policies = useInfiniteQuery({
    queryKey: [...getPrivacyGovernanceListRetentionPoliciesQueryKey(params), "picker"],
    queryFn: ({ pageParam, signal }) =>
      privacyGovernanceListRetentionPolicies({ ...params, page: pageParam }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.data.has_next ? last.data.page + 1 : undefined),
    retry: false,
  });

  const options = policies.data?.pages.flatMap((page) => page.data.items) ?? [];
  // Keep an existing assignment visible even when it is retired or not in the current
  // results, so searching or editing other fields never clears it silently.
  const showCurrent =
    currentPolicy !== null && !options.some((policy) => policy.id === currentPolicy.id);
  const keepsRetiredPolicy =
    currentPolicy !== null && !currentPolicy.is_active && value === currentPolicy.id;
  const noMatches = policies.isSuccess && options.length === 0 && search !== "";

  function applySearch() {
    setSearch(searchDraft.trim());
  }

  return (
    <div className="grid gap-2">
      <Label htmlFor={`${id}-search`}>Find a Retention Policy</Label>
      <div className="flex max-w-xl flex-col gap-2 sm:flex-row">
        <Input
          id={`${id}-search`}
          type="search"
          autoComplete="off"
          maxLength={SEARCH_MAX_LENGTH}
          placeholder="Search by code or name"
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          onKeyDown={(event) => {
            // The picker sits inside the Processing Activity form; Enter searches instead.
            if (event.key === "Enter") {
              event.preventDefault();
              applySearch();
            }
          }}
        />
        <Button type="button" variant="secondary" onClick={applySearch}>
          Search
        </Button>
      </div>
      <Label htmlFor={id}>Retention Policy</Label>
      <select
        id={id}
        className={privacySelectClass + " max-w-xl"}
        value={value}
        aria-describedby={`${id}-hint`}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">No internal Retention Policy</option>
        {showCurrent ? (
          <option value={currentPolicy.id}>
            {currentPolicy.name}
            {currentPolicy.is_active ? "" : " (retired)"}
          </option>
        ) : null}
        {options.map((policy) => (
          <option key={policy.id} value={policy.id}>
            {policy.name} ({policy.code})
          </option>
        ))}
      </select>
      <FieldHint id={`${id}-hint`}>
        Only active Retention Policies can be newly assigned.
        {keepsRetiredPolicy
          ? " The current policy is retired. It stays assigned unless you choose another option."
          : null}
      </FieldHint>
      {policies.isPending ? (
        <p role="status" className="text-xs text-muted">
          Loading active Retention Policies…
        </p>
      ) : null}
      {noMatches ? (
        <div role="status" className="flex flex-wrap items-center gap-3 text-xs text-muted">
          No active Retention Policies match “{search}”.
          <Button
            type="button"
            variant="quiet"
            onClick={() => {
              setSearchDraft("");
              setSearch("");
            }}
          >
            Clear search
          </Button>
        </div>
      ) : null}
      {policies.isError ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-xs text-danger">
          Active Retention Policies could not be loaded.
          <Button type="button" variant="secondary" onClick={() => void policies.refetch()}>
            Retry
          </Button>
        </div>
      ) : null}
      {policies.hasNextPage ? (
        <div>
          <Button
            type="button"
            variant="quiet"
            disabled={policies.isFetchingNextPage}
            onClick={() => void policies.fetchNextPage()}
          >
            {policies.isFetchingNextPage ? "Loading…" : "Show more matching policies"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
