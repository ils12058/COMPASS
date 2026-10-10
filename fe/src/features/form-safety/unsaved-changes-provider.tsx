"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

type DirtyRegistration = {
  message: string;
  pathname: string;
};

type UnsavedNavigationContextValue = {
  hasUnsavedChanges: boolean;
  registerGuard: (id: string, registration: DirtyRegistration) => void;
  unregisterGuard: (id: string) => void;
  confirmNavigation: (destinationPathname?: string | null) => boolean;
  confirmDiscard: () => boolean;
};

const UnsavedNavigationContext =
  createContext<UnsavedNavigationContextValue | null>(null);

const HISTORY_STATE_KEY = "__compassUnsavedNavigation";

type CompassHistoryMarker = {
  session: string;
  index: number;
};

type HistoryStateRecord = Record<string, unknown>;

type NavigationEntryLike = {
  index: number;
};

type NavigationDestinationLike = {
  index: number;
  url: string | null;
};

type NavigationEventLike = Event & {
  navigationType: "push" | "reload" | "replace" | "traverse";
  destination: NavigationDestinationLike;
};

type NavigationLike = EventTarget & {
  currentEntry: NavigationEntryLike | null;
  addEventListener(
    type: "navigate",
    listener: (event: NavigationEventLike) => void,
  ): void;
  removeEventListener(
    type: "navigate",
    listener: (event: NavigationEventLike) => void,
  ): void;
};

function historyRecord(state: unknown): HistoryStateRecord | null {
  return state !== null && typeof state === "object" && !Array.isArray(state)
    ? (state as HistoryStateRecord)
    : null;
}

function readHistoryMarker(state: unknown): CompassHistoryMarker | null {
  const record = historyRecord(state);
  const value = record?.[HISTORY_STATE_KEY];
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const marker = value as Record<string, unknown>;
  return typeof marker.session === "string" && typeof marker.index === "number"
    ? { session: marker.session, index: marker.index }
    : null;
}

function withHistoryMarker(
  state: unknown,
  session: string,
  index: number,
): unknown {
  const record = historyRecord(state);
  if (!record) return state;
  return {
    ...record,
    [HISTORY_STATE_KEY]: { session, index } satisfies CompassHistoryMarker,
  };
}

function firstDirtyMessage(
  registrations: Map<string, DirtyRegistration>,
): string {
  const first = [...registrations.entries()].sort(([left], [right]) =>
    left.localeCompare(right),
  )[0];
  return first?.[1].message ?? "Discard your unsaved changes?";
}

function destinationKeepsAllEditors(
  registrations: Map<string, DirtyRegistration>,
  destinationPathname: string | null | undefined,
): boolean {
  if (!destinationPathname) return false;
  return [...registrations.values()].every(
    (registration) => registration.pathname === destinationPathname,
  );
}

export function UnsavedChangesProvider({
  children,
}: {
  children: ReactNode;
}) {
  const generatedSessionId = useId();
  const historySessionRef = useRef(generatedSessionId);
  const registrationsRef = useRef(new Map<string, DirtyRegistration>());
  const currentHistoryIndexRef = useRef(0);
  const pendingTraversalDeltaRef = useRef<number | null>(null);
  const restoringHistoryRef = useRef<number | null>(null);
  // A traversal already confirmed before its popstate, so popstate does not ask again.
  const confirmedTraversalRef = useRef(false);
  const [dirtyCount, setDirtyCount] = useState(0);
  const hasUnsavedChanges = dirtyCount > 0;

  const registerGuard = useCallback(
    (id: string, registration: DirtyRegistration) => {
      registrationsRef.current.set(id, registration);
      setDirtyCount(registrationsRef.current.size);
    },
    [],
  );

  const unregisterGuard = useCallback((id: string) => {
    registrationsRef.current.delete(id);
    setDirtyCount(registrationsRef.current.size);
  }, []);

  const confirmNavigation = useCallback(
    (destinationPathname?: string | null) => {
      const registrations = registrationsRef.current;
      if (registrations.size === 0) return true;
      if (destinationKeepsAllEditors(registrations, destinationPathname)) {
        return true;
      }
      return window.confirm(firstDirtyMessage(registrations));
    },
    [],
  );

  const confirmDiscard = useCallback(
    () => confirmNavigation(null),
    [confirmNavigation],
  );

  // App Router exposes no public beforePopState hook. Keep only a COMPASS-owned
  // monotonic index beside Next's existing history state so a cancelled traversal
  // can reverse the exact delta without creating duplicate history entries.
  useEffect(() => {
    const browserHistory = window.history;
    const originalPushState = browserHistory.pushState;
    const originalReplaceState = browserHistory.replaceState;

    const existing = readHistoryMarker(browserHistory.state);
    if (existing) {
      historySessionRef.current = existing.session;
    }
    currentHistoryIndexRef.current = existing?.index ?? 0;
    originalReplaceState.call(
      browserHistory,
      withHistoryMarker(
        browserHistory.state,
        historySessionRef.current,
        currentHistoryIndexRef.current,
      ),
      "",
      window.location.href,
    );

    const pushState: History["pushState"] = function (
      data,
      unused,
      url,
    ) {
      const nextIndex = currentHistoryIndexRef.current + 1;
      originalPushState.call(
        browserHistory,
        withHistoryMarker(data, historySessionRef.current, nextIndex),
        unused,
        url,
      );
      currentHistoryIndexRef.current = nextIndex;
    };

    const replaceState: History["replaceState"] = function (
      data,
      unused,
      url,
    ) {
      originalReplaceState.call(
        browserHistory,
        withHistoryMarker(
          data,
          historySessionRef.current,
          currentHistoryIndexRef.current,
        ),
        unused,
        url,
      );
    };

    browserHistory.pushState = pushState;
    browserHistory.replaceState = replaceState;

    return () => {
      if (browserHistory.pushState === pushState) {
        browserHistory.pushState = originalPushState;
      }
      if (browserHistory.replaceState === replaceState) {
        browserHistory.replaceState = originalReplaceState;
      }
    };
  }, []);

  useEffect(() => {
    const navigation = (
      window as Window & { navigation?: NavigationLike }
    ).navigation;
    if (!navigation) return;

    const noteTraversal = (event: NavigationEventLike) => {
      if (
        event.navigationType !== "traverse" ||
        restoringHistoryRef.current !== null
      ) {
        return;
      }
      confirmedTraversalRef.current = false;
      const currentIndex = navigation.currentEntry?.index;
      if (typeof currentIndex !== "number") return;
      pendingTraversalDeltaRef.current =
        event.destination.index - currentIndex;

      // Next.js handles Back and Forward in its own popstate listener, registered before this
      // provider's, so the popstate question below can come after the editor has already gone.
      // Where the browser lets this traversal be cancelled, ask now, before popstate.
      const registrations = registrationsRef.current;
      if (registrations.size === 0 || !event.cancelable) return;
      const destination = event.destination.url
        ? new URL(event.destination.url).pathname
        : null;
      if (
        destinationKeepsAllEditors(registrations, destination) ||
        window.confirm(firstDirtyMessage(registrations))
      ) {
        confirmedTraversalRef.current = true;
        return;
      }
      pendingTraversalDeltaRef.current = null;
      event.preventDefault();
    };

    navigation.addEventListener("navigate", noteTraversal);
    return () => navigation.removeEventListener("navigate", noteTraversal);
  }, []);

  useEffect(() => {
    if (!hasUnsavedChanges) return;

    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    const handlePopState = (event: PopStateEvent) => {
      const restoringIndex = restoringHistoryRef.current;
      const marker = readHistoryMarker(event.state);
      const targetMarker =
        marker?.session === historySessionRef.current ? marker : null;

      if (restoringIndex !== null) {
        event.stopImmediatePropagation();
        currentHistoryIndexRef.current =
          targetMarker?.index ?? restoringIndex;
        restoringHistoryRef.current = null;
        pendingTraversalDeltaRef.current = null;
        window.history.replaceState(
          window.history.state,
          "",
          window.location.href,
        );
        return;
      }

      const previousIndex = currentHistoryIndexRef.current;
      const recordedDelta =
        targetMarker !== null
          ? targetMarker.index - previousIndex
          : pendingTraversalDeltaRef.current;
      pendingTraversalDeltaRef.current = null;
      const alreadyConfirmed = confirmedTraversalRef.current;
      confirmedTraversalRef.current = false;

      if (
        alreadyConfirmed ||
        destinationKeepsAllEditors(
          registrationsRef.current,
          window.location.pathname,
        ) ||
        window.confirm(firstDirtyMessage(registrationsRef.current))
      ) {
        if (targetMarker) {
          currentHistoryIndexRef.current = targetMarker.index;
        } else if (recordedDelta !== null) {
          currentHistoryIndexRef.current = previousIndex + recordedDelta;
        }
        window.history.replaceState(
          window.history.state,
          "",
          window.location.href,
        );
        return;
      }

      event.stopImmediatePropagation();
      restoringHistoryRef.current = previousIndex;

      if (recordedDelta !== null && recordedDelta !== 0) {
        window.history.go(-recordedDelta);
        return;
      }

      // An untagged entry predates this Portal provider. With no Navigation API
      // delta available, it can only be the older entry reached by Back.
      window.history.forward();
    };

    window.addEventListener("beforeunload", warnBeforeUnload);
    window.addEventListener("popstate", handlePopState, true);

    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      window.removeEventListener("popstate", handlePopState, true);
    };
  }, [hasUnsavedChanges]);

  const value = useMemo<UnsavedNavigationContextValue>(
    () => ({
      hasUnsavedChanges,
      registerGuard,
      unregisterGuard,
      confirmNavigation,
      confirmDiscard,
    }),
    [
      confirmDiscard,
      confirmNavigation,
      hasUnsavedChanges,
      registerGuard,
      unregisterGuard,
    ],
  );

  return (
    <UnsavedNavigationContext.Provider value={value}>
      {children}
    </UnsavedNavigationContext.Provider>
  );
}

export function useUnsavedNavigation(): UnsavedNavigationContextValue {
  const context = useContext(UnsavedNavigationContext);
  if (!context) {
    throw new Error(
      "useUnsavedNavigation must be used inside UnsavedChangesProvider.",
    );
  }
  return context;
}
