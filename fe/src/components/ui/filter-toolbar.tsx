import type { HTMLAttributes, ReactNode } from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils/cn";

// Search and filter controls for one list, grouped on a single working surface between the page
// header and the results. The fields share one grid; `actions` is the toolbar's one action area
// (Apply and Clear), which sits after the fields and fills the width on phones.
//
// The toolbar does not decide how filters apply. When it needs a submit, wrap it in the feature's
// own <form>, and give that form role="search" and a name when it holds a text search.
export function FilterToolbar({
  actions,
  fieldsClassName,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  actions?: ReactNode;
  // Column layout for the fields, for example "lg:grid-cols-3".
  fieldsClassName?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 rounded-sm border border-brand-line bg-surface-raised px-4 py-4 sm:px-5 lg:flex-row lg:items-end",
        className,
      )}
      {...props}
    >
      <div className={cn("grid min-w-0 flex-1 gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-4", fieldsClassName)}>
        {children}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-col-reverse gap-2 *:w-full sm:flex-row sm:justify-end sm:*:w-auto">
          {actions}
        </div>
      ) : null}
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
