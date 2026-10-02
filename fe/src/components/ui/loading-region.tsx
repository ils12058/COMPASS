import type { ReactNode } from "react";

// Initial loading for a region whose content has not arrived yet. The region is marked busy and
// gives one polite status; its Skeleton shapes stay hidden from assistive technology. A background
// refresh keeps confirmed content visible instead of returning here.
export function LoadingRegion({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div aria-busy="true" className={className}>
      <p role="status" className="sr-only">
        {label}
      </p>
      {children}
    </div>
  );
}
