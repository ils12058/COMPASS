import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import type { GuidanceOperationsResponse, UserSummary } from "@/lib/api/generated/model";

export type OperationsMetric = {
  label: string;
  count: number;
  oldest?: { label: "Oldest waiting" | "Oldest due"; instant: string };
  href?: string;
};

/** Only returned non-null facts are shown. A designation never manufactures a metric. */
export function presentOperations(data: GuidanceOperationsResponse, user: UserSummary) {
  const backlog: OperationsMetric[] = [];
  const schedule: OperationsMetric[] = [];
  const goodMoral = getGoodMoralAccess(user);
  const appointments = getAppointmentAccess(user);
  const callSlips = getCallSlipAccess(user);
  const waiting = (label: string, metric: typeof data.backlog.guidance_messages, href?: string) => {
    if (metric !== null) backlog.push({ label, count: metric.count, href,
      ...(metric.oldest_waiting_since ? { oldest: { label: "Oldest waiting", instant: metric.oldest_waiting_since } } : {}),
    });
  };
  waiting("Messages awaiting reply", data.backlog.guidance_messages);
  // Submitted+DRAFT list filters still include closed parents; no exact action-list link exists.
  waiting("Routine evaluations pending", data.backlog.routine_evaluations);
  waiting("Good Moral needs preparation", data.backlog.good_moral_preparation,
    goodMoral.canViewOperational ? "/portal/good-moral?status=REQUESTED" : undefined);
  waiting("Good Moral ready for issuance", data.backlog.good_moral_issuance,
    goodMoral.canViewOperational ? "/portal/good-moral?status=READY_FOR_ISSUANCE" : undefined);
  const due = data.backlog.call_slips_due;
  if (due !== null) backlog.push({ label: "Call Slips due", count: due.count,
    ...(due.oldest_due_at ? { oldest: { label: "Oldest due", instant: due.oldest_due_at } } : {}),
  });
  const context = (label: string, count: number | null, href?: string) => {
    if (count !== null) schedule.push({ label, count, href });
  };
  context("Your upcoming appointments", data.schedule.upcoming_self_appointments_count,
    appointments.canViewSelf ? "/portal/appointments/my?status=UPCOMING" : undefined);
  context("Upcoming managed appointments", data.schedule.upcoming_managed_appointments_count,
    appointments.canManage ? "/portal/appointments/manage?status=UPCOMING" : undefined);
  context("Active Call Slips", data.schedule.active_call_slips_count,
    callSlips.hasWorkspace ? "/portal/call-slips?state=ACTIVE" : undefined);
  return { backlog, schedule };
}
