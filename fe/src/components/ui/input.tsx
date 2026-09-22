import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25 disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-70",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
