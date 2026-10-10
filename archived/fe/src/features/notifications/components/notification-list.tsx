import { NotificationRow } from "@/features/notifications/components/notification-row";
import type { NotificationResponse } from "@/lib/api/generated/model";

export function NotificationList({
  items,
  onReadStateChanged,
}: {
  items: NotificationResponse[];
  onReadStateChanged: () => Promise<void>;
}) {
  return (
    <section aria-label="Notification history" className="overflow-hidden rounded-xl border bg-card">
      {items.map((item) => (
        <NotificationRow
          key={item.id}
          item={item}
          onReadStateChanged={onReadStateChanged}
        />
      ))}
    </section>
  );
}
