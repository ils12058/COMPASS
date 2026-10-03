import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";

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
    <Notice
      role="status"
      aria-live="polite"
      tone="warning"
      className="my-3"
      action={
        <Button type="button" variant="secondary" disabled={retrying} onClick={onRetry}>
          {retrying ? "Retrying…" : "Retry"}
        </Button>
      }
    >
      {message}
    </Notice>
  );
}
