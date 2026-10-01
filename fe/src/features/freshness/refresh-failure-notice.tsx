import { Button } from "@/components/ui/button";

export function RefreshFailureNotice({
  message = "Latest information could not be refreshed. Showing the last confirmed result.",
  onRetry,
  retrying = false,
}: {
  message?: string;
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div role="status" aria-live="polite" className="my-3 flex flex-wrap items-center gap-3 border-y border-warning/40 py-3 text-sm text-warning">
      <p>{message}</p>
      <Button type="button" variant="secondary" disabled={retrying} onClick={onRetry}>
        {retrying ? "Retrying…" : "Retry"}
      </Button>
    </div>
  );
}
