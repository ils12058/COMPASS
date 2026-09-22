"use client";

import Link from "next/link";
import { Building2, GraduationCap, Network, School } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AdminMetric } from "@/features/portal/admin/portal-it-admin-shared";
import {
  OrganizationListSkeleton,
  OrganizationQueryError,
  OrganizationStatusBadge,
} from "@/features/portal/admin/organization/portal-it-admin-organization-shared";
import {
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationListPrograms,
} from "@/lib/api/generated/organization/organization";

export function PortalItAdminOrganizationOverview() {
  const campusesQuery = useOrganizationListCampuses(undefined, {
    query: { retry: false, staleTime: 30_000 },
  });
  const collegesQuery = useOrganizationListColleges(undefined, {
    query: { retry: false, staleTime: 30_000 },
  });
  const programsQuery = useOrganizationListPrograms(undefined, {
    query: { retry: false, staleTime: 30_000 },
  });

  const isPending =
    campusesQuery.isPending || collegesQuery.isPending || programsQuery.isPending;
  const hasError =
    campusesQuery.isError || collegesQuery.isError || programsQuery.isError;

  if (isPending) {
    return <OrganizationListSkeleton label="Loading organization overview" />;
  }

  if (hasError) {
    return (
      <OrganizationQueryError
        onRetry={() => {
          void campusesQuery.refetch();
          void collegesQuery.refetch();
          void programsQuery.refetch();
        }}
      />
    );
  }

  const campuses = campusesQuery.data?.data.items ?? [];
  const colleges = collegesQuery.data?.data.items ?? [];
  const programs = programsQuery.data?.data.items ?? [];
  const collegesByCampus = new Map<string, typeof colleges>();
  const programsByCollege = new Map<string, typeof programs>();

  for (const college of colleges) {
    const current = collegesByCampus.get(college.campus.id) ?? [];
    current.push(college);
    collegesByCampus.set(college.campus.id, current);
  }

  for (const program of programs) {
    const current = programsByCollege.get(program.college.id) ?? [];
    current.push(program);
    programsByCollege.set(program.college.id, current);
  }

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <div className="flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
            <Network aria-hidden="true" className="size-5" />
          </span>
          <div>
            <h2 className="font-heading text-2xl font-bold tracking-tight">
              Organization structure
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
              Campuses contain colleges, and colleges contain programs. Keep this structure current so routing and account affiliations have a reliable foundation.
            </p>
          </div>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <AdminMetric label="Campuses" value={campuses.length} />
          <AdminMetric label="Colleges" value={colleges.length} />
          <AdminMetric label="Programs" value={programs.length} />
        </div>
      </section>

      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--compass-brand-gold)]">
              Current structure
            </p>
            <h2 className="mt-2 font-heading text-2xl font-bold tracking-tight">
              How the university is arranged
            </h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href="/portal/admin/organization/campuses">
                <Building2 aria-hidden="true" />
                Campuses
              </Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/portal/admin/organization/programs">
                <GraduationCap aria-hidden="true" />
                Programs
              </Link>
            </Button>
          </div>
        </header>

        {campuses.length ? (
          <div className="mt-6 space-y-4">
            {campuses.map((campus) => {
              const campusColleges = collegesByCampus.get(campus.id) ?? [];

              return (
                <article
                  key={campus.id}
                  className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                        <Building2 aria-hidden="true" className="size-4" />
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="break-words font-semibold">{campus.name}</h3>
                          <Badge variant="outline">{campus.code}</Badge>
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {campusColleges.length} {campusColleges.length === 1 ? "college" : "colleges"}
                        </p>
                      </div>
                    </div>
                    <OrganizationStatusBadge active={campus.is_active} />
                  </div>

                  {campusColleges.length ? (
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      {campusColleges.map((college) => {
                        const collegePrograms = programsByCollege.get(college.id) ?? [];

                        return (
                          <div
                            key={college.id}
                            className="rounded-xl border border-[var(--compass-border)] bg-card p-3"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex min-w-0 items-start gap-2">
                                <School aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-[var(--compass-brand-maroon)]" />
                                <div className="min-w-0">
                                  <p className="break-words font-semibold">{college.name}</p>
                                  <p className="mt-0.5 text-xs text-muted-foreground">{college.code}</p>
                                </div>
                              </div>
                              <OrganizationStatusBadge active={college.is_active} />
                            </div>
                            {collegePrograms.length ? (
                              <ul className="mt-3 space-y-1 border-t border-[var(--compass-border)] pt-3 text-sm text-muted-foreground">
                                {collegePrograms.map((program) => (
                                  <li key={program.id} className="flex items-start gap-2">
                                    <GraduationCap aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                                    <span className="min-w-0 break-words">
                                      {program.name} <span className="text-xs">({program.code})</span>
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="mt-3 border-t border-[var(--compass-border)] pt-3 text-sm text-muted-foreground">
                                No programs recorded yet.
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="mt-4 rounded-xl border border-dashed border-[var(--compass-border-strong)] bg-card p-4 text-sm text-muted-foreground">
                      No colleges recorded under this campus yet.
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          <div className="mt-6 rounded-2xl border border-dashed border-[var(--compass-border-strong)] bg-[var(--compass-surface-subtle)] p-8 text-center">
            <h3 className="font-heading text-xl font-bold">No campuses yet</h3>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted-foreground">
              Start with a campus, then add its colleges and programs from the Organization sections.
            </p>
            <Button asChild className="mt-5">
              <Link href="/portal/admin/organization/campuses">Open campuses</Link>
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
