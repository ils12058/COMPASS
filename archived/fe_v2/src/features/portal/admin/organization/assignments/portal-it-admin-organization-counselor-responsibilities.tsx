"use client";

import { useState } from "react";
import { Building2, Check, UserRound } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  getOrganizationListCounselorResponsibilitiesQueryKey,
  useOrganizationListCampuses,
  useOrganizationListColleges,
  useOrganizationListCounselorResponsibilities,
  useOrganizationListEligiblePeople,
  useOrganizationRemoveCollegeCounselor,
  useOrganizationSetCollegeCounselor,
} from "@/lib/api/generated/organization/organization";
import { OrganizationListEligiblePeopleRole } from "@/lib/api/generated/model";
import type { CollegeSummary } from "@/lib/api/generated/model";
import {
  AssignmentEmptyState,
  AssignmentListSkeleton,
  AssignmentPerson,
  AssignmentQueryError,
  AssignmentSection,
  OrganizationActionMessage,
} from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-assignment-shared";
import {
  OrganizationStatusBadge,
  organizationAdminError,
  organizationSelectClassName,
} from "@/features/portal/admin/organization/portal-it-admin-organization-shared";

export function PortalItAdminOrganizationCounselorResponsibilities() {
  const queryClient = useQueryClient();
  const [campusFilter, setCampusFilter] = useState("");
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const campusesQuery = useOrganizationListCampuses(undefined, {
    query: { retry: false, staleTime: 30_000 },
  });
  const collegesQuery = useOrganizationListColleges(
    { campus_id: campusFilter || undefined },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const responsibilitiesQuery = useOrganizationListCounselorResponsibilities(
    { campus_id: campusFilter || undefined },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const counselorsQuery = useOrganizationListEligiblePeople(
    {
      role: OrganizationListEligiblePeopleRole.COUNSELOR,
      page: 1,
      page_size: 100,
    },
    { query: { retry: false, staleTime: 30_000 } },
  );
  const setCounselor = useOrganizationSetCollegeCounselor();
  const removeCounselor = useOrganizationRemoveCollegeCounselor();
  const campuses = campusesQuery.data?.data.items ?? [];
  const colleges = collegesQuery.data?.data.items ?? [];
  const responsibilities = responsibilitiesQuery.data?.data.items ?? [];
  const counselors = counselorsQuery.data?.data.items ?? [];
  const assignmentsByCollege = new Map(
    responsibilities.map((item) => [item.college.id, item]),
  );
  const isMutating = setCounselor.isPending || removeCounselor.isPending;
  const hasError =
    campusesQuery.isError ||
    collegesQuery.isError ||
    responsibilitiesQuery.isError ||
    counselorsQuery.isError;

  function selectedCounselorId(college: CollegeSummary) {
    return selections[college.id] ?? assignmentsByCollege.get(college.id)?.counselor.id ?? "";
  }

  async function saveAssignment(college: CollegeSummary) {
    const counselorId = selectedCounselorId(college);
    const current = assignmentsByCollege.get(college.id)?.counselor.id ?? "";
    setError(null);
    setMessage(null);

    if (!counselorId) {
      setError("Choose a counselor before saving this responsibility.");
      return;
    }

    if (counselorId === current) {
      setMessage("No change to save for this college.");
      return;
    }

    try {
      await setCounselor.mutateAsync({
        collegeId: college.id,
        data: { counselor_id: counselorId },
      });
      setMessage(`Counselor responsibility updated for ${college.name}.`);
      await queryClient.invalidateQueries({
        queryKey: getOrganizationListCounselorResponsibilitiesQueryKey(),
      });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t update this counselor responsibility. Please try again."));
    }
  }

  async function removeAssignment(college: CollegeSummary) {
    if (!assignmentsByCollege.has(college.id)) {
      return;
    }

    if (!window.confirm(`Remove the counselor responsibility for ${college.name}?`)) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      await removeCounselor.mutateAsync({ collegeId: college.id });
      setSelections((current) => ({ ...current, [college.id]: "" }));
      setMessage(`Counselor responsibility removed from ${college.name}.`);
      await queryClient.invalidateQueries({
        queryKey: getOrganizationListCounselorResponsibilitiesQueryKey(),
      });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t remove this counselor responsibility. Please try again."));
    }
  }

  return (
    <AssignmentSection
      icon={UserRound}
      title="Counselor responsibilities"
      description="Assign one counselor to each college for default responsibility routing."
    >
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <Label htmlFor="counselor-responsibility-campus">Campus filter</Label>
            <select
              id="counselor-responsibility-campus"
              className={`${organizationSelectClassName} mt-2 sm:w-72`}
              value={campusFilter}
              onChange={(event) => setCampusFilter(event.target.value)}
            >
              <option value="">All campuses</option>
              {campuses.map((campus) => (
                <option key={campus.id} value={campus.id}>{campus.name}</option>
              ))}
            </select>
          </div>
          <p className="text-sm text-muted-foreground">
            {responsibilities.length} assigned {responsibilities.length === 1 ? "college" : "colleges"}
          </p>
        </div>

        <OrganizationActionMessage error={error} message={message} />

        {hasError ? (
          <AssignmentQueryError
            onRetry={() => {
              void campusesQuery.refetch();
              void collegesQuery.refetch();
              void responsibilitiesQuery.refetch();
              void counselorsQuery.refetch();
            }}
          />
        ) : collegesQuery.isPending || responsibilitiesQuery.isPending || counselorsQuery.isPending ? (
          <AssignmentListSkeleton />
        ) : !colleges.length ? (
          <AssignmentEmptyState
            title="No colleges to assign"
            description="Create an active college under Organization before assigning a counselor."
          />
        ) : !counselors.length ? (
          <AssignmentEmptyState
            title="No eligible counselors"
            description="Create or activate a counselor account before assigning college responsibilities."
          />
        ) : (
          <div className="space-y-3">
            {colleges.map((college) => {
              const assignment = assignmentsByCollege.get(college.id);

              return (
                <article key={college.id} className="rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm sm:p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                        <Building2 aria-hidden="true" className="size-5" />
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="break-words font-semibold">{college.name}</h3>
                          <Badge variant="outline">{college.code}</Badge>
                          <OrganizationStatusBadge active={college.is_active} />
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">{college.campus.name}</p>
                        <p className="mt-2 text-sm text-muted-foreground">
                          {assignment ? <>Current counselor: <AssignmentPerson person={assignment.counselor} /></> : "No counselor assigned yet."}
                        </p>
                      </div>
                    </div>
                    <div className="flex min-w-0 flex-col gap-2 lg:w-80">
                      <Label htmlFor={`counselor-for-${college.id}`} className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                        Assign counselor
                      </Label>
                      <div className="flex flex-col gap-2 sm:flex-row lg:flex-col xl:flex-row">
                        <select
                          id={`counselor-for-${college.id}`}
                          className={organizationSelectClassName}
                          value={selectedCounselorId(college)}
                          onChange={(event) => setSelections((current) => ({ ...current, [college.id]: event.target.value }))}
                        >
                          <option value="">Choose a counselor</option>
                          {counselors.map((counselor) => (
                            <option key={counselor.id} value={counselor.id}>{counselor.display_name}</option>
                          ))}
                        </select>
                        <Button type="button" disabled={isMutating || !college.is_active} onClick={() => void saveAssignment(college)}>
                          <Check aria-hidden="true" />
                          {setCounselor.isPending ? "Saving…" : "Save"}
                        </Button>
                      </div>
                      {assignment ? (
                        <Button type="button" variant="ghost" size="sm" className="self-start" disabled={isMutating} onClick={() => void removeAssignment(college)}>
                          Remove responsibility
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </AssignmentSection>
  );
}
