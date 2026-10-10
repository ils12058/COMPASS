"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { CurrentSessionResponse } from "@/lib/api/generated/model";

const PortalSessionContext = createContext<CurrentSessionResponse | null>(null);

export function PortalSessionProvider({
  children,
  value,
}: {
  children: ReactNode;
  value: CurrentSessionResponse;
}) {
  return <PortalSessionContext.Provider value={value}>{children}</PortalSessionContext.Provider>;
}

export function usePortalSession(): CurrentSessionResponse {
  const context = useContext(PortalSessionContext);
  if (!context) throw new Error("usePortalSession must be used inside PortalSessionProvider.");
  return context;
}
