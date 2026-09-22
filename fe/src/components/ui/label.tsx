import { forwardRef, type LabelHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

export const Label = forwardRef<
  HTMLLabelElement,
  LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("text-sm font-semibold text-ink", className)}
    {...props}
  />
));
Label.displayName = "Label";
