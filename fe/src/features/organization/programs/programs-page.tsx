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
  useOrganizationListColleges,
  useOrganizationListPrograms,
} from "@/lib/api/generated/organization/organization";

export function ProgramsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = (searchParams.get("search") ?? "").slice(0, 200).trim();
  const status = searchParams.get("is_active") ?? "";
  const collegeId = searchParams.get("college_id") ?? "";
  const colleges = useOrganizationListColleges({}, { query: { retry: false } });
  const list = useOrganizationListPrograms(
    {
      ...(collegeId ? { college_id: collegeId } : {}),
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
      <PageHeading title="Programs" />
      <p className="mt-3 max-w-3xl text-sm text-muted">
        Base UCN degree and program references used by COMPASS. Majors and
        specializations remain separate student information.
      </p>

      <div className="mt-8 flex flex-col gap-4 border-y border-border py-5 lg:flex-row lg:items-end">
        <SearchField label="Search Programs" placeholder="Search Programs…" />
        <div className="grid gap-4 sm:grid-cols-2 lg:w-[30rem]">
          <div>
            <Label htmlFor="program-college-filter">College</Label>
            <select
              id="program-college-filter"
              className={`${selectClass} mt-2`}
              value={collegeId}
              disabled={colleges.isPending || colleges.isError}
              onChange={(event) => updateFilter("college_id", event.target.value)}
            >
              <option value="">All Colleges</option>
              {colleges.data?.data.items.map((college) => (
                <option key={college.id} value={college.id}>
                  {college.code} — {college.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="program-status">Status</Label>
            <select
              id="program-status"
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

      {colleges.isError ? (
        <p role="alert" className="mt-3 text-xs text-danger">
          College choices could not be loaded. The Program list remains available.
        </p>
      ) : null}

      {list.isPending ? (
        <TableSkeleton />
      ) : list.isError ? (
        <div className="mt-6">
          <QueryError
            error={list.error}
            fallback="Programs could not be loaded."
            onRetry={() => void list.refetch()}
          />
        </div>
      ) : list.data.data.items.length === 0 ? (
        <p className="border-b border-border py-10 text-sm text-muted">
          {search || status || collegeId
            ? "No Programs match the current search or filters."
            : "No Programs are available."}
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto border-y border-border">
          <table className="w-full min-w-[46rem] border-collapse text-left text-sm">
            <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-4 py-3">Program</th>
                <th scope="col" className="px-4 py-3">Code</th>
                <th scope="col" className="px-4 py-3">College / academic unit</th>
                <th scope="col" className="px-4 py-3">Campus</th>
                <th scope="col" className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {list.data.data.items.map((program) => (
                <tr key={program.id} className="border-t border-border">
                  <th scope="row" className="px-4 py-4 font-semibold text-ink">
                    {program.name}
                  </th>
                  <td className="px-4 py-4 font-mono text-xs text-muted">
                    {program.code}
                  </td>
                  <td className="px-4 py-4">{program.college.name}</td>
                  <td className="px-4 py-4">{program.college.campus.name}</td>
                  <td className="px-4 py-4">
                    <StatusBadge active={program.is_active} />
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
