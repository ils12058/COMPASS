import { NotificationTargetType, type NotificationResponse } from "@/lib/api/generated/model";

export type NotificationDestination = { href: string; label: string };

// Backend security producers emit ACCOUNT_SECURITY with the recipient user ID.
// Add a mapping only when both the producer semantics and destination exist.
export function notificationDestination(
  notification: NotificationResponse,
  currentUserId: string,
): NotificationDestination | null {
  if (notification.target_type === NotificationTargetType.ACCOUNT_SECURITY && notification.target_id === currentUserId) {
    return { href: "/portal/account/security", label: "Open Security" };
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
    notification.target_type === NotificationTargetType.COUNSELING_SHARED_SUMMARY &&
    notification.target_id
  ) {
    return { href: "/portal/counseling/summaries/" + notification.target_id, label: "Open Counseling summary" };
  }
  if (notification.target_type === NotificationTargetType.E_COUNSELING && notification.target_id) {
    return { href: "/portal/e-counseling/" + notification.target_id, label: "Open E-Counseling" };
  }
  if (notification.target_type === NotificationTargetType.APPOINTMENT && notification.target_id) {
    // Scheduling, rescheduling, and reassignment notify each participant; the detail page
    // reloads the Appointment within the recipient's current access.
    return { href: "/portal/appointments/" + notification.target_id, label: "Open Appointment" };
  }
  if (notification.target_type === NotificationTargetType.CALL_SLIP && notification.target_id) {
    return { href: "/portal/call-slips/" + notification.target_id, label: "Open Call Slip" };
  }
  if (notification.target_type === NotificationTargetType.GOOD_MORAL && notification.target_id) {
    return { href: "/portal/good-moral/" + notification.target_id, label: "Open Good Moral request" };
  }
  if (notification.target_type === NotificationTargetType.FEEDBACK) {
    return { href: "/portal/feedback", label: "Open Feedback" };
  }
  return null;
}
