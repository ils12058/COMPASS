import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

// Styling for the optional "Back to …" link above a page title. The feature renders the link
// itself, so a workspace that guards unsaved changes can keep its own link component.
export const pageBackLinkClass =
  "mb-2 inline-flex min-h-10 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

// The page title and what the page is for, kept compact so the page's own work starts quickly.
// It draws no rule underneath: the working region that follows carries its own boundary.
export function PageHeader({
  title,
  headingId,
  description,
  back,
  context,
  meta,
  actions,
  className,
  children,
}: {
  title: ReactNode;
  headingId?: string;
  description?: ReactNode;
  // A "Back to …" link, styled with pageBackLinkClass.
  back?: ReactNode;
  // Parent context that the title does not already say, such as the workspace a record belongs to.
  context?: ReactNode;
  // Short facts that belong beside the title, such as a record status.
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
  // Anything else that belongs under the title, such as record dates.
  children?: ReactNode;
}) {
  return (
    <header className={cn("mb-6", className)}>
      {back}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          {context ? <p className="text-sm font-medium text-muted">{context}</p> : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 id={headingId} className="min-w-0 break-words font-heading text-3xl font-bold leading-tight text-ink">
              {title}
            </h1>
            {meta}
          </div>
          {description ? (
            <p className="mt-1.5 max-w-3xl text-sm leading-6 text-muted">{description}</p>
          ) : null}
          {children}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
