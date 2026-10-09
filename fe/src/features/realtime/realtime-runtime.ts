// The portal's one realtime connection per tab (ADR-100). Framework-free so its lifecycle can be
// tested without React or a browser.
//
// It belongs to one confirmed account at a time. Every connection starts by asking the ordinary
// HTTP API for a one-time ticket; the ticket travels only in the first socket frame, never in the
// URL. After `ready` the socket only receives content-free hints, and consumers re-read canonical
// data over HTTP. Nothing in COMPASS waits for this runtime: when it is not `live`, consumers keep
// their existing polling.

import { authenticateFrame, parseServerFrame, REALTIME_CLOSE, type RealtimeEvent } from "@/features/realtime/realtime-protocol";

export type RealtimeState = "disabled" | "idle" | "connecting" | "live" | "reconnecting" | "offline";

/** `generation` increases on every `ready`: a fresh connection after which consumers reconcile. */
export type RealtimeSnapshot = Readonly<{ state: RealtimeState; generation: number }>;

export type TicketOutcome =
  | { kind: "ticket"; ticket: string; userId: string }
  | { kind: "session-ended" }
  | { kind: "disabled" }
  | { kind: "unavailable" };

/** The part of a browser WebSocket the runtime uses. */
export type SocketLike = Pick<WebSocket, "onopen" | "onmessage" | "onclose" | "onerror" | "send" | "close">;

export type RealtimeRuntimeOptions = {
  /** The configured socket URL, or null when realtime is disabled for this build. */
  url: string | null;
  requestTicket: (signal: AbortSignal) => Promise<TicketOutcome>;
  createSocket: (url: string) => SocketLike;
  /** The server says this session ended: the portal re-checks it over HTTP. */
  onSessionEnded: () => void;
  isOnline?: () => boolean;
  isVisible?: () => boolean;
  setTimer?: (callback: () => void, ms: number) => unknown;
  clearTimer?: (timer: unknown) => void;
  now?: () => number;
  random?: () => number;
};

/** A hidden tab keeps its socket this long, so a quick tab switch does not reconnect. */
export const HIDDEN_GRACE_MS = 30_000;
export const BACKOFF_BASE_MS = 1_000;
export const BACKOFF_MAX_MS = 60_000;
/** A connection that stayed live this long resets the backoff. */
export const STABLE_CONNECTION_MS = 60_000;
/** Reconnects after the server's lifetime close are spread over this window. */
export const LIFETIME_RECONNECT_SPREAD_MS = 2_000;
/** The server allows 5 seconds to authenticate; a socket that is not ready by this is dropped. */
export const READY_TIMEOUT_MS = 10_000;

const DISABLED: RealtimeSnapshot = Object.freeze({ state: "disabled", generation: 0 });

/** Exponential backoff with jitter: half the ceiling is fixed, half random. */
export function backoffDelay(attempt: number, random: () => number = Math.random): number {
  const ceiling = Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, attempt));
  return Math.round(ceiling / 2 + (random() * ceiling) / 2);
}

/** Realtime belongs only to a confirmed account; a session being checked has no socket. */
export function realtimeAccount(authState: string, userId: string | null | undefined): string | null {
  return authState === "confirmed" && userId ? userId : null;
}

type Connection = {
  account: string;
  abort: AbortController;
  socket: SocketLike | null;
  readyTimer: unknown;
  liveSince: number | null;
};

export class RealtimeRuntime {
  private readonly url: string | null;
  private readonly requestTicket: RealtimeRuntimeOptions["requestTicket"];
  private readonly createSocket: RealtimeRuntimeOptions["createSocket"];
  private readonly onSessionEnded: () => void;
  private readonly setTimer: (callback: () => void, ms: number) => unknown;
  private readonly clearTimer: (timer: unknown) => void;
  private readonly now: () => number;
  private readonly random: () => number;

  private snapshot: RealtimeSnapshot;
  private account: string | null = null;
  private online: boolean;
  private visible: boolean;
  private serverDisabled = false;
  private everLive = false;
  private failures = 0;
  private connection: Connection | null = null;
  private retryTimer: unknown = null;
  private hiddenTimer: unknown = null;
  private readonly stateListeners = new Set<() => void>();
  private readonly eventListeners = new Map<string, Set<(event: RealtimeEvent) => void>>();

  constructor(options: RealtimeRuntimeOptions) {
    this.url = options.url;
    this.requestTicket = options.requestTicket;
    this.createSocket = options.createSocket;
    this.onSessionEnded = options.onSessionEnded;
    this.setTimer = options.setTimer ?? ((callback, ms) => setTimeout(callback, ms));
    this.clearTimer = options.clearTimer ?? ((timer) => clearTimeout(timer as ReturnType<typeof setTimeout>));
    this.now = options.now ?? Date.now;
    this.random = options.random ?? Math.random;
    this.online = options.isOnline?.() ?? true;
    this.visible = options.isVisible?.() ?? true;
    this.snapshot = this.url ? Object.freeze({ state: "idle", generation: 0 }) : DISABLED;
  }

  getSnapshot = (): RealtimeSnapshot => this.snapshot;

  subscribe = (listener: () => void): (() => void) => {
    this.stateListeners.add(listener);
    return () => {
      this.stateListeners.delete(listener);
    };
  };

  /** Listen for one hint type. Every consumer shares this runtime's single socket. */
  subscribeEvent(type: string, listener: (event: RealtimeEvent) => void): () => void {
    const listeners = this.eventListeners.get(type) ?? new Set();
    listeners.add(listener);
    this.eventListeners.set(type, listeners);
    return () => {
      listeners.delete(listener);
      if (listeners.size === 0) this.eventListeners.delete(type);
    };
  }

  /** The confirmed account, or null. A different account never inherits the previous socket. */
  setAccount(account: string | null): void {
    if (account === this.account) return;
    // The previous account's socket is closed, synchronously, before anything starts for the next.
    this.teardown();
    this.account = account;
    this.failures = 0;
    this.everLive = false;
    this.evaluate();
  }

  setOnline(online: boolean): void {
    if (online === this.online) return;
    this.online = online;
    if (!this.active()) return;
    if (!online) {
      this.teardown();
      this.setState("offline");
      return;
    }
    // The network came back: try promptly instead of waiting out a backoff.
    this.failures = 0;
    this.clearRetry();
    if (!this.connection) this.evaluate();
  }

  setVisible(visible: boolean): void {
    if (visible === this.visible) return;
    this.visible = visible;
    if (!this.active()) return;
    if (!visible) {
      if ((this.connection || this.retryTimer !== null) && this.hiddenTimer === null) {
        this.hiddenTimer = this.setTimer(() => {
          this.hiddenTimer = null;
          if (this.visible) return;
          this.teardown();
          this.setState("idle");
        }, HIDDEN_GRACE_MS);
      }
      return;
    }
    this.clearHidden();
    if (!this.connection && this.retryTimer === null) this.evaluate();
  }

  private active(): boolean {
    return this.url !== null && !this.serverDisabled && this.account !== null;
  }

  private setState(state: RealtimeState, { advance = false } = {}): void {
    if (state === this.snapshot.state && !advance) return;
    this.snapshot = Object.freeze({
      state,
      generation: advance ? this.snapshot.generation + 1 : this.snapshot.generation,
    });
    for (const listener of [...this.stateListeners]) listener();
  }

  private pendingState(): RealtimeState {
    return this.everLive ? "reconnecting" : "connecting";
  }

  /** Decide what to do now that nothing is connected or scheduled. */
  private evaluate(): void {
    if (this.url === null || this.serverDisabled) return this.setState("disabled");
    if (this.account === null) return this.setState("idle");
    if (!this.online) return this.setState("offline");
    if (!this.visible) return this.setState("idle");
    this.connect(this.url, this.account);
  }

  private connect(url: string, account: string): void {
    this.clearRetry();
    const connection: Connection = {
      account,
      abort: new AbortController(),
      socket: null,
      readyTimer: null,
      liveSince: null,
    };
    this.connection = connection;
    this.setState(this.pendingState());
    this.requestTicket(connection.abort.signal).then(
      (outcome) => this.ticketReceived(url, connection, outcome),
      () => this.ticketReceived(url, connection, { kind: "unavailable" }),
    );
  }

  private ticketReceived(url: string, connection: Connection, outcome: TicketOutcome): void {
    // A ticket for an attempt that was abandoned (another account, sign-out, offline) is dropped.
    if (connection !== this.connection) return;
    if (outcome.kind === "disabled") {
      this.connection = null;
      this.serverDisabled = true;
      this.setState("disabled");
      return;
    }
    if (outcome.kind === "ticket" && outcome.userId !== connection.account) {
      // The browser's session now belongs to someone else: never connect it for this account.
      outcome = { kind: "session-ended" };
    }
    if (outcome.kind !== "ticket") {
      this.connection = null;
      if (outcome.kind === "session-ended") this.onSessionEnded();
      this.scheduleRetry();
      return;
    }

    let ticket: string | null = outcome.ticket;
    const socket = this.createSocket(url);
    connection.socket = socket;
    connection.readyTimer = this.setTimer(() => {
      connection.readyTimer = null;
      if (connection === this.connection && connection.liveSince === null) {
        this.dropConnection(connection);
        this.scheduleRetry();
      }
    }, READY_TIMEOUT_MS);
    socket.onopen = () => {
      if (connection !== this.connection || ticket === null) return;
      socket.send(authenticateFrame(ticket));
      ticket = null;
    };
    socket.onmessage = (event) => this.frameReceived(connection, event.data);
    socket.onclose = (event) => this.closed(connection, event.code);
    // A close event always follows an error.
    socket.onerror = () => {};
  }

  private frameReceived(connection: Connection, data: unknown): void {
    if (connection !== this.connection) return;
    const frame = parseServerFrame(data);
    if (!frame) return;
    if (frame.kind === "ready") {
      if (connection.liveSince !== null) return;
      this.clearTimerOf(connection);
      connection.liveSince = this.now();
      this.everLive = true;
      this.setState("live", { advance: true });
      return;
    }
    if (connection.liveSince === null) return;
    for (const listener of [...(this.eventListeners.get(frame.event.type) ?? [])]) {
      try {
        listener(frame.event);
      } catch {
        // One consumer's failure never affects the connection or other consumers.
      }
    }
  }

  private closed(connection: Connection, code: number): void {
    if (connection !== this.connection) return;
    this.dropConnection(connection, { close: false });
    if (connection.liveSince !== null && this.now() - connection.liveSince >= STABLE_CONNECTION_MS) {
      this.failures = 0;
    }
    if (code === REALTIME_CLOSE.reconnect) {
      this.failures = 0;
      this.scheduleRetry(Math.round(this.random() * LIFETIME_RECONNECT_SPREAD_MS));
      return;
    }
    if (code === REALTIME_CLOSE.sessionRevoked) this.onSessionEnded();
    this.scheduleRetry();
  }

  private scheduleRetry(delay?: number): void {
    this.clearRetry();
    if (!this.online) return this.setState("offline");
    if (!this.visible) return this.setState("idle");
    const wait = delay ?? backoffDelay(this.failures, this.random);
    if (delay === undefined) this.failures += 1;
    this.setState(this.pendingState());
    this.retryTimer = this.setTimer(() => {
      this.retryTimer = null;
      if (!this.connection) this.evaluate();
    }, wait);
  }

  private dropConnection(connection: Connection, { close = true } = {}): void {
    if (connection === this.connection) this.connection = null;
    connection.abort.abort();
    this.clearTimerOf(connection);
    const socket = connection.socket;
    if (!socket) return;
    socket.onopen = null;
    socket.onmessage = null;
    socket.onclose = null;
    socket.onerror = null;
    if (close) {
      try {
        socket.close(1000);
      } catch {
        // Already closed.
      }
    }
  }

  private teardown(): void {
    this.clearRetry();
    this.clearHidden();
    if (this.connection) this.dropConnection(this.connection);
  }

  private clearTimerOf(connection: Connection): void {
    if (connection.readyTimer !== null) this.clearTimer(connection.readyTimer);
    connection.readyTimer = null;
  }

  private clearRetry(): void {
    if (this.retryTimer !== null) this.clearTimer(this.retryTimer);
    this.retryTimer = null;
  }

  private clearHidden(): void {
    if (this.hiddenTimer !== null) this.clearTimer(this.hiddenTimer);
    this.hiddenTimer = null;
  }
}
