"use client";

import { createContext, type ReactNode, useContext, useMemo } from "react";

import type { CurrentSessionResponse } from "@/lib/api/generated/model";

type CurrentAuthValue = {
  session: CurrentSessionResponse;
  capabilities: ReadonlySet<string>;
  hasCapability: (code: string) => boolean;
};

const CurrentAuthContext = createContext<CurrentAuthValue | null>(null);

export function CurrentAuthProvider({
  session,
  children,
}: {
  session: CurrentSessionResponse;
  children: ReactNode;
}) {
  const value = useMemo<CurrentAuthValue>(() => {
    const capabilities = new Set(session.user.capabilities);

    return {
      session,
      capabilities,
      hasCapability: (code) => capabilities.has(code),
    };
  }, [session]);

  return (
    <CurrentAuthContext.Provider value={value}>
      {children}
    </CurrentAuthContext.Provider>
  );
}

export function useCurrentAuth(): CurrentAuthValue {
  const value = useContext(CurrentAuthContext);
  if (!value) {
    throw new Error("useCurrentAuth must be used inside the authenticated portal.");
  }
  return value;
}
