"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { stepUpRequirement, type StepUpRequirement } from "@/features/account/security/step-up";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { getAuthGetSessionQueryOptions } from "@/lib/api/generated/auth/auth";

const CONTINUATION_LIFETIME_MS = 5 * 60 * 1000;
const EXPIRED_MESSAGE = "This action expired. Review and confirm it again.";
const SESSION_CHANGED_MESSAGE = "Your sign-in changed. Review the action and try again.";
const SESSION_UNAVAILABLE_MESSAGE = "Your sign-in could not be confirmed. Review the action and try again.";

type PendingContinuation = {
  actorSession: string;
  expiresAt: number;
  operation: () => Promise<unknown>;
  resolve: (value: unknown | undefined) => void;
  onFailure: (error: unknown) => void;
  timer: ReturnType<typeof setTimeout>;
};

type RunOptions = {
  onStepUpRequired?: () => void;
  onFailure?: (error: unknown) => void;
};

function safelyCall(callback: () => void) {
  try {
    callback();
  } catch {
    // A feedback callback must not leave a retained action unresolved.
  }
}

/**
 * Retains only the already-confirmed operation in memory after the backend's exact
 * recent-MFA precondition refusal. It is bound to the current account and session,
 * expires quickly, and is consumed before its single continuation attempt.
 */
export function useStepUpContinuation() {
  const queryClient = useQueryClient();
  const { user, session } = usePortalSession();
  const actorSession = `${user?.id ?? "unknown-account"}:${session?.id ?? "unknown-session"}`;
  const actorSessionRef = useRef(actorSession);

  const [open, setOpenState] = useState(false);
  const [requirement, setRequirement] = useState<StepUpRequirement>("verify");
  const [isContinuing, setIsContinuing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const pendingRef = useRef<PendingContinuation | null>(null);
  const activeContinuationRef = useRef<PendingContinuation | null>(null);
  const mountedRef = useRef(false);
  const actionRunningRef = useRef(false);

  const clearPending = useCallback((message?: string) => {
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = null;
    clearTimeout(pending.timer);
    pending.resolve(undefined);
    if (message) setNotice(message);
  }, []);

  useEffect(() => {
    actorSessionRef.current = actorSession;
    const pending = pendingRef.current;
    if (pending && pending.actorSession !== actorSession) {
      clearPending(SESSION_CHANGED_MESSAGE);
      setOpenState(false);
    }
    const active = activeContinuationRef.current;
    if (active && active.actorSession !== actorSession) {
      activeContinuationRef.current = null;
      clearTimeout(active.timer);
      active.resolve(undefined);
      setNotice(SESSION_CHANGED_MESSAGE);
    }
  }, [actorSession, clearPending]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      const pending = pendingRef.current;
      const active = activeContinuationRef.current;
      pendingRef.current = null;
      activeContinuationRef.current = null;
      if (pending) {
        clearTimeout(pending.timer);
        pending.resolve(undefined);
      }
      if (active && active !== pending) {
        clearTimeout(active.timer);
        active.resolve(undefined);
      }
    };
  }, []);

  const setOpen = useCallback((next: boolean) => {
    setOpenState(next);
    if (!next) clearPending();
  }, [clearPending]);

  const run = useCallback(async <T,>(
    operation: () => Promise<T>,
    options: RunOptions,
  ): Promise<T | undefined> => {
    if (actionRunningRef.current) return undefined;
    actionRunningRef.current = true;
    setNotice(null);
    try {
      try {
        return await operation();
      } catch (caught) {
        const nextRequirement = stepUpRequirement(caught);
        if (!nextRequirement) {
          safelyCall(() => options.onFailure?.(caught));
          return undefined;
        }

        safelyCall(() => options.onStepUpRequired?.());
        setRequirement(nextRequirement);
        setOpenState(true);

        // Setup is a separate security workflow. Never retain an action across setup.
        if (nextRequirement === "setup") return undefined;

        return await new Promise<T | undefined>((resolve) => {
          const expiresAt = Date.now() + CONTINUATION_LIFETIME_MS;
          const pending: PendingContinuation = {
            actorSession: actorSessionRef.current,
            expiresAt,
            operation: () => operation(),
            resolve: (value) => resolve(value as T | undefined),
            onFailure: (error) => safelyCall(() => options.onFailure?.(error)),
            timer: setTimeout(() => {
              if (pendingRef.current !== pending) return;
              pendingRef.current = null;
              setOpenState(false);
              setNotice(EXPIRED_MESSAGE);
              pending.resolve(undefined);
            }, CONTINUATION_LIFETIME_MS),
          };
          pendingRef.current = pending;
        });
      }
    } finally {
      actionRunningRef.current = false;
    }
  }, []);

  const continueAfterVerification = useCallback(async () => {
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = null;
    activeContinuationRef.current = pending;
    clearTimeout(pending.timer);
    setIsContinuing(true);

    const rejectStale = (message: string) => {
      if (activeContinuationRef.current === pending) activeContinuationRef.current = null;
      if (mountedRef.current) setNotice(message);
      pending.resolve(undefined);
    };

    try {
      if (Date.now() >= pending.expiresAt) {
        rejectStale(EXPIRED_MESSAGE);
        return;
      }
      if (actorSessionRef.current !== pending.actorSession) {
        rejectStale(SESSION_CHANGED_MESSAGE);
        return;
      }

      let currentSession;
      try {
        currentSession = await queryClient.fetchQuery(
          getAuthGetSessionQueryOptions({ query: { retry: false, staleTime: 0 } }),
        );
      } catch {
        rejectStale(SESSION_UNAVAILABLE_MESSAGE);
        return;
      }

      const current = currentSession.data;
      const currentIdentity = current.authenticated
        ? `${current.user.id}:${current.session.id}`
        : null;
      if (currentIdentity !== pending.actorSession || actorSessionRef.current !== pending.actorSession) {
        rejectStale(SESSION_CHANGED_MESSAGE);
        return;
      }
      if (Date.now() >= pending.expiresAt) {
        rejectStale(EXPIRED_MESSAGE);
        return;
      }
      if (!mountedRef.current || activeContinuationRef.current !== pending) {
        pending.resolve(undefined);
        return;
      }

      try {
        pending.resolve(await pending.operation());
      } catch (caught) {
        // A second step-up refusal or any other error is terminal for this continuation.
        if (mountedRef.current && activeContinuationRef.current === pending) pending.onFailure(caught);
        pending.resolve(undefined);
      }
    } finally {
      if (activeContinuationRef.current === pending) activeContinuationRef.current = null;
      if (mountedRef.current) setIsContinuing(false);
    }
  }, [queryClient]);

  return {
    open,
    setOpen,
    requirement,
    isContinuing,
    notice,
    setNotice,
    run,
    continueAfterVerification,
  };
}
