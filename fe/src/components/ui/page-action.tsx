import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils/cn";

// A page's major commands — Create, Record, Import, Export, Refresh — drawn as a square icon surface
// with a short visible label below it, so the page's principal work reads at a glance. Reserve it
// for one to three commands in a PageHeader. Saving, cancelling, submitting, retrying, dialog
// confirmations, row actions, and actions that belong to one region stay ordinary Buttons, and Back
// stays a text link.
//
// The label is always visible; `labelDetail` completes the accessible name when the page makes the
// object obvious to a sighted reader ("Create" + "account" is announced as "Create account").
// A command that navigates is a real link (PageActionLink); one that changes data or opens a
// dialog is a real button (PageAction).
type PageActionVariant = "primary" | "secondary";

type PageActionContent = {
  icon: LucideIcon;
  label: string;
  labelDetail?: string;
  variant?: PageActionVariant;
};

const root =
  "group inline-flex min-w-12 max-w-28 flex-col items-center gap-1.5 rounded-md text-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body";

const surface: Record<PageActionVariant, string> = {
  primary: "border-brand bg-brand text-on-brand",
  secondary: "border-border-strong bg-surface-raised text-brand",
};

// Hover feedback; a disabled button keeps its resting look.
const hover: Record<PageActionVariant, string> = {
  primary: "group-hover:border-brand-strong group-hover:bg-brand-strong",
  secondary: "group-hover:bg-surface-muted",
};

function PageActionFace({
  icon: Icon,
  label,
  labelDetail,
  variant = "primary",
  interactive,
}: PageActionContent & { interactive: boolean }) {
  return (
    <>
      <span
        aria-hidden="true"
        data-page-action-surface={variant}
        className={cn(
          "flex size-12 items-center justify-center rounded-md border transition-colors motion-reduce:transition-none",
          surface[variant],
          interactive && hover[variant],
        )}
      >
        <Icon size={21} />
      </span>
      <span className="text-sm font-semibold leading-5 text-ink">
        {label}
        {labelDetail ? <span className="sr-only"> {labelDetail}</span> : null}
      </span>
    </>
  );
}

export function PageActionLink({
  href,
  className,
  ...content
}: PageActionContent & { href: string; className?: string }) {
  return (
    <Link href={href} className={cn(root, className)}>
      <PageActionFace {...content} interactive />
    </Link>
  );
}

export const PageAction = forwardRef<
  HTMLButtonElement,
  PageActionContent & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">
>(({ icon, label, labelDetail, variant, className, type = "button", disabled, ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    disabled={disabled}
    className={cn(root, "disabled:cursor-not-allowed disabled:opacity-55", className)}
    {...props}
  >
    <PageActionFace
      icon={icon}
      label={label}
      labelDetail={labelDetail}
      variant={variant}
      interactive={!disabled}
    />
  </button>
));
PageAction.displayName = "PageAction";

// Holds a page's one to three commands; they wrap rather than scroll on narrow screens.
export function PageActionGroup({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("flex flex-wrap items-start gap-x-4 gap-y-2", className)}>{children}</div>;
}
