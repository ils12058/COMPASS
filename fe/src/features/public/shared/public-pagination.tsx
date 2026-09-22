import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

type PublicPaginationProps = {
  buildHref: (page: number) => string;
  hasNext: boolean;
  page: number;
};

const linkClassName =
  "inline-flex min-h-10 items-center gap-1 rounded-md border border-border-strong bg-surface-raised px-3 text-sm font-semibold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function PublicPagination({ buildHref, hasNext, page }: PublicPaginationProps) {
  if (page <= 1 && !hasNext) return null;

  return (
    <nav aria-label="Pagination" className="mt-8 flex items-center justify-between gap-4 border-t border-border pt-5">
      {page > 1 ? (
        <Link href={buildHref(page - 1)} className={linkClassName} scroll>
          <ChevronLeft size={17} aria-hidden="true" />
          Previous
        </Link>
      ) : (
        <span />
      )}
      <span className="text-sm font-medium text-muted">Page {page}</span>
      {hasNext ? (
        <Link href={buildHref(page + 1)} className={linkClassName} scroll>
          Next
          <ChevronRight size={17} aria-hidden="true" />
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
