import { ShieldCheck } from "lucide-react";

import { notificationPolicyLabel } from "@/features/notifications/presentation";
import type { NotificationResponse } from "@/lib/api/generated/model";
import { cn } from "@/lib/utils/cn";

export function NotificationPolicyBadge({
  policy,
}: {
  policy: NotificationResponse["policy"];
}) {
  const label = notificationPolicyLabel(policy);

  if (!label) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold",
        label === "Security"
          ? "border-primary/25 bg-primary/5 text-primary"
          : "border-border bg-muted text-muted-foreground",
      )}
    >
      {label === "Security" ? <ShieldCheck aria-hidden="true" className="size-3" /> : null}
      {label}
    </span>
  );
}
