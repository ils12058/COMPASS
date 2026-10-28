"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

// The server supplies the current page and has_next, not a total page count. Keep the pager on an
// empty later page so the reader can go back. The feature owns the URL, filters and router.
export function CanonicalPagination({
  page,
  hasNext,
  onPageChange,
  label = "Results pages",
  disabled = false,
  className,
}: {
  page: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
}) {
  if (page <= 1 && !hasNext) return null;

  return (
    <nav aria-label={label} className={cn("@container border-t border-border py-3", className)}>
      <div className="flex flex-wrap items-center justify-end gap-2 @max-[14rem]:grid @max-[14rem]:grid-cols-2">
        <Button
          variant="secondary"
          aria-label="Previous"
          title="Previous page"
          className="min-h-11 min-w-0 gap-1 px-2 @max-[14rem]:row-start-2"
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft size={18} aria-hidden="true" />
          <span className="@max-[14rem]:sr-only">Previous</span>
        </Button>
        <span aria-live="polite" className="px-1 text-sm font-medium text-muted @max-[14rem]:col-span-2 @max-[14rem]:row-start-1 @max-[14rem]:text-center">Page {page}</span>
        <Button
          variant="secondary"
          aria-label="Next"
          title="Next page"
          className="min-h-11 min-w-0 gap-1 px-2 @max-[14rem]:row-start-2"
          disabled={disabled || !hasNext}
          onClick={() => onPageChange(page + 1)}
        >
          <span className="@max-[14rem]:sr-only">Next</span>
          <ChevronRight size={18} aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
