"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Label } from "@/components/ui/label";
import {
  PageHeading,
  QueryError,
  SearchField,
  StatusBadge,
  TableSkeleton,
  replaceQueryParam,
  selectClass,
} from "@/features/organization/components/organization-shared";
import { useOrganizationListCampuses } from "@/lib/api/generated/organization/organization";

export function CampusesPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  const status = searchParams.get("is_active") ?? "";
  const list = useOrganizationListCampuses(
    {
      ...(status === "true" || status === "false"
        ? { is_active: status === "true" }
        : {}),
      ...(search ? { search } : {}),
    },
    { query: { retry: false } },
  );

  function updateFilter(value: string) {
    router.replace(
      replaceQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        "is_active",
        value,
      ),
      { scroll: false },
    );
  }

  return (
    <section aria-labelledby="campuses-heading">
      <div className="sr-only" id="campuses-heading">
        Campuses
      </div>
      <PageHeading title="Campuses" />
      <p className="mt-3 max-w-3xl text-sm text-muted">
        UCN campuses used by COMPASS as institutional reference structure.
      </p>

      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 sm:flex-row sm:items-end">
        <SearchField label="Search campuses" placeholder="Search campuses…" />
        <div className="sm:w-44">
          <Label htmlFor="campus-status">Status</Label>
          <select
            id="campus-status"
            className={`${selectClass} mt-2`}
            value={status === "true" || status === "false" ? status : ""}
            onChange={(event) => updateFilter(event.target.value)}
          >
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>
      </div>

      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <QueryError
            error={list.error}
            fallback="Campuses could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          {search || status
            ? "No Campuses match the current search or filters."
            : "No Campuses are available."}
        </p>
      ) : (
        <>
          {list.isFetching ? (
            <p role="status" className="mt-4 text-xs text-muted">
              Refreshing Campuses…
            </p>
          ) : null}
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">Code</th>
                  <th scope="col" className="px-4 py-3">Campus</th>
                  <th scope="col" className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {list.data.data.items.map((campus) => (
                  <tr key={campus.id} className="border-t border-border">
                    <td className="px-4 py-4 font-mono text-xs text-muted">
                      {campus.code}
                    </td>
                    <th scope="row" className="px-4 py-4 font-semibold text-ink">
                      {campus.name}
                    </th>
                    <td className="px-4 py-4">
                      <StatusBadge active={campus.is_active} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
