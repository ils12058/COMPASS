import type { QueryClient, QueryKey } from "@tanstack/react-query";

import type { ECounselingAccess } from "./ecounseling-access";
import { ecounselingResourceAccess } from "./ecounseling-resource-access";
import { isOpaqueRealtimeId } from "@/features/realtime/realtime-protocol";
import type { RealtimeSnapshot } from "@/features/realtime/realtime-runtime";
import {
  getECounselingGetAssignedWorkspaceQueryKey,
  getECounselingGetMyWorkspaceQueryKey,
  getECounselingListAssignedConsentsQueryKey,
  getECounselingListMyConsentsQueryKey,
} from "@/lib/api/generated/e-counseling/e-counseling";
import type { eCounselingListMyConsentsResponseSuccess } from "@/lib/api/generated/e-counseling/e-counseling";

export const CONSENT_FALLBACK_REFRESH_MS = 7_000;
export const CONSENT_LIVE_SAFETY_REFRESH_MS = 60_000;

type Environment = {
  document: Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
  window: Pick<Window, "setInterval" | "clearInterval" | "addEventListener" | "removeEventListener">;
  navigator: Pick<Navigator, "onLine">;
};
type Family = { key: (id: string) => QueryKey; consent: boolean };
type Refresh = { pending: boolean; running: boolean; queued: boolean; includeWorkspace: boolean; needsFreshRead: boolean };

// No socket, data copy, durable queue or browser-global appointment ownership. The one portal
// consumer operates on canonical queries already known to this account's QueryClient (RT-1A).
export class ECounselingConsentFreshness {
  private families: Family[];
  private environment: Environment | null = null;
  private refreshes = new Map<string, Refresh>();
  private listeners = new Set<() => void>();
  private timer: number | null = null;
  private interval = CONSENT_FALLBACK_REFRESH_MS;
  private generation = 0;

  constructor(private client: QueryClient, access: ECounselingAccess) {
    this.families = [
      ...(access.canViewSelf ? [{ key: getECounselingGetMyWorkspaceQueryKey, consent: false }] : []),
      ...(access.canConsentSelf ? [{ key: getECounselingListMyConsentsQueryKey, consent: true }] : []),
      ...(access.canViewAssigned ? [{ key: getECounselingGetAssignedWorkspaceQueryKey, consent: false }] : []),
      ...(access.canManageMediaAssigned ? [{ key: getECounselingListAssignedConsentsQueryKey, consent: true }] : []),
    ];
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };
  isPending = (id: string) => this.refreshes.has(id);
  private notify() { for (const listener of this.listeners) listener(); }
  private canRefresh() {
    return this.environment?.document.visibilityState === "visible" && this.environment.navigator.onLine;
  }
  private appointment(key: QueryKey, consentOnly = false): string | null {
    if (key.length !== 1 || typeof key[0] !== "string") return null;
    for (const family of this.families) {
      if (consentOnly && !family.consent) continue;
      const root = family.key("")[0];
      if (typeof root !== "string") continue;
      // Consent keys have a suffix; use the generated function to check the exact full key.
      const prefix = root.split("/consents")[0];
      if (!key[0].startsWith(prefix)) continue;
      const id: string = key[0].slice(prefix.length).split("/")[0];
      if (isOpaqueRealtimeId(id) && family.key(id)[0] === key[0]) return id;
    }
    return null;
  }
  private keys(id: string, consentOnly = false) {
    return this.families.filter((family) => !consentOnly || family.consent).map((family) => family.key(id)).filter((key) => this.client.getQueryState(key) !== undefined);
  }
  private markStale(id: string, consentOnly = false) {
    for (const key of this.keys(id, consentOnly)) {
      void this.client.invalidateQueries({ queryKey: key, exact: true, refetchType: "none" });
    }
  }

  requestRefresh = (id: unknown, consentOnly = false) => {
    if (!this.environment || !isOpaqueRealtimeId(id) || !this.keys(id).length || ecounselingResourceAccess(this.client).getDenial(id)) return;
    const refresh = this.refreshes.get(id) ?? { pending: false, running: false, queued: false, includeWorkspace: false, needsFreshRead: false };
    if (!consentOnly && !refresh.running && !refresh.queued && this.keys(id).some((key) => this.client.getQueryState(key)?.fetchStatus === "fetching")) {
      // A read started before this hint may return the pre-change permission. Reuse it,
      // then obtain one post-hint read before lifting the Start fence.
      refresh.needsFreshRead = true;
    }
    this.refreshes.set(id, refresh);
    refresh.pending = true;
    refresh.includeWorkspace ||= !consentOnly;
    // Fence an old APPROVED result immediately, including hidden/offline or in-flight reads.
    this.markStale(id, consentOnly);
    this.notify();
    if (!refresh.running && !refresh.queued) {
      refresh.queued = true;
      queueMicrotask(() => { refresh.queued = false; void this.flush(id, refresh); });
    }
  };

  private async flush(id: string, refresh: Refresh) {
    if (refresh.running || !this.canRefresh() || this.refreshes.get(id) !== refresh) return;
    refresh.running = true;
    try {
      while (refresh.pending && this.canRefresh() && this.refreshes.get(id) === refresh) {
        if (ecounselingResourceAccess(this.client).getDenial(id)) break;
        refresh.pending = false;
        const consentOnly = !refresh.includeWorkspace;
        refresh.includeWorkspace = false;
        const needsFreshRead = refresh.needsFreshRead;
        refresh.needsFreshRead = false;
        const consentKeys = this.keys(id, true);
        const previous = consentKeys.map((key) => this.client.getQueryData<eCounselingListMyConsentsResponseSuccess>(key)?.data?.items);
        await Promise.allSettled(this.keys(id, consentOnly).map((key) => this.client.refetchQueries(
          { queryKey: key, exact: true, type: "active" },
          { cancelRefetch: false },
        )));
        if (!this.environment || this.refreshes.get(id) !== refresh) return;
        // Normal polling reads consent only. TanStack structural sharing preserves unchanged
        // item references; a confirmed change also refreshes the existing workspace projection.
        if (consentOnly && this.canRefresh() && this.refreshes.get(id) === refresh && consentKeys.some((key, index) =>
          this.client.getQueryState(key)?.status === "success" && previous[index] !== this.client.getQueryData<eCounselingListMyConsentsResponseSuccess>(key)?.data?.items,
        )) {
          const workspaceKeys = this.keys(id).filter((key) => !consentKeys.some((consent) => consent[0] === key[0]));
          for (const key of workspaceKeys) void this.client.invalidateQueries({ queryKey: key, exact: true, refetchType: "none" });
          await Promise.allSettled(workspaceKeys.map((key) => this.client.refetchQueries({ queryKey: key, exact: true, type: "active" }, { cancelRefetch: false })));
          if (!this.environment || this.refreshes.get(id) !== refresh) return;
        }
        if (needsFreshRead) {
          refresh.pending = true;
          refresh.includeWorkspace ||= !consentOnly;
        }
        // A hint received during a read requires one trailing read. Keep the safety fence up
        // throughout, even if that older request temporarily returned an APPROVED result.
        if (refresh.pending) this.markStale(id, !refresh.includeWorkspace);
      }
    } finally {
      refresh.running = false;
      if (this.refreshes.get(id) === refresh && (!refresh.pending || ecounselingResourceAccess(this.client).getDenial(id))) this.refreshes.delete(id);
      this.notify();
    }
  }

  reconcile = (consentOnly = false) => {
    if (!this.canRefresh()) return;
    const ids = new Set(this.client.getQueryCache().getAll().flatMap((query) => {
      const id = query.isActive() ? this.appointment(query.queryKey, consentOnly) : null;
      return id ? [id] : [];
    }));
    // Foreground recovery also drains hints received while hidden/offline.
    for (const id of new Set([...ids, ...this.refreshes.keys()])) this.requestRefresh(id, consentOnly);
  };

  setRealtimeStatus(snapshot: RealtimeSnapshot) {
    if (!this.environment) return;
    const interval = snapshot.state === "live" ? CONSENT_LIVE_SAFETY_REFRESH_MS : CONSENT_FALLBACK_REFRESH_MS;
    if (interval !== this.interval) {
      this.interval = interval;
      this.resetTimer();
    }
    if (snapshot.generation > this.generation) {
      this.generation = snapshot.generation;
      this.reconcile();
    }
  }
  private resetTimer() {
    if (!this.environment) return;
    if (this.timer !== null) this.environment.window.clearInterval(this.timer);
    // Only consent lists receive the new safety cadence. Media workspace polling is unchanged.
    this.timer = this.environment.window.setInterval(() => this.reconcile(true), this.interval);
  }
  private onForeground = () => this.reconcile();

  start(environment: Environment) {
    this.environment = environment;
    this.generation = 0;
    this.resetTimer();
    environment.document.addEventListener("visibilitychange", this.onForeground);
    environment.window.addEventListener("focus", this.onForeground);
    environment.window.addEventListener("online", this.onForeground);
  }
  stop() {
    if (!this.environment) return;
    if (this.timer !== null) this.environment.window.clearInterval(this.timer);
    this.environment.document.removeEventListener("visibilitychange", this.onForeground);
    this.environment.window.removeEventListener("focus", this.onForeground);
    this.environment.window.removeEventListener("online", this.onForeground);
    this.environment = null;
    this.refreshes.clear();
    this.notify();
  }
}
