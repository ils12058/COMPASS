"use client";

import {
  PageHeading,
  QueryError,
  StatusBadge,
  TableSkeleton,
} from "@/features/organization/components/organization-shared";
import {
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationListPrograms,
} from "@/lib/api/generated/organization/organization";

export function OrganizationStructurePage() {
  const campuses = useOrganizationListCampuses({}, { query: { retry: false } });
  const colleges = useOrganizationListColleges({}, { query: { retry: false } });
  const programs = useOrganizationListPrograms({}, { query: { retry: false } });

  const pending = campuses.isPending || colleges.isPending || programs.isPending;
  const error = campuses.error ?? colleges.error ?? programs.error;
  const hasError = campuses.isError || colleges.isError || programs.isError;

  if (pending) {
    return (
      <section aria-labelledby="organization-structure-heading">
        <PageHeading title="Organization structure" />
        <TableSkeleton />
      </section>
    );
  }

  if (hasError) {
    return (
      <section aria-labelledby="organization-structure-heading">
        <PageHeading title="Organization structure" />
        <div className="mt-6">
          <QueryError
            error={error}
            fallback="Organization structure could not be loaded."
            onRetry={() => {
              void campuses.refetch();
              void colleges.refetch();
              void programs.refetch();
            }}
          />
        </div>
      </section>
    );
  }

  const campusItems = campuses.data?.data.items ?? [];
  const collegeItems = colleges.data?.data.items ?? [];
  const programItems = programs.data?.data.items ?? [];

  return (
    <section aria-labelledby="organization-structure-heading">
      <div id="organization-structure-heading">
        <PageHeading title="Organization structure" />
      </div>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
        UCN campus, college, and program records used across COMPASS. These records are read-only here.
      </p>

      {campusItems.length === 0 ? (
        <p className="mt-8 border-y border-border py-10 text-sm text-muted">
          No Organization structure is available.
        </p>
      ) : (
        <ol className="mt-8 divide-y divide-border border-y border-border">
          {campusItems.map((campus) => {
            const campusColleges = collegeItems.filter(
              (college) => college.campus.id === campus.id,
            );
            return (
              <li key={campus.id} className="py-6">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs text-muted">{campus.code}</p>
                    <h2 className="mt-1 font-heading text-xl font-semibold text-ink">
                      {campus.name}
                    </h2>
                  </div>
                  <StatusBadge active={campus.is_active} />
                </div>

                {campusColleges.length === 0 ? (
                  <p className="mt-4 text-sm text-muted">No colleges are recorded for this campus.</p>
                ) : (
                  <div className="mt-5 divide-y divide-border border-t border-border">
                    {campusColleges.map((college) => {
                      const collegePrograms = programItems.filter(
                        (program) => program.college.id === college.id,
                      );
                      return (
                        <section key={college.id} className="py-5" aria-labelledby={`college-${college.id}`}>
                          <div className="flex flex-wrap items-baseline justify-between gap-3">
                            <div>
                              <p className="font-mono text-xs text-muted">{college.code}</p>
                              <h3
                                id={`college-${college.id}`}
                                className="mt-1 font-heading text-base font-semibold text-ink"
                              >
                                {college.name}
                              </h3>
                            </div>
                            <StatusBadge active={college.is_active} />
                          </div>

                          {collegePrograms.length === 0 ? (
                            <p className="mt-3 text-sm text-muted">No programs are recorded.</p>
                          ) : (
                            <ul className="mt-3 divide-y divide-border border-y border-border">
                              {collegePrograms.map((program) => (
                                <li
                                  key={program.id}
                                  className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:gap-4"
                                >
                                  <span className="font-medium text-ink">{program.name}</span>
                                  <span className="font-mono text-xs text-muted">{program.code}</span>
                                  <StatusBadge active={program.is_active} />
                                </li>
                              ))}
                            </ul>
                          )}
                        </section>
                      );
                    })}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
