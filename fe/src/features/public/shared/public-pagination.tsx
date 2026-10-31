import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

type PublicPaginationProps = {
  buildHref: (page: number) => string;
  hasNext: boolean;
  page: number;
};

const linkClassName =
  "inline-flex min-h-11 items-center justify-center gap-1 rounded-md border border-border-strong bg-surface-raised px-2 text-sm font-semibold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus @max-[14rem]:row-start-2";

export function PublicPagination({ buildHref, hasNext, page }: PublicPaginationProps) {
  if (page <= 1 && !hasNext) return null;

  return (
    <nav aria-label="Pagination" className="@container border-t border-brand-line px-4 py-3 sm:px-5">
      <div className="flex flex-wrap items-center justify-end gap-2 @max-[14rem]:grid @max-[14rem]:grid-cols-2">
        {page > 1 ? (
          <Link href={buildHref(page - 1)} className={linkClassName} title="Previous page" scroll>
            <ChevronLeft size={18} aria-hidden="true" />
            <span className="@max-[14rem]:sr-only">Previous</span>
          </Link>
        ) : null}
        <span className="px-1 text-sm font-medium text-muted @max-[14rem]:col-span-2 @max-[14rem]:row-start-1 @max-[14rem]:text-center">Page {page}</span>
        {hasNext ? (
          <Link href={buildHref(page + 1)} className={`${linkClassName} @max-[14rem]:col-start-2`} title="Next page" scroll>
            <span className="@max-[14rem]:sr-only">Next</span>
            <ChevronRight size={18} aria-hidden="true" />
          </Link>
        ) : null}
      </div>
    </nav>
  );
}
