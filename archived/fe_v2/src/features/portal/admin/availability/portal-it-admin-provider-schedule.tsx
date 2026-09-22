"use client";

import { CalendarClock } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { WeeklyWindowRequest } from "@/lib/api/generated/model";
import {
  getAvailabilityGetProviderWeeklyQueryKey,
  useAvailabilityGetProviderWeekly,
  useAvailabilityReplaceProviderWeekly,
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

export function PortalItAdminProviderSchedule({
  canManage,
  providerId,
  providerName,
}: {
  canManage: boolean;
  providerId: string;
  providerName: string;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const weeklyQuery = useAvailabilityGetProviderWeekly(providerId, {
    query: {
      enabled: canManage && Boolean(providerId),
      retry: false,
      staleTime: 30_000,
    },
  });
  const replaceWeekly = useAvailabilityReplaceProviderWeekly();

  async function submitSchedule(windows: WeeklyWindowRequest[]) {
    setError(null);
    setMessage(null);

    try {
      await replaceWeekly.mutateAsync({ providerId, data: { windows } });
      setMessage(`${providerName}’s schedule was saved.`);
      await queryClient.invalidateQueries({
        queryKey: getAvailabilityGetProviderWeeklyQueryKey(providerId),
      });
    } catch (caught) {
      setError(availabilityAdminError(caught, "We couldn’t save this provider schedule."));
    }
  }

  return (
    <AvailabilitySection
      icon={CalendarClock}
      title="Provider schedule"
      description={`Set the recurring hours when ${providerName || "this provider"} can receive service assignments.`}
    >
      {!canManage ? (
        <AvailabilityManagementRequired />
      ) : !providerId ? (
        <p className="text-sm leading-6 text-muted-foreground">
          Choose a provider above to review their schedule.
        </p>
      ) : weeklyQuery.isPending ? (
        <AvailabilityListSkeleton label="Loading provider schedule" />
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
