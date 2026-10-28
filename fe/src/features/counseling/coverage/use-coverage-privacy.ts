"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { subscribeSessionRevalidation } from "@/lib/auth/session-revalidation";
import { CoverageGeneration } from "./coverage-safety";
// Short-lived per-detail barrier. TanStack owns fetching/cancellation; these events only clear.
export function useCoveragePrivacy(accountId: string, grantId: string) {
    const client = useQueryClient();
    const [barrier] = useState(() => new CoverageGeneration());
    const prefix = useMemo(() => ["protected-case-coverage", accountId, grantId], [accountId, grantId]);
    const [blocked, setBlocked] = useState(false);
    const [generation, setGeneration] = useState(0);
    const clear = useCallback(() => { barrier.invalidate(); setBlocked(true); setGeneration(barrier.current()); void client.cancelQueries({ queryKey: prefix }); client.removeQueries({ queryKey: prefix }); }, [barrier, client, prefix]);
    const resume = useCallback(() => { barrier.invalidate(); setGeneration(barrier.current()); setBlocked(false); }, [barrier]);
    useEffect(() => {
        const hidden = () => { if (document.visibilityState !== "visible")
            clear(); };
        window.addEventListener("offline", clear);
        document.addEventListener("visibilitychange", hidden);
        const unsubscribe = subscribeSessionRevalidation(clear);
        const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("compass-case-coverage") : null;
        if (channel)
            channel.onmessage = e => { if (e.data?.grant_id === grantId)
                clear(); };
        return () => { barrier.invalidate(); void client.cancelQueries({ queryKey: prefix }); client.removeQueries({ queryKey: prefix }); window.removeEventListener("offline", clear); document.removeEventListener("visibilitychange", hidden); unsubscribe(); channel?.close(); };
    }, [clear, barrier, client, prefix, grantId]);
    return { blocked, generation, barrier, prefix, clear, resume };
}
export function broadcastCoverageChange(grantId: string) { if (typeof BroadcastChannel !== "undefined") {
    const channel = new BroadcastChannel("compass-case-coverage");
    channel.postMessage({ grant_id: grantId });
    channel.close();
} }
