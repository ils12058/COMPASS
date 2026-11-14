import { NotificationTargetType, type NotificationResponse } from "@/lib/api/generated/model";

export type NotificationDestination = { href: string; label: string };

// Backend security producers emit ACCOUNT_SECURITY with the recipient user ID.
// Add a mapping only when both the producer semantics and destination exist.
export function notificationDestination(
  notification: NotificationResponse,
  currentUserId: string,
): NotificationDestination | null {
  if (notification.target_type === NotificationTargetType.CASE_TRANSFER && notification.target_id) {
    return { href: `/portal/counseling/transfers/${notification.target_id}`, label: "Review case transfer" };
  }
  if (notification.target_type === NotificationTargetType.APPOINTMENT_REASSIGNMENT && notification.target_id) {
    return { href: `/portal/counseling/reassignments/${notification.target_id}`, label: "Review session reassignment" };
  }
  if (notification.target_type === NotificationTargetType.CASE_COVERAGE && notification.target_id) {
    return { href: `/portal/counseling/coverages/${notification.target_id}`, label: "Review case coverage" };
  }
  if (notification.target_type === NotificationTargetType.SESSION_PROPOSAL && notification.target_id) {
    return { href: `/portal/appointments/proposals/${notification.target_id}`, label: "Choose a session time" };
  }
  if (notification.target_type === NotificationTargetType.COUNSELING_CASE && notification.target_id) {
    return { href: `/portal/counseling/cases/${notification.target_id}`, label: "Open case" };
  }
  if (notification.target_type === NotificationTargetType.ACCOUNT_SECURITY && notification.target_id === currentUserId) {
    return { href: "/portal/account/security", label: "Open Security" };
  }
  if (notification.target_type === NotificationTargetType.GRADUATE_TRACER && notification.target_id === currentUserId) {
    return { href: "/portal/graduate-tracer", label: "Open Graduate Tracer survey" };
  }
  if (notification.target_type === NotificationTargetType.INVENTORY) {
    // Inventory reopen notifications are recipient-scoped; the current route
    // reloads the canonical self-service status and record before rendering.
    return { href: "/portal/inventory/current", label: "Open Individual Inventory" };
  }
  if (
    notification.target_type === NotificationTargetType.ROUTINE_INTERVIEW &&
    notification.target_id
  ) {
    return { href: "/portal/routine-interviews/" + notification.target_id, label: "Open Routine Interview" };
  }
  if (
    notification.target_type === NotificationTargetType.EXIT_INTERVIEW &&
    notification.target_id
  ) {
    return { href: "/portal/exit-interviews/" + notification.target_id, label: "Open Exit Interview" };
  }
  if (
    notification.target_type === NotificationTargetType.STUDENT_SESSION_SUMMARY &&
    notification.target_id
  ) {
    return { href: "/portal/counseling/student-session-summaries/" + notification.target_id, label: "Open Student Session Summary" };
  }
  if (notification.target_type === NotificationTargetType.E_COUNSELING && notification.target_id) {
    return { href: "/portal/e-counseling/" + notification.target_id, label: "Open E-Counseling" };
  }
  if (notification.target_type === NotificationTargetType.GUIDANCE_FOLLOW_UP && notification.target_id) {
    return { href: "/portal/follow-ups/" + notification.target_id, label: "Open Follow-Up" };
  }
  if (notification.target_type === NotificationTargetType.APPOINTMENT && notification.target_id) {
    // Scheduling, rescheduling, and reassignment notify each participant; the detail page
    // reloads the Appointment within the recipient's current access.
    return { href: "/portal/appointments/" + notification.target_id, label: "Open Appointment" };
  }
  if (notification.target_type === NotificationTargetType.FACULTY_REFERRAL && notification.target_id) {
    return { href: "/portal/faculty/referrals/" + notification.target_id, label: "Open Referral" };
  }
  if (notification.target_type === NotificationTargetType.CALL_SLIP && notification.target_id) {
    return { href: "/portal/call-slips/" + notification.target_id, label: "Open Call Slip" };
  }
  if (notification.target_type === NotificationTargetType.GOOD_MORAL && notification.target_id) {
    return { href: "/portal/good-moral/" + notification.target_id, label: "Open Good Moral Certificate request" };
  }
  if (notification.target_type === NotificationTargetType.GROUP_SESSION) {
    if (!notification.target_id) return { href: "/portal/group-sessions/my", label: "My Group Sessions" };
    return {
      href: "/portal/group-sessions/" + notification.target_id,
      label: notification.is_current ? "Open Group Session" : "Review current event",
    };
  }
  if (notification.target_type === NotificationTargetType.FEEDBACK) {
    return {
      href: notification.target_id
        ? `/portal/feedback?opportunity=${encodeURIComponent(notification.target_id)}`
        : "/portal/feedback",
      label: "Open Feedback",
    };
  }
  return null;
}
