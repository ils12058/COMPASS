"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { CompassApiError } from "@/lib/api/errors";
import { getAuthGetSessionQueryKey, useAuthGetSession } from "@/lib/api/generated/auth/auth";

export type ReaderAudience = "pending" | "account" | "public";

// Signed-in readers use the account endpoints, which return public content
// plus content for the reader's audience. Audience rules stay on the backend;
// this only chooses which reader endpoint applies.
export function useReaderAudience(): ReaderAudience {
  const session = useAuthGetSession({ query: { retry: false, staleTime: 60_000 } });
  if (session.isPending) return "pending";
  return session.isSuccess && session.data.data.authenticated ? "account" : "public";
}

export function isSignedOutError(error: unknown): boolean {
  return error instanceof CompassApiError && error.status === 401;
}

// When an account request finds the session has ended, readers fall back to
// public content and the shared session state is checked again.
export function useSessionRecheck(signedOut: boolean) {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (signedOut) void queryClient.invalidateQueries({ queryKey: getAuthGetSessionQueryKey() });
  }, [queryClient, signedOut]);
}
