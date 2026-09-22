"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type AuthFlowState = {
  challengeExpiresAt: string | null;
  mandatorySetup: boolean;
  mfaMethods: string[];
  nextPath: string;
};

type AuthFlowValue = AuthFlowState & {
  beginMandatorySetup: (nextPath: string) => void;
  beginMfa: (methods: string[], challengeExpiresAt: string | null, nextPath: string) => void;
  clearFlow: () => void;
};

const initialState: AuthFlowState = {
  challengeExpiresAt: null,
  mandatorySetup: false,
  mfaMethods: [],
  nextPath: "/portal",
};

const AuthFlowContext = createContext<AuthFlowValue | null>(null);

export function AuthFlowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(initialState);

  const beginMfa = useCallback(
    (mfaMethods: string[], challengeExpiresAt: string | null, nextPath: string) => {
      setState({ challengeExpiresAt, mandatorySetup: false, mfaMethods, nextPath });
    },
    [],
  );

  const beginMandatorySetup = useCallback((nextPath: string) => {
    setState({ challengeExpiresAt: null, mandatorySetup: true, mfaMethods: [], nextPath });
  }, []);

  const clearFlow = useCallback(() => setState(initialState), []);

  const value = useMemo(
    () => ({ ...state, beginMandatorySetup, beginMfa, clearFlow }),
    [beginMandatorySetup, beginMfa, clearFlow, state],
  );

  return <AuthFlowContext.Provider value={value}>{children}</AuthFlowContext.Provider>;
}

export function useAuthFlow(): AuthFlowValue {
  const context = useContext(AuthFlowContext);
  if (!context) throw new Error("useAuthFlow must be used inside AuthFlowProvider.");
  return context;
}
