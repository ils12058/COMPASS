"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { RoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import {
  formatRoutineDateTime,
  formatRoutineDateTimeRange,
  routineDeliveryModeLabel,
  routineEntryModeLabel,
  routineErrorCode,
  routineErrorMessage,
  routineIntakeStatusLabel,
  RoutinePageHeading,
  RoutineQueryError,
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

const tableCell = "px-4 py-3 align-top text-sm";

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
  const ensure = useMutation({
    mutationKey: getRoutineInterviewsEnsureMyForAppointmentMutationKey(),
    mutationFn: (appointmentId: string) =>
      routineInterviewsEnsureMyForAppointment({ appointment_id: appointmentId }),
  });

  async function startRoutine(appointmentId: string) {
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
  const startError = ensure.error;
  const inventoryRequired = routineErrorCode(candidates.error) === "routine_interview_inventory_required";
  const startInventoryRequired = routineErrorCode(startError) === "routine_interview_inventory_required";

  return (
    <div>
      <RoutinePageHeading
        title="Routine Interviews"
        description="Complete interview questions connected to your Guidance and Counseling interactions."
      />

      {access.canManageSelf ? (
        <section aria-labelledby="routine-appointment-candidates" className="mb-9">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 id="routine-appointment-candidates" className="font-heading text-xl font-semibold text-ink">
                Counseling Appointments
              </h2>
              <p className="mt-1 text-sm text-muted">
                Start a Routine Interview for an eligible scheduled Appointment.
              </p>
            </div>
            {candidates.isSuccess ? (
              <Button variant="secondary" onClick={() => void candidates.refetch()} disabled={candidates.isFetching}>
                Refresh
              </Button>
            ) : null}
          </div>

          {candidates.isPending ? (
            <div aria-busy="true" className="space-y-3 border-y border-border py-4"><span className="sr-only">Loading eligible Appointments…</span>
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : candidates.isError ? (
            <RoutineQueryError
              title="Eligible Appointments could not be loaded."
              message={inventoryRequired
                ? "Submit your Individual Inventory for the current Academic Year before starting an Appointment-backed Routine Interview."
                : routineErrorMessage(candidates.error, "Try again in a moment.")}
              onRetry={() => void candidates.refetch()}
            >
              {inventoryRequired ? (
                <p className="mt-3">
                  <Link className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href="/portal/inventory">
                    Go to Individual Inventory
                  </Link>
                </p>
              ) : null}
            </RoutineQueryError>
          ) : appointmentItems.length === 0 ? (
            <p className="border-y border-border py-5 text-sm text-muted">
              No scheduled Counseling Appointments currently need a Routine Interview.
            </p>
          ) : (
            <ul className="divide-y divide-border border-y border-border">
              {appointmentItems.map((appointment) => (
                <li key={appointment.id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-semibold text-ink">{appointment.reference_code}</p>
                    <p className="mt-1 text-sm text-muted">
                      {appointment.counselor.display_name} · {formatRoutineDateTimeRange(appointment.starts_at, appointment.ends_at)} · {routineDeliveryModeLabel(appointment.delivery_mode)}
                    </p>
                  </div>
                  <Button
                    onClick={() => void startRoutine(appointment.id)}
                    disabled={ensure.isPending}
                    aria-busy={ensure.isPending}
                  >
                    {ensure.isPending ? "Starting…" : "Start Routine Interview"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {startError ? (
            <div role="alert" className="mt-3 text-sm text-danger">
              <p>{routineErrorMessage(startError, "The Routine Interview could not be started. The eligible Appointment list has been refreshed; review it and try again.")}</p>
              {startInventoryRequired ? (
                <Link className="mt-2 inline-block font-semibold underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" href="/portal/inventory">Go to Individual Inventory</Link>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      {access.canViewSelf ? (
        <section aria-labelledby="my-routine-interviews">
          <h2 id="my-routine-interviews" className="mb-4 font-heading text-xl font-semibold text-ink">
            Your Routine Interviews
          </h2>
          {routines.isPending ? (
            <div aria-busy="true" className="space-y-3 border-y border-border py-4"><span className="sr-only">Loading your Routine Interviews…</span>
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : routines.isError ? (
            <RoutineQueryError
              message={routineErrorMessage(routines.error, "Try again in a moment.")}
              onRetry={() => void routines.refetch()}
            />
          ) : routineItems.length === 0 ? (
            <p className="border-y border-border py-5 text-sm text-muted">
              You do not have any Routine Interviews yet. Eligible Appointment-backed interviews will appear here, as will interviews created by your Counselor.
            </p>
          ) : (
            <div className="overflow-x-auto border-y border-border">
              <table className="w-full min-w-[760px] border-separate border-spacing-0 text-left">
                <caption className="sr-only">Your Routine Interviews</caption>
                <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-wide text-muted">
                  <tr>
                    <th scope="col" className={`${tableCell} sticky left-0 z-20 bg-surface-muted`}>Routine Interview</th>
                    <th scope="col" className={tableCell}>Academic Year</th>
                    <th scope="col" className={tableCell}>Counselor</th>
                    <th scope="col" className={tableCell}>Nature / delivery</th>
                    <th scope="col" className={tableCell}>Student Intake</th>
                    <th scope="col" className={tableCell}>Appointment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {routineItems.map((routine) => (
                    <tr key={routine.id} className="group hover:bg-surface-muted/50">
                      <th scope="row" className={`${tableCell} sticky left-0 z-10 min-w-40 bg-surface-raised font-normal group-hover:bg-surface-muted`}>
                        <Link href={`/portal/routine-interviews/${routine.id}`} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                          {formatRoutineDateTime(routine.created_at)}
                        </Link>
                        {routine.intake_submitted_at ? (
                          <span className="mt-1 block text-xs text-muted">Submitted {formatRoutineDateTime(routine.intake_submitted_at)}</span>
                        ) : null}
                      </th>
                      <td className={tableCell}>{routine.inventory_context.academic_year.label}</td>
                      <td className={tableCell}>{routine.counselor.display_name}</td>
                      <td className={tableCell}>{routineEntryModeLabel(routine.entry_mode)}<span className="block text-muted">{routineDeliveryModeLabel(routine.delivery_mode)}</span></td>
                      <td className={tableCell}>
                        <RoutineStatus complete={routine.intake_status === "SUBMITTED"}>
                          {routineIntakeStatusLabel(routine.intake_status)}
                        </RoutineStatus>
                      </td>
                      <td className={tableCell}>
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
        </section>
      ) : null}
    </div>
  );
}
