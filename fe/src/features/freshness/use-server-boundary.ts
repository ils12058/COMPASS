"use client";

import { useEffect, useRef } from "react";

const MAX_TIMEOUT_MS = 2_147_483_647;

export function boundaryDelay(boundary: string | null | undefined, serverDate?: string | null, receivedAt?: number): number | null {
  if (!boundary) return null;
  const end = Date.parse(boundary);
  const reference = serverDate ? Date.parse(serverDate) : Number.NaN;
  if (!Number.isFinite(end)) return null;
  const now = Number.isFinite(reference)
    ? reference + Math.max(0, Date.now() - (receivedAt ?? Date.now()))
    : Date.now();
  return Math.max(0, end - now);
}

export function useServerBoundary({
  boundary,
  serverDate,
  receivedAt,
  onBoundary,
}: {
  boundary: string | null | undefined;
  serverDate?: string | null;
  receivedAt?: number;
  onBoundary: () => void;
}) {
  const callback = useRef(onBoundary);
  useEffect(() => {
    callback.current = onBoundary;
  }, [onBoundary]);

  useEffect(() => {
    const delay = boundaryDelay(boundary, serverDate, receivedAt);
    if (delay === null) return;
    const deadline = performance.now() + delay;
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;

    const arm = () => {
      if (cancelled) return;
      const remaining = deadline - performance.now();
      if (remaining <= 0) {
        callback.current();
        return;
      }
      timer = setTimeout(arm, Math.min(remaining, MAX_TIMEOUT_MS));
    };
    arm();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [boundary, serverDate, receivedAt]);
}
