import type { NotificationResponse } from "@/lib/api/generated/model";

const notificationDateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function formatNotificationDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : notificationDateFormatter.format(date);
}

export function unreadLabel(count: number): string {
  if (count <= 0) {
    return "Notifications";
  }
  if (count >= 100) {
    return "99 or more unread notifications";
  }
  return `${count} unread notification${count === 1 ? "" : "s"}`;
}

export function notificationPolicyLabel(
  policy: NotificationResponse["policy"],
): "Security" | "Important" | "Update" | null {
  switch (policy) {
    case "MANDATORY_SECURITY":
      return "Security";
    case "MANDATORY_OPERATIONAL":
      return "Important";
    case "OPTIONAL_INFORMATIONAL":
      return "Update";
    default:
      return null;
  }
}
