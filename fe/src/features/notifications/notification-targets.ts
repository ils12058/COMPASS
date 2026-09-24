import type { NotificationResponse } from "@/lib/api/generated/model";

// Backend security producers emit ACCOUNT_SECURITY with the recipient user ID.
// Add a mapping only when both the producer semantics and destination exist.
export function notificationDestination(notification: NotificationResponse, currentUserId: string): string | null {
  if (notification.target_type === "ACCOUNT_SECURITY" && notification.target_id === currentUserId) {
    return "/portal/account/security";
  }
  if (notification.target_type === "INVENTORY") {
    // Inventory reopen notifications are recipient-scoped; the current route
    // reloads the canonical self-service status and record before rendering.
    return "/portal/inventory/current";
  }
  if (
    notification.target_type === "ROUTINE_INTERVIEW" &&
    notification.target_id
  ) {
    return "/portal/routine-interviews/" + notification.target_id;
  }
  if (
    notification.target_type === "COUNSELING_SHARED_SUMMARY" &&
    notification.target_id
  ) {
    return "/portal/counseling/summaries/" + notification.target_id;
  }
  if (notification.target_type === "E_COUNSELING" && notification.target_id) {
    return "/portal/e-counseling/" + notification.target_id;
  }
  if (notification.target_type === "CALL_SLIP" && notification.target_id) {
    return "/portal/call-slips/" + notification.target_id;
  }
  if (notification.target_type === "GOOD_MORAL" && notification.target_id) {
    return "/portal/good-moral/" + notification.target_id;
  }
  if (notification.target_type === "FEEDBACK") {
    return "/portal/feedback";
  }
  return null;
}
