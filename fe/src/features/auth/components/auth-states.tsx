import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function AuthSessionLoading({ label = "Checking your session…" }: { label?: string }) {
  return (
    <div aria-busy="true" aria-label={label}>
      <Skeleton className="h-9 w-3/4" />
      <Skeleton className="mt-4 h-5 w-full" />
      <Skeleton className="mt-8 h-11 w-full" />
      <p className="sr-only">{label}</p>
    </div>
  );
}

export function AuthFailure({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div role="alert" className="border-y border-border py-6">
      <h1 className="font-heading text-2xl font-bold text-ink">Session verification unavailable</h1>
      <p className="mt-3 text-sm leading-6 text-muted">{message}</p>
      <Button className="mt-5" variant="secondary" onClick={onRetry}>Retry</Button>
    </div>
  );
}

export function FormError({ id, message }: { id: string; message: string | null }) {
  return (
    <div id={id} aria-live="polite" className="min-h-6 text-sm leading-6 text-danger">
      {message}
    </div>
  );
}
