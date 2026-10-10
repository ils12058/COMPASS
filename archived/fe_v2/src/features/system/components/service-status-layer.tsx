"use client";

import { usePathname } from "next/navigation";
import {
  type ReactNode,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";
import { useQueryClient } from "@tanstack/react-query";

import { MaintenanceScreen } from "@/features/system/components/maintenance-screen";
import { ScheduledMaintenanceDialog } from "@/features/system/components/scheduled-maintenance-dialog";
import { ServiceStatusBanner } from "@/features/system/components/service-status-banner";
import { usePlatformPublicStatus } from "@/lib/api/generated/platform-operations/platform-operations";
import { getPlatformPublicStatusQueryKey } from "@/lib/api/generated/platform-operations/platform-operations";
import { isMaintenanceExemptPath } from "@/lib/system/maintenance-route-policy";
import {
  normalizeServiceStatus,
  UNKNOWN_SERVICE_STATUS,
  type ServiceStatusView,
} from "@/lib/system/service-status";
import { COMPASS_MAINTENANCE_SIGNAL_EVENT } from "@/lib/system/status-events";

const OPERATIONAL_POLL_MS = 5 * 60_000;
const ATTENTION_POLL_MS = 60_000;

function subscribeOnline(onChange: () => void): () => void {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
}

function getOnlineSnapshot(): boolean {
  return navigator.onLine;
}

function getServerOnlineSnapshot(): boolean {
  return true;
}

function nextPollDelay(status: ServiceStatusView): number {
  return status.kind === "operational"
    ? OPERATIONAL_POLL_MS
    : ATTENTION_POLL_MS;
}

export function ServiceStatusLayer({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const queryClient = useQueryClient();
  const online = useSyncExternalStore(
    subscribeOnline,
    getOnlineSnapshot,
    getServerOnlineSnapshot,
  );
  const query = usePlatformPublicStatus({
    query: {
      enabled: online,
      retry: false,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchIntervalInBackground: false,
      refetchInterval: (currentQuery) => {
        if (!online) {
          return false;
        }

        const platformStatus = currentQuery.state.data?.data;
        return platformStatus
          ? nextPollDelay(normalizeServiceStatus(platformStatus))
          : ATTENTION_POLL_MS;
      },
      staleTime: 30_000,
    },
  });

  const backendStatus = useMemo<ServiceStatusView>(() => {
    if (query.data?.data) {
      return normalizeServiceStatus(query.data.data);
    }
    if (query.isError) {
      return { kind: "unavailable" };
    }
    return UNKNOWN_SERVICE_STATUS;
  }, [query.data, query.isError]);

  const status = online ? backendStatus : { kind: "offline" as const };

  useEffect(() => {
    document.documentElement.dataset.compassServiceStatus = status.kind;
    return () => {
      delete document.documentElement.dataset.compassServiceStatus;
    };
  }, [status.kind]);

  useEffect(() => {
    const refresh = () => {
      void queryClient.invalidateQueries({
        queryKey: getPlatformPublicStatusQueryKey(),
      });
    };

    window.addEventListener(COMPASS_MAINTENANCE_SIGNAL_EVENT, refresh);
    return () => {
      window.removeEventListener(COMPASS_MAINTENANCE_SIGNAL_EVENT, refresh);
    };
  }, [queryClient]);

  if (
    backendStatus.kind === "maintenance_active" &&
    !isMaintenanceExemptPath(pathname)
  ) {
    return (
      <MaintenanceScreen
        status={backendStatus}
        onRetry={() => void query.refetch()}
        checking={query.isFetching}
      />
    );
  }

  const scheduledMaintenance =
    online && backendStatus.kind === "maintenance_scheduled"
      ? backendStatus
      : null;

  let bannerStatus:
    | Extract<
        ServiceStatusView,
        {
          kind:
            | "maintenance_active"
            | "offline"
            | "unavailable";
        }
      >
    | null = null;

  if (!online) {
    bannerStatus = { kind: "offline" };
  } else if (
    backendStatus.kind === "unavailable" ||
    (backendStatus.kind === "maintenance_active" &&
      isMaintenanceExemptPath(pathname))
  ) {
    bannerStatus = backendStatus;
  }

  return (
    <>
      {children}
      {scheduledMaintenance ? (
        <ScheduledMaintenanceDialog status={scheduledMaintenance} />
      ) : null}
      {bannerStatus ? <ServiceStatusBanner status={bannerStatus} /> : null}
    </>
  );
}
