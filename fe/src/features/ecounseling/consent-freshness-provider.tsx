"use client";

import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

import { useRealtimeEvent, useRealtimeStatus } from "@/features/realtime/realtime-provider";
import type { UserSummary } from "@/lib/api/generated/model";
import { getECounselingAccess } from "./ecounseling-access";
import { ECounselingConsentFreshness } from "./consent-freshness";

const Context = createContext<ECounselingConsentFreshness | null>(null);
const noSubscription = () => () => {};
const notPending = () => false;

// Mounted once inside the existing portal runtime, independent of Daily connection state.
export function ECounselingConsentFreshnessProvider({ user, children }: { user: UserSummary | null; children: ReactNode }) {
  const client = useQueryClient();
  const { state, generation } = useRealtimeStatus();
  const consumer = useMemo(() => {
    if (!user) return null;
    const access = getECounselingAccess(user);
    return access.hasWorkspace ? new ECounselingConsentFreshness(client, access) : null;
  }, [client, user]);
  useEffect(() => {
    consumer?.start({ document, window, navigator });
    return () => consumer?.stop();
  }, [consumer]);
  useEffect(() => { consumer?.setRealtimeStatus({ state, generation }); }, [consumer, state, generation]);
  useRealtimeEvent("ecounseling.consent.changed", (event) => consumer?.requestRefresh(event.appointment_id));
  useRealtimeEvent("ecounseling.media.changed", (event) => consumer?.requestMediaRefresh(event.appointment_id));
  return <Context.Provider value={consumer}>{children}</Context.Provider>;
}

export function useECounselingFreshness() { return useContext(Context); }

export function usePendingECounselingMedia(appointmentId: string): boolean {
  const consumer = useContext(Context);
  return useSyncExternalStore(consumer?.subscribe ?? noSubscription, () => consumer?.isWorkspacePending(appointmentId) ?? false, notPending);
}

/** A successful previous response is not Start permission while a hint/refetch is unresolved. */
export function useConfirmedECounselingConsent(appointmentId: string, queryKey: QueryKey): boolean {
  const client = useQueryClient();
  const consumer = useContext(Context);
  const pending = useSyncExternalStore(consumer?.subscribe ?? noSubscription, () => consumer?.isPending(appointmentId) ?? false, notPending);
  const confirmed = () => {
    const query = client.getQueryState(queryKey);
    return query?.status === "success" && !query.isInvalidated && query.fetchStatus === "idle";
  };
  const current = useSyncExternalStore(
    (notify) => client.getQueryCache().subscribe(notify),
    confirmed,
    confirmed,
  );
  return current && !pending;
}
