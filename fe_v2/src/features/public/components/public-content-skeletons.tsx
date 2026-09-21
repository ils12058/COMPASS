import { Skeleton } from "@/components/ui/skeleton";

export function AnnouncementCardSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <article className="landing-paper-sheet h-full" data-tone="plain" aria-hidden="true">
      <Skeleton className="mb-3 h-4 w-28" />
      <Skeleton className={compact ? "h-6 w-4/5" : "h-7 w-3/4"} />
      <div className="mt-4 space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-[88%]" />
        <Skeleton className="h-4 w-[64%]" />
      </div>
      <Skeleton className="mt-5 h-4 w-36" />
    </article>
  );
}

export function ResourceCardSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <article className="landing-paper-sheet h-full" data-tone="plain" aria-hidden="true">
      <Skeleton className="mb-3 h-4 w-40" />
      <Skeleton className={compact ? "h-6 w-4/5" : "h-7 w-3/4"} />
      <Skeleton className="mt-3 h-4 w-32" />
      <Skeleton className="mt-5 h-4 w-32" />
    </article>
  );
}

export function AnnouncementDetailSkeleton() {
  return (
    <article className="landing-paper-sheet mt-6" data-tone="plain" aria-hidden="true">
      <header className="border-b border-[var(--compass-border)] pb-5">
        <Skeleton className="mb-3 h-4 w-48" />
        <Skeleton className="h-9 w-[78%] md:h-10" />
      </header>
      <div className="mt-6 max-w-3xl space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-[94%]" />
        <Skeleton className="h-4 w-[82%]" />
        <Skeleton className="h-4 w-[68%]" />
      </div>
    </article>
  );
}

export function ResourceDetailSkeleton() {
  return (
    <article className="landing-paper-sheet mt-6" data-tone="plain" aria-hidden="true">
      <header className="border-b border-[var(--compass-border)] pb-5">
        <Skeleton className="mb-3 h-4 w-56" />
        <Skeleton className="h-9 w-[78%] md:h-10" />
      </header>
      <div className="mt-6 max-w-3xl space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-[94%]" />
        <Skeleton className="h-4 w-[82%]" />
        <Skeleton className="h-4 w-[68%]" />
      </div>
      <Skeleton className="mt-8 h-9 w-36" />
    </article>
  );
}
