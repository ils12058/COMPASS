"use client";

import { usePathname } from "next/navigation";
import {
  type ReactNode,
  useEffect,
  useMemo,
  useSyncExternalStore,
} from "react";

import { MaintenanceScreen } from "@/features/system/components/maintenance-screen";
import { ServiceStatusBanner } from "@/features/system/components/service-status-banner";
import {
  usePlatformPublicStatus,
} from "@/lib/api/generated/platform-operations/platform-operations";
import { isMaintenanceExemptPath } from "@/lib/system/maintenance-route-policy";
import {
  normalizeServiceStatus,
  type ServiceStatusView,
} from "@/lib/system/service-status";
import { COMPASS_MAINTENANCE_SIGNAL_EVENT } from "@/lib/system/status-events";

const OPERATIONAL_POLL_MS = 5 * 60_000;
const ATTENTION_POLL_MS = 60_000;
const MAX_TIMEOUT_MS = 2_147_000_000;

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

function nextPollDelay(status: ServiceStatusView): number | null {
  if (status.kind === "offline") {
    return null;
  }
  return status.kind === "operational" ? OPERATIONAL_POLL_MS : ATTENTION_POLL_MS;
}

function transitionDelay(status: ServiceStatusView): number | null {
  if (
    status.kind !== "maintenance_scheduled" &&
    status.kind !== "maintenance_active"
  ) {
    return null;
  }

  const candidates: number[] = [];
  if (status.startsAt) {
    candidates.push(Date.parse(status.startsAt) - Date.now());
  }
  if (status.endsAt) {
    candidates.push(Date.parse(status.endsAt) - Date.now());
  }

  const future = candidates.filter((value) => Number.isFinite(value) && value > 0);
  if (!future.length) {
    return null;
  }

  return Math.min(Math.min(...future) + 500, MAX_TIMEOUT_MS);
}

export function ServiceStatusLayer({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname();
  const online = useSyncExternalStore(
    subscribeOnline,
    getOnlineSnapshot,
    getServerOnlineSnapshot,
  );
  const query = usePlatformPublicStatus({
    query: {
      retry: false,
      refetchOnWindowFocus: false,
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
    return { kind: "unknown" };
  }, [query.data, query.isError]);

  const status: ServiceStatusView = online
    ? backendStatus
    : { kind: "offline" };

  useEffect(() => {
    document.documentElement.dataset.compassServiceStatus = status.kind;
    return () => {
      delete document.documentElement.dataset.compassServiceStatus;
    };
  }, [status.kind]);

  useEffect(() => {
    if (!online) {
      return;
    }

    const refresh = () => {
      void query.refetch();
    };
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };

    window.addEventListener("focus", refresh);
    window.addEventListener("online", refresh);
    window.addEventListener(COMPASS_MAINTENANCE_SIGNAL_EVENT, refresh);
    document.addEventListener("visibilitychange", refreshWhenVisible);

    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("online", refresh);
      window.removeEventListener(COMPASS_MAINTENANCE_SIGNAL_EVENT, refresh);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [online, query.refetch]);

  useEffect(() => {
    const delay = nextPollDelay(status);
    if (delay === null) {
      return;
    }

    const timer = window.setTimeout(() => {
      void query.refetch();
    }, delay);

    return () => window.clearTimeout(timer);
  }, [query.refetch, status]);

  useEffect(() => {
    const delay = transitionDelay(status);
    if (delay === null) {
      return;
    }

    const timer = window.setTimeout(() => {
      void query.refetch();
    }, delay);

    return () => window.clearTimeout(timer);
  }, [query.refetch, status]);

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

  let bannerStatus:
    | Extract<
        ServiceStatusView,
        {
          kind:
            | "maintenance_scheduled"
            | "maintenance_active"
            | "offline"
            | "unavailable";
        }
      >
    | null = null;

  if (!online) {
    bannerStatus = { kind: "offline" };
  } else if (
    backendStatus.kind === "maintenance_scheduled" ||
    backendStatus.kind === "unavailable" ||
    (backendStatus.kind === "maintenance_active" &&
      isMaintenanceExemptPath(pathname))
  ) {
    bannerStatus = backendStatus;
  }

  return (
    <>
      {children}
      {bannerStatus ? <ServiceStatusBanner status={bannerStatus} /> : null}
    </>
  );
}
