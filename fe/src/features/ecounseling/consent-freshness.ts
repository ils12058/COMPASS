import type { QueryClient, QueryKey } from "@tanstack/react-query";

import type { ECounselingAccess } from "./ecounseling-access";
import { ecounselingResourceAccess } from "./ecounseling-resource-access";
import { sessionRefreshInterval } from "./ecounseling-shared";
import { isOpaqueRealtimeId } from "@/features/realtime/realtime-protocol";
import type { RealtimeSnapshot } from "@/features/realtime/realtime-runtime";
import {
  getECounselingGetAssignedWorkspaceQueryKey,
  getECounselingGetMyWorkspaceQueryKey,
  getECounselingListAssignedConsentsQueryKey,
  getECounselingListMyConsentsQueryKey,
} from "@/lib/api/generated/e-counseling/e-counseling";
import type { eCounselingListMyConsentsResponseSuccess } from "@/lib/api/generated/e-counseling/e-counseling";
import type { StudentWorkspaceResponse } from "@/lib/api/generated/model";

export const CONSENT_FALLBACK_REFRESH_MS = 7_000;
export const CONSENT_LIVE_SAFETY_REFRESH_MS = 60_000;

type Environment = {
  document: Pick<Document, "visibilityState" | "addEventListener" | "removeEventListener">;
  window: Pick<Window, "setInterval" | "clearInterval" | "addEventListener" | "removeEventListener">;
  navigator: Pick<Navigator, "onLine">;
};
type Selection = "all" | "consent" | "workspace";
type Family = { key: (id: string) => QueryKey; consent: boolean };
type Refresh = {
  consent: boolean; workspace: boolean; running: boolean; queued: boolean;
  fenceConsent: boolean; fenceWorkspace: boolean; freshConsent: boolean; freshWorkspace: boolean;
};
type WorkspaceData = { data?: Pick<StudentWorkspaceResponse, "media" | "provider_readiness"> };

// RT-1B extends RT-1A's one account-owned engine. Consent and media have separate work/fence
// bits and polling policies, sharing canonical selection, coalescing, recovery and disposal.
export class ECounselingConsentFreshness {
  private families: Family[];
  private environment: Environment | null = null;
  private refreshes = new Map<string, Refresh>();
  private listeners = new Set<() => void>();
  private timer: number | null = null;
  private mediaTimers = new Map<string, { timer: number; interval: number }>();
  private unsubscribeCache: (() => void) | null = null;
  private activeCall: string | null = null;
  private live = false;
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
  isPending = (id: string) => this.refreshes.get(id)?.fenceConsent ?? false;
  isWorkspacePending = (id: string) => this.refreshes.get(id)?.fenceWorkspace ?? false;
  private notify() { for (const listener of this.listeners) listener(); }
  private canRefresh() {
    return this.environment?.document.visibilityState === "visible" && this.environment.navigator.onLine;
  }
  private selected(family: Family, selection: Selection) {
    return selection === "all" || family.consent === (selection === "consent");
  }
  private appointment(key: QueryKey, selection: Selection = "all"): string | null {
    if (key.length !== 1 || typeof key[0] !== "string") return null;
    for (const family of this.families) {
      if (!this.selected(family, selection)) continue;
      const root = family.key("")[0];
      if (typeof root !== "string") continue;
      const prefix = root.split("/consents")[0];
      if (!key[0].startsWith(prefix)) continue;
      const id: string = key[0].slice(prefix.length).split("/")[0];
      if (isOpaqueRealtimeId(id) && family.key(id)[0] === key[0]) return id;
    }
    return null;
  }
  private keys(id: string, selection: Selection = "all") {
    return this.families.filter((family) => this.selected(family, selection)).map((family) => family.key(id)).filter((key) => this.client.getQueryState(key) !== undefined);
  }
  private markStale(id: string, selection: Selection) {
    for (const key of this.keys(id, selection)) void this.client.invalidateQueries({ queryKey: key, exact: true, refetchType: "none" });
  }
  private schedule(id: string, refresh: Refresh) {
    if (refresh.running || refresh.queued) return;
    refresh.queued = true;
    queueMicrotask(() => { refresh.queued = false; void this.flush(id, refresh); });
  }
  private queue(id: unknown, selection: Selection) {
    if (!this.environment || !isOpaqueRealtimeId(id) || !this.keys(id, selection).length || ecounselingResourceAccess(this.client).getDenial(id)) return;
    const refresh = this.refreshes.get(id) ?? {
      consent: false, workspace: false, running: false, queued: false,
      fenceConsent: false, fenceWorkspace: false, freshConsent: false, freshWorkspace: false,
    };
    for (const kind of ["consent", "workspace"] as const) {
      if (selection !== "all" && selection !== kind) continue;
      if (!this.keys(id, kind).length) continue;
      // A request begun before this hint cannot establish post-hint truth. Reuse it,
      // then queue one fresh read. Hints during our own read already set a trailing bit.
      if (!refresh.running && this.keys(id, kind).some((key) => this.client.getQueryState(key)?.fetchStatus === "fetching")) {
        if (kind === "consent") refresh.freshConsent = true;
        else refresh.freshWorkspace = true;
      }
      refresh[kind] = true;
      if (kind === "consent") refresh.fenceConsent = true;
      else refresh.fenceWorkspace = true;
    }
    if (selection === "all" && (refresh.freshConsent || refresh.freshWorkspace)) {
      // Preserve RT-1A's complete post-hint consent/workspace reconciliation if either
      // authoritative read predates the consent hint. Media-only hints remain workspace-only.
      refresh.freshConsent = this.keys(id, "consent").length > 0;
      refresh.freshWorkspace = this.keys(id, "workspace").length > 0;
    }
    this.refreshes.set(id, refresh);
    this.markStale(id, selection);
    this.notify();
    this.schedule(id, refresh);
  }
  requestRefresh = (id: unknown, consentOnly = false) => this.queue(id, consentOnly ? "consent" : "all");
  requestMediaRefresh = (id: unknown) => this.queue(id, "workspace");

  async refreshWorkspace(id: string) {
    this.requestMediaRefresh(id);
    if (!this.isWorkspacePending(id)) return;
    await new Promise<void>((resolve) => {
      const unsubscribe = this.subscribe(() => {
        if (!this.environment || !this.isWorkspacePending(id)) { unsubscribe(); resolve(); }
      });
    });
  }
  private read(keys: QueryKey[]) {
    return Promise.allSettled(keys.map((key) => this.client.refetchQueries(
      { queryKey: key, exact: true, type: "active" }, { cancelRefetch: false },
    )));
  }
  private async flush(id: string, refresh: Refresh) {
    if (refresh.running || !this.canRefresh() || this.refreshes.get(id) !== refresh) return;
    refresh.running = true;
    try {
      // One leading pass plus one trailing pass. Further changes retain one pending bit
      // for a later microtask, rather than keeping an unbounded loop in this invocation.
      for (let pass = 0; pass < 2 && (refresh.consent || refresh.workspace) && this.canRefresh() && this.refreshes.get(id) === refresh; pass++) {
        if (ecounselingResourceAccess(this.client).getDenial(id)) break;
        const consent = refresh.consent;
        const workspace = refresh.workspace;
        const freshConsent = refresh.freshConsent;
        const freshWorkspace = refresh.freshWorkspace;
        refresh.consent = refresh.workspace = refresh.freshConsent = refresh.freshWorkspace = false;
        const consentKeys = consent ? this.keys(id, "consent") : [];
        const previous = consentKeys.map((key) => this.client.getQueryData<eCounselingListMyConsentsResponseSuccess>(key)?.data?.items);
        await this.read([...consentKeys, ...(workspace ? this.keys(id, "workspace") : [])]);
        if (!this.environment || this.refreshes.get(id) !== refresh) return;
        if (consent && !workspace && this.canRefresh() && consentKeys.some((key, index) =>
          this.client.getQueryState(key)?.status === "success" && previous[index] !== this.client.getQueryData<eCounselingListMyConsentsResponseSuccess>(key)?.data?.items,
        )) {
          refresh.fenceWorkspace = true;
          const workspaceKeys = this.keys(id, "workspace");
          const oldRead = workspaceKeys.some((key) => this.client.getQueryState(key)?.fetchStatus === "fetching");
          this.markStale(id, "workspace");
          this.notify();
          await this.read(workspaceKeys);
          if (!this.environment || this.refreshes.get(id) !== refresh) return;
          refresh.workspace ||= oldRead;
        }
        refresh.consent ||= freshConsent;
        refresh.workspace ||= freshWorkspace;
        if (refresh.consent) this.markStale(id, "consent");
        if (refresh.workspace) this.markStale(id, "workspace");
      }
    } finally {
      refresh.running = false;
      if (this.refreshes.get(id) === refresh) {
        if ((!refresh.consent && !refresh.workspace) || ecounselingResourceAccess(this.client).getDenial(id)) this.refreshes.delete(id);
        else if (this.canRefresh()) this.schedule(id, refresh);
      }
      this.notify();
    }
  }
  reconcile = (consentOnly = false) => {
    if (!this.canRefresh()) return;
    const ids = new Set(this.client.getQueryCache().getAll().flatMap((query) => {
      const id = query.isActive() ? this.appointment(query.queryKey, consentOnly ? "consent" : "all") : null;
      return id ? [id] : [];
    }));
    for (const id of new Set([...ids, ...this.refreshes.keys()])) {
      // A safety clock is redundant while this appointment already has a canonical read.
      // Events and foreground recovery still retain the necessary trailing reconciliation.
      if (!consentOnly || !this.refreshes.has(id)) this.requestRefresh(id, consentOnly);
    }
  };
  setActiveCall(id: string | null) {
    this.activeCall = isOpaqueRealtimeId(id) ? id : null;
    this.updateMediaTimers();
  }
  private updateMediaTimers = () => {
    if (!this.environment) return;
    const wanted = new Map<string, number>();
    for (const query of this.client.getQueryCache().getAll()) {
      if (!query.isActive()) continue;
      const id = this.appointment(query.queryKey, "workspace");
      if (!id || ecounselingResourceAccess(this.client).getDenial(id)) continue;
      const data = this.client.getQueryData<WorkspaceData>(query.queryKey)?.data;
      const interval = sessionRefreshInterval(id === this.activeCall, data?.media, this.live)
        || (data?.provider_readiness?.join_allowed ? (this.live ? CONSENT_LIVE_SAFETY_REFRESH_MS : CONSENT_FALLBACK_REFRESH_MS) : false);
      if (interval) wanted.set(id, interval);
    }
    for (const [id, current] of this.mediaTimers) {
      if (wanted.get(id) !== current.interval) {
        this.environment.window.clearInterval(current.timer);
        this.mediaTimers.delete(id);
      }
    }
    for (const [id, interval] of wanted) {
      if (!this.mediaTimers.has(id)) this.mediaTimers.set(id, {
        // A consent-only poll must not starve a simultaneously due workspace poll.
        interval, timer: this.environment.window.setInterval(() => { if (this.canRefresh() && !this.isWorkspacePending(id)) this.requestMediaRefresh(id); }, interval),
      });
    }
  };
  setRealtimeStatus(snapshot: RealtimeSnapshot) {
    if (!this.environment) return;
    this.live = snapshot.state === "live";
    const interval = this.live ? CONSENT_LIVE_SAFETY_REFRESH_MS : CONSENT_FALLBACK_REFRESH_MS;
    if (interval !== this.interval) { this.interval = interval; this.resetTimer(); }
    this.updateMediaTimers();
    if (snapshot.generation > this.generation) { this.generation = snapshot.generation; this.reconcile(); }
  }
  private resetTimer() {
    if (!this.environment) return;
    if (this.timer !== null) this.environment.window.clearInterval(this.timer);
    this.timer = this.environment.window.setInterval(() => this.reconcile(true), this.interval);
  }
  private onForeground = () => this.reconcile();
  start(environment: Environment) {
    this.environment = environment;
    this.generation = 0;
    this.resetTimer();
    this.unsubscribeCache = this.client.getQueryCache().subscribe(this.updateMediaTimers);
    this.updateMediaTimers();
    environment.document.addEventListener("visibilitychange", this.onForeground);
    environment.window.addEventListener("focus", this.onForeground);
    environment.window.addEventListener("online", this.onForeground);
  }
  stop() {
    if (!this.environment) return;
    if (this.timer !== null) this.environment.window.clearInterval(this.timer);
    for (const current of this.mediaTimers.values()) this.environment.window.clearInterval(current.timer);
    this.mediaTimers.clear();
    this.unsubscribeCache?.();
    this.unsubscribeCache = null;
    this.environment.document.removeEventListener("visibilitychange", this.onForeground);
    this.environment.window.removeEventListener("focus", this.onForeground);
    this.environment.window.removeEventListener("online", this.onForeground);
    this.environment = null;
    this.activeCall = null;
    this.refreshes.clear();
    this.notify();
  }
}
