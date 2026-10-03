import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils/cn";

// Initial loading for a list or table of records. Inside a results Panel the panel draws the frame;
// a route-level fallback has no panel yet, so it passes `framed` to draw one.
export function RowsSkeleton({
  label,
  rows = 3,
  framed = false,
  className,
}: {
  label: string;
  rows?: number;
  framed?: boolean;
  className?: string;
}) {
  return (
    <LoadingRegion
      label={label}
      className={cn(
        "divide-y divide-border",
        framed && "rounded-sm border border-brand-line bg-surface-raised",
        className,
      )}
    >
      {Array.from({ length: rows }).map((_, row) => (
        <div key={row} className="grid gap-2 px-4 py-4 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-6 sm:px-5">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-4 w-full max-w-md" />
        </div>
      ))}
    </LoadingRegion>
  );
}
