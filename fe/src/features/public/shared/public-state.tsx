import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function PublicListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" className="divide-y divide-border border-y border-border">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="py-5">
          <Skeleton className="h-3 w-28 rounded-sm" />
          <Skeleton className="mt-3 h-5 w-3/4 rounded-sm" />
        </div>
      ))}
      <p className="sr-only">Loading…</p>
    </div>
  );
}

export function PublicAnnouncementSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" className="divide-y divide-border border-y border-border">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-4 py-5 sm:grid-cols-[4rem_minmax(0,1fr)] sm:gap-x-6">
          <Skeleton className="h-[4.5rem] rounded-md" />
          <div>
            <Skeleton className="h-5 w-3/4 rounded-sm" />
            <Skeleton className="mt-3 h-3 w-full rounded-sm" />
            <Skeleton className="mt-2 h-3 w-2/3 rounded-sm" />
          </div>
        </div>
      ))}
      <p className="sr-only">Loading…</p>
    </div>
  );
}

export function PublicTileSkeleton({ tiles = 3 }: { tiles?: number }) {
  return (
    <div aria-busy="true" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: tiles }).map((_, index) => (
        <div key={index} className="rounded-md border border-border bg-surface-raised p-5">
          <Skeleton className="h-3 w-32 rounded-sm" />
          <Skeleton className="mt-4 h-5 w-4/5 rounded-sm" />
          <Skeleton className="mt-3 h-3 w-full rounded-sm" />
          <Skeleton className="mt-2 h-3 w-5/6 rounded-sm" />
          <Skeleton className="mt-6 h-3 w-24 rounded-sm" />
        </div>
      ))}
      <p className="sr-only">Loading…</p>
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
