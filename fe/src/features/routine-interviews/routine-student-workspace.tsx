"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import type { RoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import {
  formatRoutineDateTime,
  formatRoutineDateTimeRange,
  routineAcademicYearLabel,
  routineDeliveryModeLabel,
  routineEntryModeLabel,
  routineErrorMessage,
  routineIntakeStatusLabel,
  RoutinePageHeading,
  RoutineStatus,
} from "@/features/routine-interviews/routine-interviews-shared";
import {
  getRoutineInterviewsEnsureMyForAppointmentMutationKey,
  getRoutineInterviewsListMineQueryKey,
  getRoutineInterviewsListMyAppointmentCandidatesQueryKey,
  routineInterviewsEnsureMyForAppointment,
  useRoutineInterviewsListMine,
  useRoutineInterviewsListMyAppointmentCandidates,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

const tableCell = dataTable.headerCell;
const cell = `${dataTable.cell} text-sm`;

export function StudentRoutineWorkspace({
  access,
}: {
  access: RoutineInterviewAccess;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const routines = useRoutineInterviewsListMine({
    query: { enabled: access.canViewSelf, retry: false },
  });
  const candidates = useRoutineInterviewsListMyAppointmentCandidates({
    query: { enabled: access.canManageSelf, retry: false },
  });
  // Every scheduled Counseling Appointment includes a Routine Interview. Opening it runs the
  // backend's idempotent ensure, which returns the Appointment's one Routine Interview.
  const ensure = useMutation({
    mutationKey: getRoutineInterviewsEnsureMyForAppointmentMutationKey(),
    mutationFn: (appointmentId: string) =>
      routineInterviewsEnsureMyForAppointment({ appointment_id: appointmentId }),
  });

  async function openRoutine(appointmentId: string) {
    try {
      const response = await ensure.mutateAsync(appointmentId);
      const routine = response.data;
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListMineQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListMyAppointmentCandidatesQueryKey() }),
      ]);
      router.push(`/portal/routine-interviews/${routine.id}`);
    } catch {
      // The canonical candidate endpoint is refreshed below for lifecycle conflicts.
      void candidates.refetch();
    }
  }

  const routineItems = routines.data?.data.items ?? [];
  const appointmentItems = candidates.data?.data.items ?? [];
  const openError = ensure.error;

  return (
    <div>
      <RoutinePageHeading
        title="Routine Interviews"
      />

      {access.canManageSelf ? (
        <Panel aria-labelledby="routine-appointment-candidates" className="mb-5">
          <PanelHeader
            title="Routine Interviews to complete"
            titleId="routine-appointment-candidates"
            description="Complete the Routine Interview for each scheduled Counseling Appointment before your session."
            actions={candidates.isSuccess ? (
              <Button variant="secondary" onClick={() => void candidates.refetch()} disabled={candidates.isFetching}>
                Refresh
              </Button>
            ) : undefined}
          />

          {candidates.isPending ? (
            <RowsSkeleton label="Loading eligible Appointments…" rows={2} />
          ) : candidates.isError ? (
            <PanelMessage
              role="alert"
              tone="danger"
              action={<Button variant="secondary" onClick={() => void candidates.refetch()}>Retry</Button>}
            >
              Your Counseling Appointments could not be checked.{" "}
              {routineErrorMessage(candidates.error, "Try again in a moment.")}
            </PanelMessage>
          ) : appointmentItems.length === 0 ? (
            <PanelMessage>
              No Counseling Appointment is waiting for a Routine Interview.
            </PanelMessage>
          ) : (
            <ul className="divide-y divide-border">
              {appointmentItems.map((appointment) => (
                <li key={appointment.id} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                  <div className="min-w-0">
                    <p className="font-semibold text-ink">{appointment.reference_code}</p>
                    <p className="mt-1 text-sm text-muted">
                      {appointment.counselor.display_name} · {formatRoutineDateTimeRange(appointment.starts_at, appointment.ends_at)} · {routineDeliveryModeLabel(appointment.delivery_mode)}
                    </p>
                  </div>
                  <Button
                    onClick={() => void openRoutine(appointment.id)}
                    disabled={ensure.isPending}
                    aria-busy={ensure.isPending && ensure.variables === appointment.id}
                  >
                    {ensure.isPending && ensure.variables === appointment.id ? "Opening…" : "Complete Routine Interview"}
                    <span className="sr-only"> for {appointment.reference_code}</span>
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {openError ? (
            <div role="alert" className="border-t border-border px-4 py-3 text-sm text-danger sm:px-5">
              <p>{routineErrorMessage(openError, "The Routine Interview could not be opened. Your Counseling Appointments have been checked again; try again.")}</p>
            </div>
          ) : null}
        </Panel>
      ) : null}

      {access.canViewSelf ? (
        <Panel aria-labelledby="my-routine-interviews">
          <PanelHeader title="Your Routine Interviews" titleId="my-routine-interviews" />
          {routines.isPending ? (
            <RowsSkeleton label="Loading your Routine Interviews…" rows={2} />
          ) : routines.isError ? (
            <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void routines.refetch()}>Retry</Button>}>
              Routine Interviews could not be loaded. {routineErrorMessage(routines.error, "Try again in a moment.")}
            </PanelMessage>
          ) : routineItems.length === 0 ? (
            <PanelMessage>
              You do not have any Routine Interviews yet. Routine Interviews you open for your Counseling Appointments appear here, as do interviews created by your Counselor.
            </PanelMessage>
          ) : (
            <div className={dataTable.scroll}>
              <table className={`${dataTable.table} min-w-[760px]`}>
                <caption className="sr-only">Your Routine Interviews</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={`${tableCell} ${dataTable.stickyHeaderCell}`}>Routine Interview</th>
                    <th scope="col" className={tableCell}>Academic Year</th>
                    <th scope="col" className={tableCell}>Counselor</th>
                    <th scope="col" className={tableCell}>Nature / delivery</th>
                    <th scope="col" className={tableCell}>Student Intake</th>
                    <th scope="col" className={tableCell}>Appointment</th>
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {routineItems.map((routine) => (
                    <tr key={routine.id} className={dataTable.row}>
                      <th scope="row" className={`${cell} ${dataTable.stickyCell} min-w-40 font-normal`}>
                        <Link href={`/portal/routine-interviews/${routine.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                          {formatRoutineDateTime(routine.created_at)}
                        </Link>
                        {routine.intake_submitted_at ? (
                          <span className="mt-1 block text-xs text-muted">Submitted {formatRoutineDateTime(routine.intake_submitted_at)}</span>
                        ) : null}
                      </th>
                      <td className={cell}>{routineAcademicYearLabel(routine.academic_year)}</td>
                      <td className={cell}>{routine.counselor.display_name}</td>
                      <td className={cell}>{routineEntryModeLabel(routine.entry_mode)}<span className="block text-muted">{routineDeliveryModeLabel(routine.delivery_mode)}</span></td>
                      <td className={cell}>
                        <RoutineStatus complete={routine.intake_status === "SUBMITTED"}>
                          {routineIntakeStatusLabel(routine.intake_status)}
                        </RoutineStatus>
                      </td>
                      <td className={cell}>
                        {routine.appointment ? (
                          <><span className="font-medium text-ink">{routine.appointment.reference_code}</span><span className="block text-muted">{formatRoutineDateTimeRange(routine.appointment.starts_at, routine.appointment.ends_at)}</span></>
                        ) : <span className="text-muted">—</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      ) : null}
    </div>
  );
}
