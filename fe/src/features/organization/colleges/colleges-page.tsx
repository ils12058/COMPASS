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
import {
  useOrganizationListCampuses,
  useOrganizationListColleges,
} from "@/lib/api/generated/organization/organization";

export function CollegesPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  const status = searchParams.get("is_active") ?? "";
  const campusId = searchParams.get("campus_id") ?? "";
  const campuses = useOrganizationListCampuses({}, { query: { retry: false } });
  const list = useOrganizationListColleges(
    {
      ...(campusId ? { campus_id: campusId } : {}),
      ...(status === "true" || status === "false"
        ? { is_active: status === "true" }
        : {}),
      ...(search ? { search } : {}),
    },
    { query: { retry: false } },
  );

  function updateFilter(key: string, value: string) {
    router.replace(
      replaceQueryParam(
        pathname,
        new URLSearchParams(searchParams.toString()),
        key,
        value,
      ),
      { scroll: false },
    );
  }

  return (
    <section>
      <PageHeading title="Colleges" />
      <p className="mt-3 max-w-3xl text-sm text-muted">
        UCN colleges and top-level academic offering units used by COMPASS for
        institutional reference and Guidance Office routing.
      </p>

      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 lg:flex-row lg:items-end">
        <SearchField label="Search Colleges" placeholder="Search Colleges…" />
        <div className="grid gap-4 sm:grid-cols-2 lg:w-[26rem]">
          <div>
            <Label htmlFor="college-campus-filter">Campus</Label>
            <select
              id="college-campus-filter"
              className={`${selectClass} mt-2`}
              value={campusId}
              disabled={campuses.isPending || campuses.isError}
              onChange={(event) => updateFilter("campus_id", event.target.value)}
            >
              <option value="">All Campuses</option>
              {campuses.data?.data.items.map((campus) => (
                <option key={campus.id} value={campus.id}>
                  {campus.code} — {campus.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="college-status">Status</Label>
            <select
              id="college-status"
              className={`${selectClass} mt-2`}
              value={status === "true" || status === "false" ? status : ""}
              onChange={(event) => updateFilter("is_active", event.target.value)}
            >
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </div>
        </div>
      </div>

      {campuses.isError ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          Campus choices could not be loaded. The College list remains available.
        </p>
      ) : null}

      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <QueryError
            error={list.error}
            fallback="Colleges could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          {search || status || campusId
            ? "No Colleges match the current search or filters."
            : "No Colleges are available."}
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto border-y border-border">
          <table className="w-full min-w-[42rem] border-collapse text-left text-sm">
            <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-3">College / academic unit</th>
                <th scope="col" className="px-4 py-3">Code</th>
                <th scope="col" className="px-4 py-3">Campus</th>
                <th scope="col" className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {list.data.data.items.map((college) => (
                <tr key={college.id} className="border-t border-border">
                  <th scope="row" className="px-4 py-4 font-semibold text-ink">
                    {college.name}
                  </th>
                  <td className="px-4 py-4 font-mono text-xs text-muted">
                    {college.code}
                  </td>
                  <td className="px-4 py-4">
                    {college.campus.code} — {college.campus.name}
                  </td>
                  <td className="px-4 py-4">
                    <StatusBadge active={college.is_active} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
