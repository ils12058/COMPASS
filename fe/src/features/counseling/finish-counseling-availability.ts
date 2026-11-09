import { AppointmentStatus } from "@/lib/api/generated/model";
import type {
  AppointmentDetailResponse,
  CounselingFinishResponse,
} from "@/lib/api/generated/model";
import { isCounselingService } from "@/features/counseling/canonical-counseling-service";

export type FinishCounselingState = "OFFERED" | "RECORDED" | "UNAVAILABLE";

export function finishCounselingState(
  appointment: Pick<
    AppointmentDetailResponse,
    "status" | "service" | "actions" | "counseling_encounter_recorded" | "counseling_encounter_linked"
  >,
  { canFinish }: { canFinish: boolean },
): FinishCounselingState {
  if (
    !isCounselingService(appointment.service) ||
    appointment.counseling_encounter_recorded === null ||
    !canFinish
  ) {
    return "UNAVAILABLE";
  }
  if (appointment.counseling_encounter_recorded) return "RECORDED";
  // A linked Encounter that does not match is already this Appointment's only link, so Finish can
  // only be refused. Reviewing it is not something this control can do (D-CENC-21).
  if (appointment.counseling_encounter_linked === true) return "UNAVAILABLE";
  if (appointment.status === AppointmentStatus.COMPLETED) return "OFFERED";
  if (
    appointment.status === AppointmentStatus.SCHEDULED &&
    appointment.actions.complete.allowed
  ) {
    return "OFFERED";
  }
  return "UNAVAILABLE";
}

export function finishCounselingNotice(
  result: Pick<CounselingFinishResponse, "already_finished" | "encounter_result">,
  { wasCompleted }: { wasCompleted: boolean },
): string {
  if (result.already_finished) {
    return "Counseling was already finished. The latest details are now shown.";
  }
  if (result.encounter_result === "EXISTING") {
    return "Counseling finished. The Encounter already recorded for this Appointment was kept.";
  }
  if (wasCompleted) {
    return "Counseling Encounter recorded for this completed Appointment.";
  }
  return "Counseling finished and the Encounter recorded.";
}

export const unconfirmedFinishMessage =
  "Couldn't confirm whether counseling was finished.";
