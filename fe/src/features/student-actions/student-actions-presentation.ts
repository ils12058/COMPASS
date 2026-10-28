import { StudentActionKind, type StudentActionItem } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

/** Inclusion and ordering come from the server; this mapping supplies plain copy and routes. */
export function presentStudentAction(item: StudentActionItem) {
  const id = item.source_id;
  const timing = item.due_at
    ? `${item.kind === StudentActionKind.ECOUNSELING_JOIN ? "Join until" : "Report time"}: ${formatInstitutionalDateTime(item.due_at)}`
    : item.waiting_since ? `Waiting since ${formatInstitutionalDateTime(item.waiting_since)}` : null;
  let row: { title: string; detail: string; href: string; actionLabel: string };
  switch (item.kind) {
    case StudentActionKind.INVENTORY_START:
      row = { title: "Individual Inventory", detail: "You haven't started this year's form.", href: "/portal/inventory", actionLabel: "Start Inventory" }; break;
    case StudentActionKind.INVENTORY_CONTINUE:
      row = { title: "Individual Inventory", detail: "Your form for this academic year is still a draft.", href: "/portal/inventory/current", actionLabel: "Continue Inventory" }; break;
    case StudentActionKind.ROUTINE_INTAKE:
      row = { title: "Routine Interview", detail: "Your form is ready to complete.", href: `/portal/routine-interviews/${id}`, actionLabel: "Complete Routine Interview" }; break;
    case StudentActionKind.EXIT_INTERVIEW_START:
      row = { title: "Exit Interview", detail: "Your Exit Interview is ready to start.", href: "/portal/exit-interviews", actionLabel: "Start Exit Interview" }; break;
    case StudentActionKind.EXIT_INTERVIEW_CONTINUE:
      row = { title: "Exit Interview", detail: "Your Exit Interview is still in draft.", href: `/portal/exit-interviews/${id}`, actionLabel: "Continue Exit Interview" }; break;
    case StudentActionKind.EXIT_INTERVIEW_CORRECTION:
      row = { title: "Exit Interview correction", detail: "Your Exit Interview was reopened for correction.", href: `/portal/exit-interviews/${id}`, actionLabel: "Correct Exit Interview" }; break;
    case StudentActionKind.GRADUATE_TRACER_CONTINUE:
      row = { title: "Graduate Tracer Survey", detail: "Your response is still in draft.", href: "/portal/graduate-tracer", actionLabel: "Continue survey" }; break;
    case StudentActionKind.CALL_SLIP_ACTIVE:
      row = { title: "Call Slip", detail: "Review where and when you are expected to report.", href: `/portal/call-slips/${id}`, actionLabel: "Review Call Slip" }; break;
    case StudentActionKind.ECOUNSELING_CONSENT:
      row = { title: "E-Counseling consent", detail: item.pending_count && item.pending_count > 1 ? `${item.pending_count} consent decisions require your review.` : "A consent decision requires your review.", href: `/portal/e-counseling/${id}`, actionLabel: "Review consent" }; break;
    case StudentActionKind.ECOUNSELING_JOIN:
      row = { title: "E-Counseling", detail: "Your online Counseling session is available to join now.", href: `/portal/e-counseling/${id}`, actionLabel: "Join E-Counseling" }; break;
    case StudentActionKind.GUIDANCE_MESSAGE_UNREAD:
      row = { title: "Guidance Messages", detail: "You have unread messages.", href: `/portal/messages/${id}`, actionLabel: "Read new Guidance message" }; break;
  }
  return { ...row, timing, priorityLabel: item.priority === "TIME_SENSITIVE" ? "Time sensitive" : null };
}
