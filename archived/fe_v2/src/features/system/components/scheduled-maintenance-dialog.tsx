"use client";

import { CalendarClock } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ServiceStatusView } from "@/lib/system/service-status";

type ScheduledMaintenanceStatus = Extract<
  ServiceStatusView,
  { kind: "maintenance_scheduled" }
>;

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ScheduledMaintenanceDialog({
  status,
}: {
  status: ScheduledMaintenanceStatus;
}) {
  const noticeKey = `${status.startsAt}:${status.endsAt}:${status.message}`;
  const [dismissedNoticeKey, setDismissedNoticeKey] = useState<string | null>(
    null,
  );
  const open = dismissedNoticeKey !== noticeKey;

  const handleOpenChange = (nextOpen: boolean) => {
    setDismissedNoticeKey(nextOpen ? null : noticeKey);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--compass-brand-gold)]">
            <CalendarClock aria-hidden="true" className="size-5" />
            Scheduled maintenance
          </div>
          <DialogTitle>COMPASS will be briefly unavailable</DialogTitle>
          <DialogDescription>{status.message}</DialogDescription>
        </DialogHeader>

        <div className="rounded-xl bg-muted p-4 text-sm">
          <p className="font-semibold">Maintenance window</p>
          <p className="mt-1 text-muted-foreground">
            {formatDateTime(status.startsAt)} – {formatDateTime(status.endsAt)}
          </p>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Dismiss
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
