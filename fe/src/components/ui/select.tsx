import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

// A native <select> with the same control language as Input and Textarea, including the
// aria-invalid treatment. Options stay ordinary <option> children.
export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(
      "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink outline-none focus:border-focus focus:ring-2 focus:ring-focus/25 aria-[invalid=true]:border-danger aria-[invalid=true]:focus:border-danger aria-[invalid=true]:focus:ring-danger/25 disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-70",
      className,
    )}
    {...props}
  />
));
Select.displayName = "Select";
