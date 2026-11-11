import type { UserSummary } from "@/lib/api/generated/model";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { getGuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import { facultyReferralAccess } from "@/features/faculty-referrals/access";
import { hasStudentActions } from "@/features/student-actions/student-actions-access";

// Discovery uses the owning workspace helpers. Action availability and rendered targets stay
// with the destination page; no guide fetches data or repeats record eligibility predicates.
export function taskGuideAccess(user: UserSummary) {
  const appointments = getAppointmentAccess(user);
  const messages = getGuidanceMessagesAccess(user);
  const faculty = facultyReferralAccess(user);
  return {
    "book-appointment": appointments.canViewSelf && appointments.canBook,
    "send-message": messages.hasWorkspace,
    "my-appointments": appointments.canViewSelf,
    "individual-inventory": getInventoryAccess(user).canViewSelf,
    "good-moral": getGoodMoralAccess(user).hasStudentWorkspace,
    "my-actions": hasStudentActions(user),
    "exit-interview": getExitInterviewAccess(user).hasStudentWorkspace,
    "graduate-tracer": getGraduateTracerAccess(user).hasStudentWorkspace,
    "feedback": getFeedbackAccess(user).hasStudentSubmissionAccess,
    "faculty-submit": faculty.submit,
    "faculty-track": faculty.read,
  };
}
