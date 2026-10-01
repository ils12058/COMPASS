export type SessionRevalidationReason = "session" | "authority";
type Listener = (reason: SessionRevalidationReason) => void;

const listeners = new Set<Listener>();

export function requestSessionRevalidation(reason: SessionRevalidationReason) {
  for (const listener of listeners) listener(reason);
}

export function subscribeSessionRevalidation(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
