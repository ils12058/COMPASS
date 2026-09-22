"use client";

import { CalendarClock } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { WeeklyWindowRequest } from "@/lib/api/generated/model";
import {
  getAvailabilityGetOfficeWeeklyQueryKey,
  useAvailabilityGetOfficeWeekly,
  useAvailabilityReplaceOfficeWeekly,
} from "@/lib/api/generated/availability/availability";
import { PortalItAdminWeeklyScheduleEditor } from "@/features/portal/admin/availability/portal-it-admin-weekly-schedule-editor";
import {
  AvailabilityActionMessage,
  AvailabilityListSkeleton,
  AvailabilityManagementRequired,
  AvailabilityQueryError,
  AvailabilitySection,
  availabilityAdminError,
} from "@/features/portal/admin/availability/portal-it-admin-availability-shared";

export function PortalItAdminOfficeSchedule({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const weeklyQuery = useAvailabilityGetOfficeWeekly({
    query: {
      enabled: canManage,
      retry: false,
      staleTime: 30_000,
    },
  });
  const replaceWeekly = useAvailabilityReplaceOfficeWeekly();

  async function submitSchedule(windows: WeeklyWindowRequest[]) {
    setError(null);
    setMessage(null);

    try {
      await replaceWeekly.mutateAsync({ data: { windows } });
      setMessage("Office schedule saved.");
      await queryClient.invalidateQueries({
        queryKey: getAvailabilityGetOfficeWeeklyQueryKey(),
      });
    } catch (caught) {
      setError(availabilityAdminError(caught, "We couldn’t save the office schedule."));
    }
  }

  return (
    <AvailabilitySection
      icon={CalendarClock}
      title="Office schedule"
      description="Set the recurring hours when the Guidance and Counseling Office can receive service requests."
    >
      {!canManage ? (
        <AvailabilityManagementRequired />
      ) : weeklyQuery.isPending ? (
        <AvailabilityListSkeleton label="Loading office schedule" />
      ) : weeklyQuery.isError || !weeklyQuery.data?.data ? (
        <AvailabilityQueryError onRetry={() => void weeklyQuery.refetch()} />
      ) : (
        <div className="space-y-5">
          <AvailabilityActionMessage error={error} message={message} />
          <PortalItAdminWeeklyScheduleEditor
            key={weeklyQuery.data.data.windows.map((window) => window.id).join("-")}
            initialWindows={weeklyQuery.data.data.windows}
            isSubmitting={replaceWeekly.isPending}
            onSubmit={submitSchedule}
          />
        </div>
      )}
    </AvailabilitySection>
  );
}
