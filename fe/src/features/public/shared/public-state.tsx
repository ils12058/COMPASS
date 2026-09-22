import { Button } from "@/components/ui/button";

export function PublicListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading content" className="divide-y divide-border border-y border-border">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="py-5">
          <div className="h-3 w-28 animate-pulse rounded-sm bg-surface-muted" />
          <div className="mt-3 h-5 w-3/4 animate-pulse rounded-sm bg-surface-muted" />
        </div>
      ))}
    </div>
  );
}

export function PublicSectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="border-y border-border py-6">
      <p className="text-sm leading-6 text-muted">{message}</p>
      <Button className="mt-3" variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
