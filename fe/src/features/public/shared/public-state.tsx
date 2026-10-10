import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Notice } from "@/components/ui/notice";
import { PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";

// A reading surface still loading: a title and a few lines of text.
export function PublicListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <LoadingRegion label="Loading…" className="rounded-sm border border-brand-line bg-surface-raised px-5 py-6 sm:px-8">
      <Skeleton className="h-3 w-28 rounded-sm" />
      <Skeleton className="mt-4 h-8 w-3/4 rounded-sm" />
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="mt-4 h-3 w-full rounded-sm" />
      ))}
    </LoadingRegion>
  );
}

// Rows inside an announcements or resources panel.
export function PublicRowsSkeleton({ rows = 3, label = "Loading…" }: { rows?: number; label?: string }) {
  return (
    <LoadingRegion label={label} className="divide-y divide-border">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-4 px-4 py-4 sm:px-5">
          <Skeleton className="h-16 rounded-sm" />
          <div>
            <Skeleton className="h-5 w-3/4 rounded-sm" />
            <Skeleton className="mt-3 h-3 w-full rounded-sm" />
            <Skeleton className="mt-2 h-3 w-2/3 rounded-sm" />
          </div>
        </div>
      ))}
    </LoadingRegion>
  );
}

// A failure inside a panel.
export function PublicSectionError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <PanelMessage
      role="alert"
      action={
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      }
    >
      {message}
    </PanelMessage>
  );
}

// A failure that stands on the page by itself, such as a detail page that could not load.
export function PublicPageError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Notice
      role="alert"
      action={
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      }
    >
      {message}
    </Notice>
  );
}
