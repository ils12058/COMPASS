"use client";

import { Button } from "@/components/ui/button";

export function CanonicalPagination({
  page,
  hasNext,
  onPageChange,
  label = "Results pages",
}: {
  page: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
  label?: string;
}) {
  return (
    <nav aria-label={label} className="flex items-center justify-between gap-3 border-t border-border py-4">
      <Button
        variant="secondary"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </Button>
      <span className="text-sm text-muted">Page {page}</span>
      <Button
        variant="secondary"
        disabled={!hasNext}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </Button>
    </nav>
  );
}
