import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

type HeadingLevel = 2 | 3;

function Heading({
  level,
  id,
  className,
  children,
}: {
  level: HeadingLevel;
  id?: string;
  className: string;
  children: ReactNode;
}) {
  const Tag = level === 2 ? "h2" : "h3";
  return (
    <Tag id={id} className={className}>
      {children}
    </Tag>
  );
}

// A bounded working surface on the warm canvas: white, framed evenly by the maroon-tinted line,
// with a near-square corner and no shadow. Use it for things that belong together — a filter
// toolbar's results, a record, a form, an Overview region — not as a default wrapper for every
// heading or paragraph. The frame is the same on every side: no colored top or side stripe.
export function Panel({
  as: Tag = "section",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & {
  as?: "section" | "div" | "aside" | "article";
}) {
  return (
    <Tag
      className={cn("min-w-0 rounded-sm border border-brand-line bg-surface-raised", className)}
      {...props}
    >
      {children}
    </Tag>
  );
}

// The panel's title band. `context` is short text about the contents, such as how many results
// are on this page. Passing it, even as null while loading, keeps one polite live region in place,
// so a new result count is announced after a filter or page change. `actions` holds links or
// buttons that act on the whole panel.
export function PanelHeader({
  title,
  titleId,
  level = 2,
  description,
  context,
  actions,
  className,
}: {
  title: ReactNode;
  titleId?: string;
  level?: HeadingLevel;
  description?: ReactNode;
  context?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      data-panel-header=""
      className={cn(
        "flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-brand-line px-4 py-3 sm:px-5",
        className,
      )}
    >
      <div className="min-w-0">
        <Heading level={level} id={titleId} className="font-heading text-lg font-semibold leading-snug text-ink">
          {title}
        </Heading>
        {description ? <p className="mt-0.5 text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {context !== undefined || actions ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {context !== undefined ? (
            <p aria-live="polite" aria-atomic="true" className="text-sm text-muted">
              {context}
            </p>
          ) : null}
          {actions}
        </div>
      ) : null}
    </div>
  );
}

export function PanelBody({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("px-4 py-4 sm:px-5", className)}>{children}</div>;
}

// A named group inside one panel, such as one part of an official form or record sheet. Groups are
// separated by the panel's own line instead of each becoming a separate card.
export function PanelSection({
  title,
  titleId,
  level = 2,
  description,
  actions,
  className,
  children,
  ...props
}: Omit<HTMLAttributes<HTMLElement>, "title"> & {
  title: ReactNode;
  titleId: string;
  level?: HeadingLevel;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-labelledby={titleId}
      className={cn(
        // The first group in a panel, or the first after the panel's header or a fieldset's legend,
        // needs no line of its own.
        "border-t border-brand-line px-4 py-5 first:border-t-0 [legend+&]:border-t-0 [[data-panel-header]+&]:border-t-0 sm:px-5",
        className,
      )}
      {...props}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <Heading
          level={level}
          id={titleId}
          className="font-heading text-sm font-semibold uppercase tracking-[0.08em] text-brand"
        >
          {title}
        </Heading>
        {actions}
      </div>
      {description ? <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
      {/* Content written for a bare section often opens with its own top margin; the section's
          spacing replaces it. */}
      <div className="mt-4 *:first:mt-0">{children}</div>
    </section>
  );
}

// The panel's one action area, such as a form's submit and cancel.
export function PanelFooter({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-3 rounded-b-sm border-t border-brand-line bg-brand-wash px-4 py-3 sm:px-5",
        className,
      )}
    >
      {children}
    </div>
  );
}

// An empty, error, or unavailable state that belongs to the panel it sits in. Pass role="alert" for
// failures; empty states announce nothing.
//
// Its weight follows what it says. A short muted message with nothing to do ("No counseling
// encounters are assigned to you yet.") is compact, so a sparse list stays shallow; a failure or
// a message with an action keeps room for its Retry or next step. Pass `density` only to override
// that for a reason.
export function PanelMessage({
  tone = "muted",
  action,
  density,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  tone?: "muted" | "danger";
  action?: ReactNode;
  density?: "compact" | "regular";
}) {
  const compact = (density ?? (tone === "muted" && !action ? "compact" : "regular")) === "compact";
  return (
    <div
      data-density={compact ? "compact" : "regular"}
      className={cn("px-4 sm:px-5", compact ? "py-3.5" : "py-6", className)}
      {...props}
    >
      <p className={cn("max-w-3xl text-sm leading-6", tone === "danger" ? "text-danger" : "text-muted")}>
        {children}
      </p>
      {action ? <div className="mt-3 flex flex-wrap gap-3">{action}</div> : null}
    </div>
  );
}

export type RecordFact = { label: string; value: ReactNode };

// The top of a record's page: what the record is, its current status, and the few facts a reader
// checks first. Place it first inside the record's Panel; detail groups follow as PanelSections.
export function RecordSummary({
  label,
  title,
  titleId,
  status,
  facts = [],
  className,
}: {
  // The record type or role of the name below, such as "Applicant".
  label?: string;
  title: ReactNode;
  titleId?: string;
  status?: ReactNode;
  facts?: RecordFact[];
  className?: string;
}) {
  return (
    <div className={cn("px-4 py-4 sm:px-5", className)}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          {label ? <p className="text-xs font-semibold text-muted">{label}</p> : null}
          <h2 id={titleId} className="mt-0.5 break-words font-heading text-xl font-semibold leading-snug text-ink">
            {title}
          </h2>
        </div>
        {status ? <div className="shrink-0">{status}</div> : null}
      </div>
      {facts.length > 0 ? (
        <dl className="mt-4 grid gap-x-6 gap-y-3 border-t border-brand-line pt-4 sm:grid-cols-2 lg:grid-cols-4">
          {facts.map((fact) => (
            <div key={fact.label} className="min-w-0">
              <dt className="text-xs font-semibold text-muted">{fact.label}</dt>
              <dd className="mt-0.5 break-words text-sm text-ink">{fact.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
