import type { QueryClient } from "@tanstack/react-query";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { CounselingContextAnchorType } from "@/lib/api/generated/model";
import {
  getAppointmentsGetHistoryQueryKey,
  getAppointmentsGetQueryKey,
  getAppointmentsListBookableSlotsQueryKey,
  getAppointmentsListManagedQueryKey,
  getAppointmentsListMyQueryKey,
  getAppointmentsListRemindersQueryKey,
  getAppointmentsListRescheduleSlotsQueryKey,
} from "@/lib/api/generated/appointments/appointments";
import {
  getCounselingContextGetOverviewQueryKey,
  getCounselingListAppointmentCandidatesQueryKey,
  getCounselingListMyEncountersQueryKey,
} from "@/lib/api/generated/counseling/counseling";
import {
  getECounselingGetAssignedWorkspaceQueryKey,
  getECounselingGetMyWorkspaceQueryKey,
} from "@/lib/api/generated/e-counseling/e-counseling";
import {
  getRoutineInterviewsGetAssignedQueryKey,
  getRoutineInterviewsGetMineQueryKey,
  getRoutineInterviewsListAssignedQueryKey,
  getRoutineInterviewsListEncounterCandidatesQueryKey,
  getRoutineInterviewsListMineQueryKey,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

// Finishing changes the Appointment, its Encounter, its Counseling Context and possibly its linked
// Routine Interview, so every surface that projects one of those facts is reconciled from the
// server rather than patched locally.
export async function invalidateAfterCounselingFinish(
  queryClient: QueryClient,
  {
    appointmentId,
    routineInterviewId,
  }: { appointmentId: string; routineInterviewId?: string | null },
): Promise<void> {
  await Promise.all([
    invalidateGuidanceWork(queryClient),
    queryClient.invalidateQueries({ queryKey: getAppointmentsGetQueryKey(appointmentId) }),
    queryClient.invalidateQueries({ queryKey: getAppointmentsGetHistoryQueryKey(appointmentId) }),
    queryClient.invalidateQueries({ queryKey: getAppointmentsListRemindersQueryKey(appointmentId) }),
    queryClient.invalidateQueries({ queryKey: getAppointmentsListMyQueryKey() }),
    queryClient.invalidateQueries({ queryKey: getAppointmentsListManagedQueryKey() }),
    queryClient.invalidateQueries({ queryKey: getAppointmentsListBookableSlotsQueryKey() }),
    queryClient.invalidateQueries({ queryKey: getAppointmentsListRescheduleSlotsQueryKey(appointmentId) }),
    queryClient.invalidateQueries({
      queryKey: getCounselingContextGetOverviewQueryKey(
        CounselingContextAnchorType.APPOINTMENT,
        appointmentId,
      ),
    }),
    queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
    queryClient.invalidateQueries({ queryKey: getCounselingListAppointmentCandidatesQueryKey() }),
    queryClient.invalidateQueries({ queryKey: getECounselingGetMyWorkspaceQueryKey(appointmentId) }),
    queryClient.invalidateQueries({ queryKey: getECounselingGetAssignedWorkspaceQueryKey(appointmentId) }),
    ...(routineInterviewId
      ? [
          queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetMineQueryKey(routineInterviewId) }),
          queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineInterviewId) }),
          queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListMineQueryKey() }),
          queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() }),
          queryClient.invalidateQueries({
            queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(routineInterviewId),
          }),
        ]
      : []),
  ]);
}
