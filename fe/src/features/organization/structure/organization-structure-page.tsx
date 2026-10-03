"use client";

import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
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
        <PageHeading title="Organization structure" headingId="organization-structure-heading" />
        <TableSkeleton />
      </section>
    );
  }

  if (hasError) {
    return (
      <section aria-labelledby="organization-structure-heading">
        <PageHeading title="Organization structure" headingId="organization-structure-heading" />
        <div className="mt-5">
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
      <PageHeading
        title="Organization structure"
        headingId="organization-structure-heading"
        description="UCN campus, college, and program records used across COMPASS. These records are read-only here."
      />

      {campusItems.length === 0 ? (
        <Notice className="mt-5">
          No Organization structure is available.
        </Notice>
      ) : (
        <ol className="mt-5 space-y-5">
          {campusItems.map((campus) => {
            const campusColleges = collegeItems.filter(
              (college) => college.campus.id === campus.id,
            );
            return (
              <li key={campus.id}>
                <Panel aria-labelledby={`campus-${campus.id}`}>
                  <PanelHeader
                    title={campus.name}
                    titleId={`campus-${campus.id}`}
                    description={<span className="font-mono text-xs">{campus.code}</span>}
                    actions={<StatusBadge active={campus.is_active} />}
                  />

                  {campusColleges.length === 0 ? (
                    <PanelMessage>No colleges are recorded for this campus.</PanelMessage>
                  ) : (
                    <div className="divide-y divide-border">
                      {campusColleges.map((college) => {
                        const collegePrograms = programItems.filter(
                          (program) => program.college.id === college.id,
                        );
                        return (
                          <section key={college.id} className="px-4 py-4 sm:px-5" aria-labelledby={`college-${college.id}`}>
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
                              <ul className="mt-3 divide-y divide-border rounded-sm border border-border">
                                {collegePrograms.map((program) => (
                                  <li
                                    key={program.id}
                                    className="grid gap-2 px-3 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center sm:gap-4"
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
                </Panel>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
