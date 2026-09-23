"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useOrganizationAction } from "@/features/organization/components/organization-action";
import { PeoplePicker } from "@/features/organization/components/people-picker";
import {
  PageHeading,
  QueryError,
  TableSkeleton,
} from "@/features/organization/components/organization-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getOrganizationListCounselorResponsibilitiesQueryKey,
  getOrganizationListStaffSupervisionsQueryKey,
  useOrganizationListColleges,
  useOrganizationListCounselorResponsibilities,
  useOrganizationListStaffSupervisions,
  useOrganizationRemoveCollegeCounselor,
  useOrganizationRemoveStaffSupervisor,
  useOrganizationSetCollegeCounselor,
  useOrganizationSetStaffSupervisor,
} from "@/lib/api/generated/organization/organization";

export function ResponsibilitiesPage() {
  const { user } = usePortalSession();
  const canViewStructure = user.capabilities.includes("organization.view");
  const queryClient = useQueryClient();
  const responsibilities = useOrganizationListCounselorResponsibilities(
    {},
    { query: { retry: false } },
  );
  const colleges = useOrganizationListColleges(
    {},
    { query: { enabled: canViewStructure, retry: false } },
  );
  const supervisions = useOrganizationListStaffSupervisions({
    query: { retry: false },
  });

  const setCollege = useOrganizationSetCollegeCounselor();
  const removeCollege = useOrganizationRemoveCollegeCounselor();
  const setSupervisor = useOrganizationSetStaffSupervisor();
  const removeSupervisor = useOrganizationRemoveStaffSupervisor();
  const action = useOrganizationAction();

  const [collegeDialog, setCollegeDialog] = useState<{
    collegeId: string;
    label: string;
  } | null>(null);
  const [counselorId, setCounselorId] = useState("");
  const [collegeRemoval, setCollegeRemoval] = useState<{
    collegeId: string;
    label: string;
  } | null>(null);

  const [staffDialog, setStaffDialog] = useState<{
    staffId?: string;
    staffLabel?: string;
  } | null>(null);
  const [staffId, setStaffId] = useState("");
  const [supervisorId, setSupervisorId] = useState("");
  const [staffRemoval, setStaffRemoval] = useState<{
    staffId: string;
    label: string;
  } | null>(null);

  const collegePending = setCollege.isPending || removeCollege.isPending;
  const staffPending = setSupervisor.isPending || removeSupervisor.isPending;

  async function refreshCollege() {
    await queryClient.invalidateQueries({
      queryKey: getOrganizationListCounselorResponsibilitiesQueryKey(),
    });
  }

  async function refreshStaff() {
    await queryClient.invalidateQueries({
      queryKey: getOrganizationListStaffSupervisionsQueryKey(),
    });
  }

  function openCollege(
    collegeId: string,
    label: string,
    currentCounselorId = "",
  ) {
    action.setError(null);
    action.setNotice(null);
    setCollegeDialog({ collegeId, label });
    setCounselorId(currentCounselorId);
  }

  async function saveCollege() {
    if (!collegeDialog || !counselorId) return;
    const target = collegeDialog;
    const response = await action.run(
      () =>
        setCollege.mutateAsync({
          collegeId: target.collegeId,
          data: { counselor_id: counselorId },
        }),
      "The responsible Counselor could not be assigned.",
      {
        onStepUpRequired: () => setCollegeDialog(null),
        onStepUpVerified: () => setCollegeDialog(target),
      },
    );
    if (!response) return;
    setCollegeDialog(null);
    action.setNotice("Responsible Counselor updated.");
    await refreshCollege();
  }

  async function confirmRemoveCollege() {
    if (!collegeRemoval) return;
    const target = collegeRemoval;
    const response = await action.run(
      () => removeCollege.mutateAsync({ collegeId: target.collegeId }),
      "The responsible Counselor could not be removed.",
      {
        onStepUpRequired: () => setCollegeRemoval(null),
        onStepUpVerified: () => setCollegeRemoval(target),
      },
    );
    if (!response) return;
    setCollegeRemoval(null);
    action.setNotice("Responsible Counselor removed.");
    await refreshCollege();
  }

  function openStaff(
    existingStaffId?: string,
    staffLabel?: string,
    currentSupervisorId = "",
  ) {
    action.setError(null);
    action.setNotice(null);
    setStaffDialog({ staffId: existingStaffId, staffLabel });
    setStaffId(existingStaffId ?? "");
    setSupervisorId(currentSupervisorId);
  }

  async function saveStaff() {
    if (!staffDialog || !staffId || !supervisorId) return;
    const target = staffDialog;
    const response = await action.run(
      () =>
        setSupervisor.mutateAsync({
          staffId,
          data: { supervisor_id: supervisorId },
        }),
      "The Staff supervisor could not be assigned.",
      {
        onStepUpRequired: () => setStaffDialog(null),
        onStepUpVerified: () => setStaffDialog(target),
      },
    );
    if (!response) return;
    setStaffDialog(null);
    action.setNotice("Staff supervisor updated.");
    await refreshStaff();
  }

  async function confirmRemoveStaff() {
    if (!staffRemoval) return;
    const target = staffRemoval;
    const response = await action.run(
      () => removeSupervisor.mutateAsync({ staffId: target.staffId }),
      "The Staff supervisor could not be removed.",
      {
        onStepUpRequired: () => setStaffRemoval(null),
        onStepUpVerified: () => setStaffRemoval(target),
      },
    );
    if (!response) return;
    setStaffRemoval(null);
    action.setNotice("Staff supervisor removed.");
    await refreshStaff();
  }

  const assignmentByCollege = new Map(
    responsibilities.data?.data.items.map((item) => [item.college.id, item]) ??
      [],
  );
  const collegeRows =
    canViewStructure && colleges.data
      ? colleges.data.data.items.map((college) => ({
          college,
          assignment: assignmentByCollege.get(college.id),
        }))
      : (responsibilities.data?.data.items.map((assignment) => ({
          college: assignment.college,
          assignment,
        })) ?? []);

  return (
    <section>
      <PageHeading title="Responsibilities" />
      <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
        Organization responsibility defines default institutional routing. It
        does not by itself grant blanket access to confidential records.
      </p>
      {action.notice &&
      !collegeDialog &&
      !collegeRemoval &&
      !staffDialog &&
      !staffRemoval
        ? action.messages
        : null}

      <section className="mt-10" aria-labelledby="college-counselors-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2
              id="college-counselors-heading"
              className="font-heading text-2xl font-semibold text-ink"
            >
              College counselors
            </h2>
            <p className="mt-2 text-sm text-muted">
              One explicit responsible Counselor may be assigned to each
              College. Head Guidance fallback remains backend-owned.
            </p>
          </div>
        </div>

        {responsibilities.isPending ||
        (canViewStructure && colleges.isPending) ? (
          <TableSkeleton />
        ) : responsibilities.isError ? (
          <div className="mt-5">
            <QueryError
              error={responsibilities.error}
              fallback="College Counselor responsibilities could not be loaded."
              onRetry={() => void responsibilities.refetch()}
            />
          </div>
        ) : canViewStructure && colleges.isError ? (
          <div className="mt-5">
            <QueryError
              error={colleges.error}
              fallback="College structure could not be loaded."
              onRetry={() => void colleges.refetch()}
            />
          </div>
        ) : collegeRows.length === 0 ? (
          <p className="mt-5 border-y border-border py-8 text-sm text-muted">
            No College Counselor responsibilities are configured.
          </p>
        ) : (
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[42rem] border-collapse text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    College
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Campus
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Responsible Counselor
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {collegeRows.map(({ college, assignment }) => (
                  <tr key={college.id} className="border-t border-border">
                    <th scope="row" className="px-4 py-4 font-semibold text-ink">
                      {college.name}
                    </th>
                    <td className="px-4 py-4">{college.campus.name}</td>
                    <td className="px-4 py-4">
                      {assignment?.counselor.display_name ?? "Not assigned"}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="quiet"
                          onClick={() =>
                            openCollege(
                              college.id,
                              college.name,
                              assignment?.counselor.id,
                            )
                          }
                        >
                          {assignment ? "Reassign" : "Assign"}
                        </Button>
                        {assignment ? (
                          <Button
                            variant="quiet"
                            onClick={() =>
                              setCollegeRemoval({
                                collegeId: college.id,
                                label: college.name,
                              })
                            }
                          >
                            Remove
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!canViewStructure ? (
          <p className="mt-3 text-xs leading-5 text-muted">
            Structure viewing is not available in this capability combination,
            so COMPASS shows only explicit College responsibilities returned by
            the manager API. It does not invent unassigned College choices.
          </p>
        ) : null}
      </section>

      <section className="mt-12" aria-labelledby="staff-supervision-heading">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2
              id="staff-supervision-heading"
              className="font-heading text-2xl font-semibold text-ink"
            >
              Staff supervision
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
              Guidance Services Staff inherit their supervising Counselor&apos;s
              organizational responsibility scope where COMPASS workflows use
              that scope.
            </p>
          </div>
          <Button onClick={() => openStaff()}>Set supervisor</Button>
        </div>

        {supervisions.isPending ? (
          <TableSkeleton />
        ) : supervisions.isError ? (
          <div className="mt-5">
            <QueryError
              error={supervisions.error}
              fallback="Staff supervision relationships could not be loaded."
              onRetry={() => void supervisions.refetch()}
            />
          </div>
        ) : supervisions.data.data.items.length === 0 ? (
          <p className="mt-5 border-y border-border py-8 text-sm text-muted">
            No Staff supervision relationships are configured.
          </p>
        ) : (
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
              <thead className="bg-surface-subtle text-xs font-semibold uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Guidance Services Staff
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Supervisor
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {supervisions.data.data.items.map((item) => (
                  <tr key={item.staff.id} className="border-t border-border">
                    <th scope="row" className="px-4 py-4 font-semibold text-ink">
                      {item.staff.display_name}
                    </th>
                    <td className="px-4 py-4">
                      {item.supervisor.display_name}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="quiet"
                          onClick={() =>
                            openStaff(
                              item.staff.id,
                              item.staff.display_name,
                              item.supervisor.id,
                            )
                          }
                        >
                          Change supervisor
                        </Button>
                        <Button
                          variant="quiet"
                          onClick={() =>
                            setStaffRemoval({
                              staffId: item.staff.id,
                              label: item.staff.display_name,
                            })
                          }
                        >
                          Remove
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Dialog
        open={Boolean(collegeDialog)}
        onOpenChange={(open) => {
          if (collegePending) return;
          if (!open) {
            setCollegeDialog(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <DialogContent>
          <DialogTitle>Set responsible Counselor</DialogTitle>
          <DialogDescription>
            {collegeDialog
              ? `Choose the explicit responsible Counselor for ${collegeDialog.label}.`
              : "Choose a Counselor."}
          </DialogDescription>
          <div className="mt-6">
            <PeoplePicker
              id="college-counselor-search"
              label="Counselor"
              role="COUNSELOR"
              enabled={Boolean(collegeDialog)}
              value={counselorId}
              onChange={setCounselorId}
            />
          </div>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={collegePending}
              onClick={() => setCollegeDialog(null)}
            >
              Cancel
            </Button>
            <Button
              disabled={collegePending || !counselorId}
              onClick={() => void saveCollege()}
            >
              {setCollege.isPending ? "Saving…" : "Assign Counselor"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(collegeRemoval)}
        onOpenChange={(open) => {
          if (collegePending) return;
          if (!open) {
            setCollegeRemoval(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>Remove responsible Counselor?</AlertDialogTitle>
          <AlertDialogDescription>
            {collegeRemoval
              ? `${collegeRemoval.label} will no longer have an explicit responsible Counselor. Default routing may use other canonical fallback behavior.`
              : "The explicit responsibility will be removed."}
          </AlertDialogDescription>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={collegePending}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant="danger"
              disabled={collegePending}
              onClick={() => void confirmRemoveCollege()}
            >
              {removeCollege.isPending ? "Removing…" : "Remove Counselor"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={Boolean(staffDialog)}
        onOpenChange={(open) => {
          if (staffPending) return;
          if (!open) {
            setStaffDialog(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <DialogContent className="max-w-xl">
          <DialogTitle>Set Staff supervisor</DialogTitle>
          <DialogDescription>
            Assign one supervising Counselor. This does not create a direct
            Staff-to-College relationship.
          </DialogDescription>
          <div className="mt-6 space-y-6">
            {staffDialog?.staffId ? (
              <div>
                <p className="text-sm font-semibold text-ink">
                  Guidance Services Staff
                </p>
                <p className="mt-2 rounded-md border border-border bg-surface-muted px-3 py-2 text-sm text-ink">
                  {staffDialog.staffLabel}
                </p>
              </div>
            ) : (
              <PeoplePicker
                id="staff-person-search"
                label="Guidance Services Staff"
                role="GUIDANCE_SERVICES_STAFF"
                enabled={Boolean(staffDialog)}
                value={staffId}
                onChange={setStaffId}
              />
            )}
            <PeoplePicker
              id="staff-supervisor-search"
              label="Supervising Counselor"
              role="COUNSELOR"
              enabled={Boolean(staffDialog)}
              value={supervisorId}
              onChange={setSupervisorId}
            />
          </div>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={staffPending}
              onClick={() => setStaffDialog(null)}
            >
              Cancel
            </Button>
            <Button
              disabled={staffPending || !staffId || !supervisorId}
              onClick={() => void saveStaff()}
            >
              {setSupervisor.isPending ? "Saving…" : "Set supervisor"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={Boolean(staffRemoval)}
        onOpenChange={(open) => {
          if (staffPending) return;
          if (!open) {
            setStaffRemoval(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>Remove supervisor?</AlertDialogTitle>
          <AlertDialogDescription>
            {staffRemoval
              ? `${staffRemoval.label} will no longer inherit a Counselor's organizational responsibility scope.`
              : "The Staff supervision relationship will be removed."}
          </AlertDialogDescription>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={staffPending}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant="danger"
              disabled={staffPending}
              onClick={() => void confirmRemoveStaff()}
            >
              {removeSupervisor.isPending ? "Removing…" : "Remove supervisor"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </section>
  );
}
