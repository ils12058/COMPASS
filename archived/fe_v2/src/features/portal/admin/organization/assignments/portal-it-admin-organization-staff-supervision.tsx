"use client";

import { useState } from "react";
import { Check, UserRound, UsersRound } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  getOrganizationListStaffSupervisionsQueryKey,
  useOrganizationListEligiblePeople,
  useOrganizationListStaffSupervisions,
  useOrganizationRemoveStaffSupervisor,
  useOrganizationSetStaffSupervisor,
} from "@/lib/api/generated/organization/organization";
import { OrganizationListEligiblePeopleRole } from "@/lib/api/generated/model";
import {
  AssignmentEmptyState,
  AssignmentListSkeleton,
  AssignmentPerson,
  AssignmentQueryError,
  AssignmentSection,
  OrganizationActionMessage,
} from "@/features/portal/admin/organization/assignments/portal-it-admin-organization-assignment-shared";
import { organizationAdminError, organizationSelectClassName } from "@/features/portal/admin/organization/portal-it-admin-organization-shared";

export function PortalItAdminOrganizationStaffSupervision() {
  const queryClient = useQueryClient();
  const [selections, setSelections] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const supervisionQuery = useOrganizationListStaffSupervisions({
    query: { retry: false, staleTime: 30_000 },
  });
  const staffQuery = useOrganizationListEligiblePeople(
    {
      role: OrganizationListEligiblePeopleRole.GUIDANCE_SERVICES_STAFF,
      page: 1,
      page_size: 100,
    },
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
  const setSupervisor = useOrganizationSetStaffSupervisor();
  const removeSupervisor = useOrganizationRemoveStaffSupervisor();
  const supervisions = supervisionQuery.data?.data.items ?? [];
  const staff = staffQuery.data?.data.items ?? [];
  const counselors = counselorsQuery.data?.data.items ?? [];
  const supervisionByStaff = new Map(supervisions.map((item) => [item.staff.id, item]));
  const isMutating = setSupervisor.isPending || removeSupervisor.isPending;
  const hasError = supervisionQuery.isError || staffQuery.isError || counselorsQuery.isError;

  function selectedSupervisorId(staffId: string) {
    return selections[staffId] ?? supervisionByStaff.get(staffId)?.supervisor.id ?? "";
  }

  async function saveAssignment(staffId: string, staffName: string) {
    const supervisorId = selectedSupervisorId(staffId);
    const current = supervisionByStaff.get(staffId)?.supervisor.id ?? "";
    setError(null);
    setMessage(null);

    if (!supervisorId) {
      setError("Choose a counselor before saving this supervision relationship.");
      return;
    }

    if (supervisorId === current) {
      setMessage("No change to save for this staff member.");
      return;
    }

    try {
      await setSupervisor.mutateAsync({
        staffId,
        data: { supervisor_id: supervisorId },
      });
      setMessage(`Supervisor updated for ${staffName}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListStaffSupervisionsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t update this supervision relationship. Please try again."));
    }
  }

  async function removeAssignment(staffId: string, staffName: string) {
    if (!supervisionByStaff.has(staffId)) {
      return;
    }

    if (!window.confirm(`Remove the supervisor for ${staffName}?`)) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      await removeSupervisor.mutateAsync({ staffId });
      setSelections((current) => ({ ...current, [staffId]: "" }));
      setMessage(`Supervisor removed from ${staffName}.`);
      await queryClient.invalidateQueries({ queryKey: getOrganizationListStaffSupervisionsQueryKey() });
    } catch (caught) {
      setError(organizationAdminError(caught, "We couldn’t remove this supervision relationship. Please try again."));
    }
  }

  return (
    <AssignmentSection
      icon={UsersRound}
      title="Staff supervision"
      description="Assign a counselor to supervise each Guidance Services Staff account when that relationship is part of the operating model."
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm text-muted-foreground">
              {supervisions.length} assigned {supervisions.length === 1 ? "staff member" : "staff members"}
            </p>
          </div>
          <p className="text-xs text-muted-foreground">Eligible supervisors are active counselor accounts.</p>
        </div>

        <OrganizationActionMessage error={error} message={message} />

        {hasError ? (
          <AssignmentQueryError
            onRetry={() => {
              void supervisionQuery.refetch();
              void staffQuery.refetch();
              void counselorsQuery.refetch();
            }}
          />
        ) : supervisionQuery.isPending || staffQuery.isPending || counselorsQuery.isPending ? (
          <AssignmentListSkeleton />
        ) : !staff.length ? (
          <AssignmentEmptyState
            title="No staff accounts to assign"
            description="Create or activate Guidance Services Staff accounts before setting supervision relationships."
          />
        ) : !counselors.length ? (
          <AssignmentEmptyState
            title="No eligible supervisors"
            description="Create or activate a counselor account before assigning supervision."
          />
        ) : (
          <div className="space-y-3">
            {staff.map((staffMember) => {
              const supervision = supervisionByStaff.get(staffMember.id);

              return (
                <article key={staffMember.id} className="rounded-2xl border border-[var(--compass-border)] bg-card p-4 shadow-sm sm:p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)]/10 text-[var(--compass-brand-maroon)]">
                        <UserRound aria-hidden="true" className="size-5" />
                      </span>
                      <div className="min-w-0">
                        <h3 className="break-words font-semibold"><AssignmentPerson person={staffMember} /></h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {supervision ? <>Current supervisor: <AssignmentPerson person={supervision.supervisor} /></> : "No supervisor assigned yet."}
                        </p>
                      </div>
                    </div>
                    <div className="flex min-w-0 flex-col gap-2 lg:w-80">
                      <Label htmlFor={`supervisor-for-${staffMember.id}`} className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                        Assign supervisor
                      </Label>
                      <div className="flex flex-col gap-2 sm:flex-row lg:flex-col xl:flex-row">
                        <select
                          id={`supervisor-for-${staffMember.id}`}
                          className={organizationSelectClassName}
                          value={selectedSupervisorId(staffMember.id)}
                          onChange={(event) => setSelections((current) => ({ ...current, [staffMember.id]: event.target.value }))}
                        >
                          <option value="">Choose a counselor</option>
                          {counselors.map((counselor) => (
                            <option key={counselor.id} value={counselor.id}>{counselor.display_name}</option>
                          ))}
                        </select>
                        <Button type="button" disabled={isMutating} onClick={() => void saveAssignment(staffMember.id, staffMember.display_name)}>
                          <Check aria-hidden="true" />
                          {setSupervisor.isPending ? "Saving…" : "Save"}
                        </Button>
                      </div>
                      {supervision ? (
                        <Button type="button" variant="ghost" size="sm" className="self-start" disabled={isMutating} onClick={() => void removeAssignment(staffMember.id, staffMember.display_name)}>
                          Remove supervisor
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
