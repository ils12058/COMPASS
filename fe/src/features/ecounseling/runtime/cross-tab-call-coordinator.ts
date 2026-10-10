// Advisory protection against joining E-Counseling from two COMPASS tabs at once (ADR-094).
//
// Tabs talk over BroadcastChannel only, never browser storage. A message carries a random tab ID
// that lives in this tab's memory, a message type, and a claim time: no Appointment, participant,
// room URL, token or media. The tab with a call holds a lease it renews with a heartbeat, so a tab
// that crashed or closed without saying so stops blocking others once its lease runs out. Without
// BroadcastChannel the coordinator does nothing and each tab still allows only one call.
//
// It is advisory: it prevents an accidental second call, and the backend still decides every join.

export const CALL_CHANNEL_NAME = "compass-ecounseling-call";
export const HEARTBEAT_MS = 2_000;
export const LEASE_MS = 6_000;
export const CLAIM_WINDOW_MS = 250;

export type CoordinatorMessage =
  | { v: 1; type: "query"; tab: string }
  | { v: 1; type: "owner"; tab: string; since: number }
  | { v: 1; type: "released"; tab: string };

export type ChannelLike = {
  postMessage(message: CoordinatorMessage): void;
  addEventListener(type: "message", listener: (event: MessageEvent) => void): void;
  removeEventListener(type: "message", listener: (event: MessageEvent) => void): void;
  close(): void;
};

export type CoordinatorOptions = {
  createChannel?: () => ChannelLike | null;
  now?: () => number;
  setTimer?: (callback: () => void, ms: number) => unknown;
  clearTimer?: (timer: unknown) => void;
  wait?: (ms: number) => Promise<void>;
  tabId?: string;
};

function browserChannel(): ChannelLike | null {
  if (typeof BroadcastChannel === "undefined") return null;
  try {
    return new BroadcastChannel(CALL_CHANNEL_NAME) as unknown as ChannelLike;
  } catch {
    return null;
  }
}

function randomTabId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function isMessage(value: unknown): value is CoordinatorMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Record<string, unknown>;
  if (message.v !== 1 || typeof message.tab !== "string") return false;
  if (message.type === "owner") return typeof message.since === "number";
  return message.type === "query" || message.type === "released";
}

// The earlier claim wins; equal claim times fall back to the tab ID, so both tabs agree.
function precedes(a: { since: number; tab: string }, b: { since: number; tab: string }) {
  return a.since < b.since || (a.since === b.since && a.tab < b.tab);
}

export class CrossTabCallCoordinator {
  readonly tabId: string;
  private channel: ChannelLike | null = null;
  private readonly foreign = new Map<string, { since: number; expires: number }>();
  private claim: { since: number } | null = null;
  private heartbeat: unknown = null;
  private expiry: unknown = null;
  private readonly listeners = new Set<() => void>();
  private blocked = false;
  private readonly createChannel: () => ChannelLike | null;
  private readonly now: () => number;
  private readonly setTimer: (callback: () => void, ms: number) => unknown;
  private readonly clearTimer: (timer: unknown) => void;
  private readonly wait: (ms: number) => Promise<void>;

  constructor(options: CoordinatorOptions = {}) {
    this.createChannel = options.createChannel ?? browserChannel;
    this.now = options.now ?? Date.now;
    this.setTimer = options.setTimer ?? ((callback, ms) => setTimeout(callback, ms));
    this.clearTimer = options.clearTimer ?? ((timer) => clearTimeout(timer as ReturnType<typeof setTimeout>));
    this.wait = options.wait ?? ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
    this.tabId = options.tabId ?? randomTabId();
  }

  // Joins the channel and asks whether another tab already has a call.
  start() {
    if (this.channel) return;
    this.channel = this.createChannel();
    if (!this.channel) return;
    this.channel.addEventListener("message", this.onMessage);
    this.post({ v: 1, type: "query", tab: this.tabId });
  }

  stop() {
    this.release();
    if (this.expiry !== null) this.clearTimer(this.expiry);
    this.expiry = null;
    this.channel?.removeEventListener("message", this.onMessage);
    this.channel?.close();
    this.channel = null;
    this.foreign.clear();
    this.refresh();
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  // Whether another tab currently holds an unexpired lease.
  getSnapshot = () => this.blocked;

  // Tries to take the lease before a join. False when another tab holds one, or claimed first
  // during the short window in which competing claims are heard.
  async acquire(): Promise<boolean> {
    if (!this.channel) return true;
    this.prune();
    if (this.foreign.size > 0) return false;
    if (this.claim) return true;
    const mine = { since: this.now(), tab: this.tabId };
    this.claim = { since: mine.since };
    this.post({ v: 1, type: "owner", tab: this.tabId, since: mine.since });
    await this.wait(CLAIM_WINDOW_MS);
    if (!this.claim) return false;
    this.prune();
    const earlier = [...this.foreign.entries()].some(([tab, lease]) => precedes({ since: lease.since, tab }, mine));
    if (earlier) {
      this.release();
      return false;
    }
    this.startHeartbeat();
    return true;
  }

  release() {
    if (!this.claim) return;
    this.claim = null;
    if (this.heartbeat !== null) this.clearTimer(this.heartbeat);
    this.heartbeat = null;
    this.post({ v: 1, type: "released", tab: this.tabId });
  }

  private startHeartbeat() {
    const beat = () => {
      if (!this.claim) return;
      this.post({ v: 1, type: "owner", tab: this.tabId, since: this.claim.since });
      this.heartbeat = this.setTimer(beat, HEARTBEAT_MS);
    };
    this.heartbeat = this.setTimer(beat, HEARTBEAT_MS);
  }

  private post(message: CoordinatorMessage) {
    try {
      this.channel?.postMessage(message);
    } catch {
      // A closed channel only loses advisory messages.
    }
  }

  private onMessage = (event: MessageEvent) => {
    const message: unknown = event.data;
    if (!isMessage(message) || message.tab === this.tabId) return;
    if (message.type === "query") {
      if (this.claim) this.post({ v: 1, type: "owner", tab: this.tabId, since: this.claim.since });
      return;
    }
    if (message.type === "released") this.foreign.delete(message.tab);
    else this.foreign.set(message.tab, { since: message.since, expires: this.now() + LEASE_MS });
    this.refresh();
  };

  private prune() {
    const now = this.now();
    for (const [tab, lease] of this.foreign) if (lease.expires <= now) this.foreign.delete(tab);
  }

  // Recomputes the blocked state and schedules the next lease expiry, so a crashed tab's lease
  // stops blocking without anyone polling.
  private refresh() {
    this.prune();
    if (this.expiry !== null) this.clearTimer(this.expiry);
    this.expiry = null;
    const next = Math.min(...[...this.foreign.values()].map((lease) => lease.expires));
    if (Number.isFinite(next)) this.expiry = this.setTimer(() => this.refresh(), Math.max(0, next - this.now()) + 1);
    const blocked = this.foreign.size > 0;
    if (blocked !== this.blocked) {
      this.blocked = blocked;
      for (const listener of this.listeners) listener();
    }
  }
}
