"use client";

import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { boundaryDelay } from "@/features/freshness/use-server-boundary";
import {
  getPlatformPublicStatusQueryOptions,
  usePlatformPublicStatus,
} from "@/lib/api/generated/platform-operations/platform-operations";
import { PublicPlatformStatus, type PlatformPublicStatusResponse } from "@/lib/api/generated/model";

// What COMPASS shows for Maintenance Mode comes only from the public status endpoint, which the
// backend keeps reachable during maintenance. "unknown" means no status has been read: it never
// locks COMPASS, and it never claims COMPASS is fine either.
export type MaintenancePhase = "operational" | "scheduled" | "active" | "unknown";

export function maintenancePhase(status: PlatformPublicStatusResponse | undefined): MaintenancePhase {
  if (!status) return "unknown";
  if (status.status === PublicPlatformStatus.maintenance_active) return "active";
  if (status.status === PublicPlatformStatus.maintenance_scheduled) return "scheduled";
  return "operational";
}

// The moment the backend's answer may change: a scheduled window's start, or an active window's
// end. Reaching it only means "ask again". An expected end for manual maintenance is a promise,
// not a switch, so COMPASS stays in maintenance until the backend reports otherwise.
export function maintenanceBoundary(status: PlatformPublicStatusResponse | undefined): string | null {
  const phase = maintenancePhase(status);
  if (phase === "scheduled") return status?.starts_at ?? null;
  if (phase === "active") return status?.ends_at ?? null;
  return null;
}

// Where an authenticated portal route goes during maintenance. The backend keeps Platform
// Operations available so an operator can end maintenance; everything else would only fail.
export type PortalMaintenanceMode = "workspace" | "maintenance" | "recovery";

export function portalMaintenanceMode({
  phase,
  pathname,
  canOperate,
}: {
  phase: MaintenancePhase;
  pathname: string;
  canOperate: boolean;
}): PortalMaintenanceMode {
  if (phase !== "active") return "workspace";
  const platformRoute = pathname === "/portal/platform" || pathname.startsWith("/portal/platform/");
  return platformRoute && canOperate ? "recovery" : "maintenance";
}

// Reads the status again now, whatever its age. Observers of the status query update with it.
export function checkMaintenanceStatus(queryClient: QueryClient) {
  return queryClient.fetchQuery(getPlatformPublicStatusQueryOptions({ query: { staleTime: 0, retry: false } }));
}

const BOUNDARY_BUFFER_MS = 1_000;
const MAX_TIMEOUT_MS = 2_147_483_647;

// How long to wait before asking again at the next boundary, by the server's clock, or null when
// there is nothing to wait for. A boundary already past when the status was read is reflected in
// that status, so it schedules nothing; polling carries on from there.
export function boundaryRefetchDelay(
  status: PlatformPublicStatusResponse | undefined,
  serverDate?: string | null,
  receivedAt?: number,
): number | null {
  const delay = boundaryDelay(maintenanceBoundary(status), serverDate, receivedAt);
  if (delay === null || delay === 0) return null;
  return Math.min(delay + BOUNDARY_BUFFER_MS, MAX_TIMEOUT_MS);
}

// The public maintenance status. One place on each page `watch`es it: that observer polls (every
// 30 seconds during maintenance, every minute otherwise) and asks again just after the next
// boundary, measured against the server's clock. Other readers share the same query.
export function useMaintenanceStatus({ watch = false }: { watch?: boolean } = {}) {
  const queryClient = useQueryClient();
  const query = usePlatformPublicStatus({
    query: {
      retry: false,
      staleTime: 15_000,
      refetchOnWindowFocus: watch,
      refetchInterval: watch
        ? (current) => (maintenancePhase(current.state.data?.data) === "active" ? 30_000 : 60_000)
        : false,
    },
  });
  const status = query.data?.data;
  const phase = maintenancePhase(status);
  const boundary = maintenanceBoundary(status);
  const serverDate = query.data?.headers.date;
  const receivedAt = query.dataUpdatedAt;
  const refetch = query.refetch;
  const askedAt = useRef<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkedAt, setCheckedAt] = useState<number | null>(null);

  useEffect(() => {
    if (!watch || !boundary) return;
    const key = `${phase}:${boundary}`;
    if (askedAt.current === key) return;
    const delay = boundaryRefetchDelay(status, serverDate, receivedAt);
    if (delay === null) return;
    const timer = setTimeout(() => {
      askedAt.current = key;
      void refetch();
    }, delay);
    return () => clearTimeout(timer);
  }, [watch, phase, boundary, status, serverDate, receivedAt, refetch]);

  const check = useCallback(async () => {
    setChecking(true);
    try {
      await checkMaintenanceStatus(queryClient);
    } catch {
      // A failed check keeps the last confirmed status; the page says when it last asked.
    } finally {
      setChecking(false);
      setCheckedAt(Date.now());
    }
  }, [queryClient]);

  return { status, phase, pending: query.isPending, checking, checkedAt, check };
}
