"use client";

import { ChevronDown, SlidersHorizontal } from "lucide-react";
import { useId, useState, type HTMLAttributes, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils/cn";

const toolbarFrame = "rounded-sm border border-brand-line bg-surface-raised px-4 py-4 sm:px-5";
const actionsClass = "flex shrink-0 flex-col-reverse gap-2 *:w-full sm:flex-row sm:justify-end sm:*:w-auto";

// In-flow search and filter controls, grouped on a single working surface between the page header
// and what they act on: the public Announcements and Resources lists, and parameter forms such as a
// report's filters. Collections in the authenticated portal use FloatingListTools instead. The
// fields share one grid; `actions` is the toolbar's one action area (Apply and Clear), which sits
// after the fields and fills the width on phones.
//
// A long toolbar passes its secondary filters as `advanced`. The children (usually the search)
// stay in view and the advanced filters fold away behind a Filters button that counts the ones
// in use. They start open while any is in use, so the reader can see what narrows the results.
// Folded fields stay in the form, so their values still apply.
//
// The toolbar does not decide how filters apply. When it needs a submit, wrap it in the feature's
// own <form>, and give that form role="search" and a name when it holds a text search.
export function FilterToolbar({
  actions,
  fieldsClassName,
  advanced,
  advancedCount = 0,
  advancedClassName,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  actions?: ReactNode;
  // Column layout for the fields, for example "lg:grid-cols-3".
  fieldsClassName?: string;
  // Secondary filters that fold away behind the Filters button.
  advanced?: ReactNode;
  // How many advanced filters differ from their defaults in the applied results.
  advancedCount?: number;
  // Column layout for the advanced filters, for example "lg:grid-cols-3".
  advancedClassName?: string;
}) {
  const advancedId = useId();
  const [open, setOpen] = useState(advancedCount > 0);

  if (!advanced) {
    return (
      <div className={cn("flex flex-col gap-4 lg:flex-row lg:items-end", toolbarFrame, className)} {...props}>
        <div className={cn("grid min-w-0 flex-1 gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-4", fieldsClassName)}>
          {children}
        </div>
        {actions ? <div className={actionsClass}>{actions}</div> : null}
      </div>
    );
  }

  // On phones the parts stack in reading order: search, the Filters button, the advanced filters,
  // then Apply. From lg the search, the button, and the actions share one row.
  return (
    <div
      className={cn(
        "grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end lg:gap-x-3",
        toolbarFrame,
        className,
      )}
      {...props}
    >
      <div className={cn("grid min-w-0 gap-x-4 gap-y-3", fieldsClassName)}>{children}</div>
      <Button
        type="button"
        variant="secondary"
        aria-expanded={open}
        aria-controls={advancedId}
        className="w-full sm:w-auto sm:justify-self-start lg:col-start-2 lg:row-start-1"
        onClick={() => setOpen((current) => !current)}
      >
        <SlidersHorizontal size={16} aria-hidden="true" />
        Filters
        {advancedCount > 0 ? (
          <>
            <span aria-hidden="true" className="tabular-nums">· {advancedCount}</span>
            <span className="sr-only">, {advancedCount} in use</span>
          </>
        ) : null}
        <ChevronDown
          size={16}
          aria-hidden="true"
          className={cn("transition-transform motion-reduce:transition-none", open && "rotate-180")}
        />
      </Button>
      <div
        id={advancedId}
        hidden={!open}
        className={cn(
          "grid min-w-0 gap-x-4 gap-y-3 border-t border-brand-line pt-4 sm:grid-cols-2 lg:col-span-3 lg:row-start-2 lg:grid-cols-4",
          advancedClassName,
        )}
      >
        {advanced}
      </div>
      {actions ? <div className={cn(actionsClass, "lg:col-start-3 lg:row-start-1")}>{actions}</div> : null}
    </div>
  );
}

export function FilterField({
  label,
  htmlFor,
  hint,
  className,
  children,
}: {
  label: ReactNode;
  htmlFor: string;
  // Help or a load failure for this field, already tied to the control by the feature.
  hint?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("grid min-w-0 content-start gap-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint}
    </div>
  );
}
