import type { ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

// Styling for the optional "Back to …" link above a page title. The feature renders the link
// itself, so a workspace that guards unsaved changes can keep its own link component.
export const pageBackLinkClass =
  "mb-2 inline-flex min-h-10 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

// The page title, kept compact so the page's own work starts quickly. A description is for what the
// title and the controls do not already say: scope, policy, privacy, or consequences.
// It draws no rule underneath: the working region that follows carries its own boundary. The
// header owns the one gap before that region, so feature wrappers do not remove it and the next
// region does not add its own. Page actions line up with the title, not with the description.
export function PageHeader({
  title,
  headingId,
  description,
  back,
  context,
  meta,
  actions,
  help,
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
  help?: ReactNode;
  className?: string;
  // Anything else that belongs under the title, such as record dates.
  children?: ReactNode;
}) {
  return (
    <header className={cn("mb-5", className)}>
      {back}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {context ? <p className="text-sm font-medium text-muted">{context}</p> : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 id={headingId} className="min-w-0 break-words font-heading text-2xl font-bold leading-tight text-ink sm:text-3xl">
              {title}
            </h1>
            {meta}
          </div>
          {description ? (
            <p className="mt-1 max-w-3xl [overflow-wrap:anywhere] text-sm leading-6 text-muted">{description}</p>
          ) : null}
          {children}
        </div>
        {/* Actions wrap within their share of the row, so a narrowed page (such as one beside an open
            Messages panel) never breaks its title mid-word. */}
        {actions || help ? <div className="flex min-w-0 flex-wrap items-start gap-2 sm:max-w-[65%] sm:justify-end">{actions}{help}</div> : null}
      </div>
    </header>
  );
}
