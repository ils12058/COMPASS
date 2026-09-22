import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

const buttonVariants = cva(
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body disabled:cursor-not-allowed disabled:opacity-55 motion-reduce:transition-none",
  {
    variants: {
      variant: {
        primary:
          "border-brand bg-brand text-on-brand hover:bg-brand-strong",
        secondary:
          "border-border-strong bg-surface-raised text-ink hover:bg-surface-muted",
        danger: "border-danger bg-danger text-on-brand hover:bg-brand-strong",
        quiet:
          "border-transparent bg-transparent text-brand hover:bg-brand-subtle",
      },
    },
    defaultVariants: { variant: "primary" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, type = "button", variant, ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";
