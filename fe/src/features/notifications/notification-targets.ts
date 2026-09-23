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
  return null;
}
