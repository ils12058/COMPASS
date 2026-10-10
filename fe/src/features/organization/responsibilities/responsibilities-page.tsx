"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ResponsibilitiesHelp } from "@/features/organization/responsibilities/responsibilities-help";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { dataTable } from "@/components/ui/data-table";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { useOrganizationAction } from "@/features/organization/components/organization-action";
import { PeoplePicker } from "@/features/organization/components/people-picker";
import {
  PageHeading,
  PanelQueryError,
  StatusBadge,
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
import type { OrganizationPersonSummary } from "@/lib/api/generated/model";

function supervisionScopeConsequence(supervisor: OrganizationPersonSummary): string {
  return supervisor.responsibility_scope === "ASSIGNED_AND_FALLBACK_COLLEGES"
    ? "This staff member will handle the counselor's assigned colleges and colleges routed to them as the unique active Head."
    : "This staff member will share the counselor's assigned-college responsibilities in COMPASS.";
}

export function ResponsibilitiesPage() {
  const { user } = usePortalSession();
  const canViewStructure = user.capabilities.includes("organization.structure.view");
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
    currentCounselor: OrganizationPersonSummary | null;
  } | null>(null);
  const [counselorId, setCounselorId] = useState("");
  const [selectedCounselor, setSelectedCounselor] =
    useState<OrganizationPersonSummary | null>(null);
  const [collegeReview, setCollegeReview] = useState<{
    collegeId: string;
    collegeLabel: string;
    currentCounselor: OrganizationPersonSummary | null;
    newCounselor: OrganizationPersonSummary;
  } | null>(null);
  const [collegeRemoval, setCollegeRemoval] = useState<{
    collegeId: string;
    label: string;
    currentCounselor: OrganizationPersonSummary;
  } | null>(null);

  const [staffDialog, setStaffDialog] = useState<{
    staff: OrganizationPersonSummary | null;
  } | null>(null);
  const [staffId, setStaffId] = useState("");
  const [selectedStaff, setSelectedStaff] =
    useState<OrganizationPersonSummary | null>(null);
  const [supervisorId, setSupervisorId] = useState("");
  const [selectedSupervisor, setSelectedSupervisor] =
    useState<OrganizationPersonSummary | null>(null);
  const [staffReview, setStaffReview] = useState<{
    staff: OrganizationPersonSummary;
    currentSupervisor: OrganizationPersonSummary | null;
    newSupervisor: OrganizationPersonSummary;
  } | null>(null);
  const [staffRemoval, setStaffRemoval] = useState<{
    staff: OrganizationPersonSummary;
    supervisor: OrganizationPersonSummary;
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
    currentCounselor: OrganizationPersonSummary | null = null,
  ) {
    action.setError(null);
    action.setNotice(null);
    setCollegeDialog({ collegeId, label, currentCounselor });
    setCounselorId(currentCounselor?.id ?? "");
    setSelectedCounselor(currentCounselor);
  }

  function reviewCollege() {
    if (!collegeDialog || !selectedCounselor) return;
    if (collegeDialog.currentCounselor?.id === selectedCounselor.id) return;
    setCollegeReview({
      collegeId: collegeDialog.collegeId,
      collegeLabel: collegeDialog.label,
      currentCounselor: collegeDialog.currentCounselor,
      newCounselor: selectedCounselor,
    });
    setCollegeDialog(null);
    action.setError(null);
  }

  async function confirmCollege() {
    if (!collegeReview) return;
    const target = collegeReview;
    const response = await action.run(
      () =>
        setCollege.mutateAsync({
          collegeId: target.collegeId,
          data: { counselor_id: target.newCounselor.id },
        }),
      "The responsible Counselor could not be assigned.",
      {
        onStepUpRequired: () => setCollegeReview(null),
        onStepUpVerified: () => setCollegeReview(target),
      },
    );
    if (!response) return;
    setCollegeReview(null);
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
    staff: OrganizationPersonSummary | null = null,
    currentSupervisor: OrganizationPersonSummary | null = null,
  ) {
    action.setError(null);
    action.setNotice(null);
    setStaffDialog({ staff });
    setStaffId(staff?.id ?? "");
    setSelectedStaff(staff);
    setSupervisorId(currentSupervisor?.id ?? "");
    setSelectedSupervisor(currentSupervisor);
  }

  function reviewStaff() {
    if (!staffDialog || !selectedStaff || !selectedSupervisor) return;
    const currentSupervisor =
      supervisions.data?.data.items.find(
        (item) => item.staff.id === selectedStaff.id,
      )?.supervisor ?? null;
    if (currentSupervisor?.id === selectedSupervisor.id) return;
    setStaffReview({
      staff: selectedStaff,
      currentSupervisor,
      newSupervisor: selectedSupervisor,
    });
    setStaffDialog(null);
    action.setError(null);
  }

  async function confirmStaff() {
    if (!staffReview) return;
    const target = staffReview;
    const response = await action.run(
      () =>
        setSupervisor.mutateAsync({
          staffId: target.staff.id,
          data: { supervisor_id: target.newSupervisor.id },
        }),
      "The Staff supervisor could not be assigned.",
      {
        onStepUpRequired: () => setStaffReview(null),
        onStepUpVerified: () => setStaffReview(target),
      },
    );
    if (!response) return;
    setStaffReview(null);
    action.setNotice(
      target.currentSupervisor ? "Staff supervisor changed." : "Staff supervisor assigned.",
    );
    await refreshStaff();
  }

  async function confirmRemoveStaff() {
    if (!staffRemoval) return;
    const target = staffRemoval;
    const response = await action.run(
      () => removeSupervisor.mutateAsync({ staffId: target.staff.id }),
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
    <section aria-labelledby="responsibilities-heading">
      <PageHeading
        title="Responsibilities"
        headingId="responsibilities-heading"
        help={<ResponsibilitiesHelp />}
      />
      {action.notice &&
      !collegeDialog &&
      !collegeReview &&
      !collegeRemoval &&
      !staffDialog &&
      !staffReview &&
      !staffRemoval
        ? action.messages
        : null}

      <Panel className="mt-5" aria-labelledby="college-counselors-heading">
        <PanelHeader
          title="College counselors"
          titleId="college-counselors-heading"
        />

        {responsibilities.isPending ||
        (canViewStructure && colleges.isPending) ? (
          <TableSkeleton />
        ) : responsibilities.isError ? (
          <PanelQueryError
            error={responsibilities.error}
            fallback="College Counselor responsibilities could not be loaded."
            onRetry={() => void responsibilities.refetch()}
          />
        ) : canViewStructure && colleges.isError ? (
          <PanelQueryError
            error={colleges.error}
            fallback="College structure could not be loaded."
            onRetry={() => void colleges.refetch()}
          />
        ) : collegeRows.length === 0 ? (
          <PanelMessage>
            No college counselor responsibilities have been assigned.
          </PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[42rem]`}>
              <caption className="sr-only">College counselors</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>
                    College
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Campus
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Responsible Counselor
                  </th>
                  <th scope="col" className={`${dataTable.headerCell} text-right`}>
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {collegeRows.map(({ college, assignment }) => (
                  <tr key={college.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-semibold text-ink`}>
                      {college.name}
                    </th>
                    <td className={dataTable.cell}>{college.campus.name}</td>
                    <td className={dataTable.cell}>
                      {assignment ? (
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-ink">
                              {assignment.counselor.full_name}
                            </span>
                            <StatusBadge active={assignment.counselor.is_active} />
                          </div>
                          <p className="text-xs text-muted">
                            {assignment.counselor.email}
                          </p>
                        </div>
                      ) : (
                        "Not assigned"
                      )}
                    </td>
                    <td className={`${dataTable.cell} py-2`}>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="quiet"
                          onClick={() =>
                            openCollege(
                              college.id,
                              college.name,
                              assignment?.counselor ?? null,
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
                                currentCounselor: assignment.counselor,
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
          <p className="border-t border-brand-line px-4 py-3 text-xs leading-5 text-muted sm:px-5">
            Only Colleges with an assigned Counselor are shown. College structure is unavailable.
          </p>
        ) : null}
      </Panel>

      <Panel className="mt-5" aria-labelledby="staff-supervision-heading">
        <PanelHeader
          title="Staff supervision"
          titleId="staff-supervision-heading"
          actions={<Button onClick={() => openStaff()}>Set supervisor</Button>}
        />

        {supervisions.isPending ? (
          <TableSkeleton />
        ) : supervisions.isError ? (
          <PanelQueryError
            error={supervisions.error}
            fallback="Staff supervision relationships could not be loaded."
            onRetry={() => void supervisions.refetch()}
          />
        ) : supervisions.data.data.items.length === 0 ? (
          <PanelMessage>
            No staff supervision relationships have been assigned.
          </PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[36rem]`}>
              <caption className="sr-only">Staff supervision</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>
                    Guidance Services Staff
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Supervisor
                  </th>
                  <th scope="col" className={`${dataTable.headerCell} text-right`}>
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {supervisions.data.data.items.map((item) => (
                  <tr key={item.staff.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} font-normal`}>
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-ink">
                            {item.staff.full_name}
                          </span>
                          <StatusBadge active={item.staff.is_active} />
                        </div>
                        <p className="text-xs text-muted">{item.staff.email}</p>
                      </div>
                    </th>
                    <td className={dataTable.cell}>
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-ink">
                            {item.supervisor.full_name}
                          </span>
                          <StatusBadge active={item.supervisor.is_active} />
                        </div>
                        <p className="text-xs text-muted">{item.supervisor.email}</p>
                      </div>
                    </td>
                    <td className={`${dataTable.cell} py-2`}>
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="quiet"
                          onClick={() =>
                            openStaff(item.staff, item.supervisor)
                          }
                        >
                          Change supervisor
                        </Button>
                        <Button
                          variant="quiet"
                          onClick={() =>
                            setStaffRemoval({
                              staff: item.staff,
                              supervisor: item.supervisor,
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
      </Panel>

      <Dialog
        open={Boolean(collegeDialog)}
        onOpenChange={(open) => {
          if (!open) {
            setCollegeDialog(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <DialogContent dismissible={!collegePending}>
          <DialogTitle>
            {collegeDialog?.currentCounselor
              ? "Reassign responsible Counselor"
              : "Assign responsible Counselor"}
          </DialogTitle>
          <DialogDescription>
            {collegeDialog
              ? `Choose a Counselor for ${collegeDialog.label}, then review the assignment.`
              : "Choose a Counselor."}
          </DialogDescription>
          <div className="mt-6">
            <PeoplePicker
              id="college-counselor-search"
              label="Counselor"
              role="COUNSELOR"
              enabled={Boolean(collegeDialog)}
              value={counselorId}
              selectedPerson={selectedCounselor}
              onChange={(id, person) => {
                setCounselorId(id);
                setSelectedCounselor(person);
              }}
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
              disabled={
                collegePending ||
                !selectedCounselor ||
                collegeDialog?.currentCounselor?.id === selectedCounselor.id
              }
              onClick={reviewCollege}
            >
              {collegeDialog?.currentCounselor
                ? "Review reassignment"
                : "Review assignment"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConsequentialActionDialog
        open={collegeReview !== null}
        title={
          collegeReview
            ? `${collegeReview.currentCounselor ? "Reassign" : "Assign"} responsible Counselor for ${collegeReview.collegeLabel}?`
            : "Review responsible Counselor"
        }
        confirmLabel={
          collegeReview?.currentCounselor
            ? "Change responsible Counselor"
            : "Assign responsible Counselor"
        }
        pendingLabel={collegeReview?.currentCounselor ? "Changing…" : "Assigning…"}
        pending={collegePending}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setCollegeReview(null);
        }}
        onConfirm={() => void confirmCollege()}
      >
        {collegeReview ? (
          <>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-muted">College</dt>
                <dd className="font-semibold text-ink">{collegeReview.collegeLabel}</dd>
              </div>
              <div>
                <dt className="text-muted">Current responsible Counselor</dt>
                <dd className="font-semibold text-ink">
                  {collegeReview.currentCounselor?.full_name ?? "None"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">New responsible Counselor</dt>
                <dd className="font-semibold text-ink">{collegeReview.newCounselor.full_name}</dd>
              </div>
            </dl>
            <p>This changes the College&apos;s counselor for default routing. It does not grant blanket confidential-record access.</p>
          </>
        ) : null}
      </ConsequentialActionDialog>

      <ConsequentialActionDialog
        open={collegeRemoval !== null}
        title={
          collegeRemoval
            ? `Remove ${collegeRemoval.currentCounselor.full_name} as the responsible Counselor for ${collegeRemoval.label}?`
            : "Remove responsible Counselor?"
        }
        confirmLabel="Remove responsible Counselor"
        pendingLabel="Removing…"
        pending={collegePending}
        error={action.error}
        variant="danger"
        onOpenChange={(open) => {
          if (!open) {
            setCollegeRemoval(null);
            action.setError(null);
          }
        }}
        onConfirm={() => void confirmRemoveCollege()}
      >
        <p>
          {collegeRemoval
            ? `${collegeRemoval.label} will no longer have an assigned Counselor. Default routing uses the Head Guidance Counselor only when exactly one active Head Guidance Counselor is available.`
            : "The Counselor assignment will be removed."}
        </p>
      </ConsequentialActionDialog>

      <Dialog
        open={Boolean(staffDialog)}
        onOpenChange={(open) => {
          if (!open) {
            setStaffDialog(null);
            action.setError(null);
            action.setNotice(null);
          }
        }}
      >
        <DialogContent className="max-w-xl" dismissible={!staffPending}>
          <DialogTitle>
            {staffDialog?.staff ? "Change Staff supervisor" : "Set Staff supervisor"}
          </DialogTitle>
          <DialogDescription>
            Choose a supervising Counselor, then review the assignment.
          </DialogDescription>
          <div className="mt-6 space-y-6">
            {staffDialog?.staff ? (
              <div>
                <p className="text-sm font-semibold text-ink">Guidance Services Staff</p>
                <div className="mt-2 rounded-sm border border-brand-line bg-brand-wash px-3 py-3 text-sm">
                  <p className="font-semibold text-ink">{staffDialog.staff.full_name}</p>
                  <p className="mt-1 text-xs text-muted">
                    {staffDialog.staff.institutional_id
                      ? `${staffDialog.staff.institutional_id} · ${staffDialog.staff.email}`
                      : staffDialog.staff.email}
                  </p>
                </div>
              </div>
            ) : (
              <PeoplePicker
                id="staff-person-search"
                label="Guidance Services Staff"
                role="GUIDANCE_SERVICES_STAFF"
                enabled={Boolean(staffDialog)}
                value={staffId}
                selectedPerson={selectedStaff}
                onChange={(id, person) => {
                  setStaffId(id);
                  setSelectedStaff(person);
                }}
              />
            )}
            <PeoplePicker
              id="staff-supervisor-search"
              label="Supervising Counselor"
              role="COUNSELOR"
              enabled={Boolean(staffDialog)}
              value={supervisorId}
              selectedPerson={selectedSupervisor}
              onChange={(id, person) => {
                setSupervisorId(id);
                setSelectedSupervisor(person);
              }}
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
              disabled={
                staffPending ||
                !selectedStaff ||
                !selectedSupervisor ||
                supervisions.data?.data.items.find(
                  (item) => item.staff.id === selectedStaff.id,
                )?.supervisor.id === selectedSupervisor.id
              }
              onClick={reviewStaff}
            >
              Review supervisor
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConsequentialActionDialog
        open={staffReview !== null}
        title={
          staffReview
            ? `${staffReview.currentSupervisor ? "Change" : "Assign"} supervisor for ${staffReview.staff.full_name}?`
            : "Review Staff supervisor"
        }
        confirmLabel={staffReview?.currentSupervisor ? "Change supervisor" : "Assign supervisor"}
        pendingLabel={staffReview?.currentSupervisor ? "Changing…" : "Assigning…"}
        pending={staffPending}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setStaffReview(null);
        }}
        onConfirm={() => void confirmStaff()}
      >
        {staffReview ? (
          <>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-muted">Staff member</dt>
                <dd className="font-semibold text-ink">{staffReview.staff.full_name}</dd>
              </div>
              <div>
                <dt className="text-muted">Current supervisor</dt>
                <dd className="font-semibold text-ink">
                  {staffReview.currentSupervisor?.full_name ?? "Not assigned"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">New supervisor</dt>
                <dd className="font-semibold text-ink">{staffReview.newSupervisor.full_name}</dd>
              </div>
            </dl>
            {staffReview.currentSupervisor ? (
              <p>The current supervision relationship will be replaced.</p>
            ) : null}
            <p>{supervisionScopeConsequence(staffReview.newSupervisor)}</p>
          </>
        ) : null}
      </ConsequentialActionDialog>

      <ConsequentialActionDialog
        open={staffRemoval !== null}
        title={
          staffRemoval
            ? `Remove ${staffRemoval.staff.full_name}'s supervisor?`
            : "Remove Staff supervisor?"
        }
        confirmLabel="Remove supervisor"
        pendingLabel="Removing…"
        pending={staffPending}
        error={action.error}
        variant="danger"
        onOpenChange={(open) => {
          if (!open) {
            setStaffRemoval(null);
            action.setError(null);
          }
        }}
        onConfirm={() => void confirmRemoveStaff()}
      >
        <p>
          {staffRemoval
            ? `${staffRemoval.staff.full_name} will no longer share ${staffRemoval.supervisor.full_name}'s handled College responsibilities.`
            : "The Staff supervision relationship will be removed."}
        </p>
      </ConsequentialActionDialog>

      {action.stepUpDialog}
    </section>
  );
}
