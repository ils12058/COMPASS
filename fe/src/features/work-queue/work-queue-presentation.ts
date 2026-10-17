import { WorkKind, type WorkItem } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

/** Product copy and owning-domain navigation only; the backend owns inclusion and order. */
export function presentWork(item: WorkItem, generatedAt?: string) {
  const detail = item.due_at
    ? `Report time: ${formatInstitutionalDateTime(item.due_at)}`
    : item.waiting_since ? `Waiting since ${formatInstitutionalDateTime(item.waiting_since)}` : "Awaiting your review";
  switch (item.kind) {
    case WorkKind.GUIDANCE_FOLLOW_UP:
      return { title: "Review Guidance follow-up", detail: `${generatedAt && item.due_at && new Date(item.due_at) < new Date(generatedAt) ? "Overdue · " : ""}Due ${item.due_at ? formatInstitutionalDateTime(item.due_at) : "date unavailable"}`, href: `/portal/follow-ups/${item.source_id}`, actionLabel: "Open follow-up" };
    case WorkKind.GUIDANCE_MESSAGE_REPLY:
      return { title: "Reply to Guidance Message", detail, href: `/portal/messages/${item.source_id}`, actionLabel: "Open conversation" };
    case WorkKind.ROUTINE_EVALUATION:
      return { title: "Review Routine Interview", detail, href: `/portal/routine-interviews/${item.source_id}`, actionLabel: "Review Routine Interview" };
    case WorkKind.GOOD_MORAL_PREPARATION:
      return { title: "Prepare Good Moral request", detail, href: `/portal/good-moral/${item.source_id}`, actionLabel: "Prepare request" };
    case WorkKind.GOOD_MORAL_ISSUANCE:
      return { title: "Issue Good Moral certificate", detail, href: `/portal/good-moral/${item.source_id}`, actionLabel: "Review certificate" };
    case WorkKind.CALL_SLIP_DUE:
      return { title: "Review Call Slip", detail, href: `/portal/call-slips/${item.source_id}`, actionLabel: "Review Call Slip" };
  }
}
