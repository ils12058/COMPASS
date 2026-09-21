import type { NotificationResponse } from "@/lib/api/generated/model";

type NotificationDestination = {
  href: string;
  label: string;
};

const ACCOUNT_SECURITY_EVENTS = new Set([
  "security.password.changed",
  "security.mfa.disabled",
  "security.recovery_codes.regenerated",
  "security.mfa.admin_reset",
  "security.account_access.changed",
]);

export function notificationDestination(
  notification: NotificationResponse,
): NotificationDestination | null {
  if (ACCOUNT_SECURITY_EVENTS.has(notification.event_code)) {
    return {
      href: "/portal/account/security",
      label: "Review account security",
    };
  }

  return null;
}
