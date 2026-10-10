"use client";

import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect } from "react";

/** Reconcile mounted projections when the window regains focus; Query owns reads and deduping. */
export function useProjectionFocus(queryKey: QueryKey, enabled: boolean) {
  const client = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    const refresh = () => {
      if (document.visibilityState === "visible" && navigator.onLine) {
        void client.invalidateQueries({ queryKey });
      }
    };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [client, enabled, queryKey]);
}
