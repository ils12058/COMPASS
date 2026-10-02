"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

// Previous / Page N / Next over the canonical page and has_next facts; there is no total page
// count to show. A single page of results renders nothing, while an empty later page keeps the pager
// so the reader can go back. The feature owns what onPageChange does: its URL, filters, and router.
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
  // For example while the requested page is still loading.
  disabled?: boolean;
  className?: string;
}) {
  if (page <= 1 && !hasNext) return null;

  return (
    <nav
      aria-label={label}
      className={cn("flex items-center justify-between gap-3 border-t border-border py-4", className)}
    >
      <Button
        variant="secondary"
        disabled={disabled || page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </Button>
      <span aria-live="polite" className="text-sm text-muted">Page {page}</span>
      <Button
        variant="secondary"
        disabled={disabled || !hasNext}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </Button>
    </nav>
  );
}
