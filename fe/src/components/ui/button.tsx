import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

const variants = cva(
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body disabled:cursor-not-allowed disabled:opacity-55 motion-reduce:transition-none",
  {
    variants: {
      variant: {
        primary:
          "border-brand bg-brand text-on-brand hover:bg-brand-strong",
        secondary:
          "border-border-strong bg-surface-raised text-ink hover:bg-surface-muted",
        // Hover lightens the same danger token so a destructive action never reads as brand maroon.
        danger: "border-danger bg-danger text-on-brand hover:bg-danger/90",
        quiet:
          "border-transparent bg-transparent text-brand hover:bg-brand-subtle",
      },
    },
    defaultVariants: { variant: "primary" },
  },
);

export type ButtonVariantProps = VariantProps<typeof variants>;

// The variant classes for <Button>, and for links that navigate but are presented as an action:
// those stay <Link> or <a> and take className={buttonVariants({ variant })}. A className passed here
// is merged, so a bounded change such as a margin or a full width replaces the conflicting default.
export function buttonVariants({
  className,
  ...options
}: ButtonVariantProps & { className?: string } = {}) {
  return cn(variants(options), className);
}

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    ButtonVariantProps {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, type = "button", variant, ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={buttonVariants({ variant, className })}
      {...props}
    />
  ),
);
Button.displayName = "Button";
