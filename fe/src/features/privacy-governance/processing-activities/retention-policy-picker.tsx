"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
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

const pickerParams = { is_active: true, page_size: 50 } as const;

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
  const policies = useInfiniteQuery({
    queryKey: [
      ...getPrivacyGovernanceListRetentionPoliciesQueryKey(pickerParams),
      "picker",
    ],
    queryFn: ({ pageParam, signal }) =>
      privacyGovernanceListRetentionPolicies(
        { ...pickerParams, page: pageParam },
        { signal },
      ),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.data.has_next ? last.data.page + 1 : undefined),
    retry: false,
  });

  const options = policies.data?.pages.flatMap((page) => page.data.items) ?? [];
  // Keep an existing assignment visible even when it is retired or not yet
  // loaded, so editing other fields never clears it silently.
  const showCurrent =
    currentPolicy !== null && !options.some((policy) => policy.id === currentPolicy.id);
  const keepsRetiredPolicy =
    currentPolicy !== null && !currentPolicy.is_active && value === currentPolicy.id;

  return (
    <div className="grid gap-2">
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
            {policies.isFetchingNextPage ? "Loading…" : "Load more Retention Policies"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
