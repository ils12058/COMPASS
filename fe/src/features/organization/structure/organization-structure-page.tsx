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

// Structure is read-only hierarchical text, not a wide collection, so this page alone is bounded;
// the other Organization tabs keep the whole workspace for their tables. Each name sits close to its
// status at this width.
const structureWidth = "max-w-4xl";

export function OrganizationStructurePage() {
  const campuses = useOrganizationListCampuses({}, { query: { retry: false } });
  const colleges = useOrganizationListColleges({}, { query: { retry: false } });
  const programs = useOrganizationListPrograms({}, { query: { retry: false } });

  const pending = campuses.isPending || colleges.isPending || programs.isPending;
  const error = campuses.error ?? colleges.error ?? programs.error;
  const hasError = campuses.isError || colleges.isError || programs.isError;

  if (pending) {
    return (
      <section aria-labelledby="organization-structure-heading" className={structureWidth}>
        <PageHeading title="Organization structure" headingId="organization-structure-heading" />
        <TableSkeleton />
      </section>
    );
  }

  if (hasError) {
    return (
      <section aria-labelledby="organization-structure-heading" className={structureWidth}>
        <PageHeading title="Organization structure" headingId="organization-structure-heading" />
        <div>
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
    <section aria-labelledby="organization-structure-heading" className={structureWidth}>
      <PageHeading
        title="Organization structure"
        headingId="organization-structure-heading"
        description="Campus, college, and program records are read-only here."
      />

      {campusItems.length === 0 ? (
        <Notice>
          No organization structure is available.
        </Notice>
      ) : (
        <ol className="space-y-5">
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
                    // Colleges are the campus's rows; each College's Programs are indented beneath
                    // it rather than boxed, so the hierarchy reads from position and type alone.
                    <ul className="divide-y divide-border">
                      {campusColleges.map((college) => {
                        const collegePrograms = programItems.filter(
                          (program) => program.college.id === college.id,
                        );
                        return (
                          <li key={college.id} className="px-4 py-3.5 sm:px-5" aria-labelledby={`college-${college.id}`}>
                            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
                              <div className="min-w-0">
                                <h3
                                  id={`college-${college.id}`}
                                  className="font-heading text-base font-semibold leading-snug text-ink"
                                >
                                  {college.name}
                                </h3>
                                <p className="font-mono text-xs text-muted">{college.code}</p>
                              </div>
                              <StatusBadge active={college.is_active} />
                            </div>

                            {collegePrograms.length === 0 ? (
                              <p className="mt-2 pl-4 text-sm text-muted sm:pl-6">No programs are recorded.</p>
                            ) : (
                              <ul aria-label={`Programs in ${college.name}`} className="mt-2 space-y-0.5 pl-4 sm:pl-6">
                                {collegePrograms.map((program) => (
                                  <li
                                    key={program.id}
                                    className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-0.5 py-1 sm:grid-cols-[minmax(0,1fr)_7rem_auto]"
                                  >
                                    <span className="min-w-0 text-sm text-ink">{program.name}</span>
                                    <span className="col-start-1 row-start-2 font-mono text-xs text-muted sm:col-start-2 sm:row-start-1">{program.code}</span>
                                    <span className="col-start-2 row-start-1 sm:col-start-3"><StatusBadge active={program.is_active} /></span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </li>
                        );
                      })}
                    </ul>
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
