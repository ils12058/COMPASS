import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type ComponentProps, type ComponentType, type HTMLAttributes } from "react";

import { cn } from "@/lib/utils/cn";

// A page's major commands use a compact icon and visible label in one touch-friendly control. Reserve it
// for one to three page-level commands near a heading. Saving, cancelling, submitting, retrying, dialog
// confirmations, row actions, and actions that belong to one region stay ordinary Buttons, and Back
// stays a text link.
//
// The label is always visible; `labelDetail` completes the accessible name when the page makes the
// object obvious to a sighted reader ("Create" + "account" is announced as "Create account").
// A command that navigates is a real link (PageActionLink); one that changes data or opens a
// dialog is a real button (PageAction).
type PageActionVariant = "primary" | "secondary" | "danger";

type PageActionContent = {
  icon: LucideIcon;
  label: string;
  labelDetail?: string;
  variant?: PageActionVariant;
};

const root =
  "group inline-flex min-h-11 min-w-11 max-w-full items-center justify-center gap-2 rounded-md border px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body motion-reduce:transition-none";

const surface: Record<PageActionVariant, string> = {
  primary: "border-brand bg-brand text-on-brand",
  secondary: "border-border-strong bg-surface-raised text-brand",
  danger: "border-danger bg-danger text-on-brand",
};

// Hover feedback; a disabled button keeps its resting look.
const hover: Record<PageActionVariant, string> = {
  primary: "hover:border-brand-strong hover:bg-brand-strong",
  secondary: "hover:bg-surface-muted",
  danger: "hover:bg-danger/90",
};

function PageActionFace({
  icon: Icon,
  label,
  labelDetail,
  variant = "primary",
}: PageActionContent) {
  return (
    <>
      <span
        aria-hidden="true"
        data-page-action-surface={variant}
        className={cn(
          "flex shrink-0 items-center justify-center",
        )}
      >
        <Icon size={18} />
      </span>
      <span data-page-action-label="" className="[overflow-wrap:anywhere] text-sm font-semibold leading-5">
        {label}
        {labelDetail ? <span className="sr-only"> {labelDetail}</span> : null}
      </span>
    </>
  );
}

export function PageActionLink({
  as: LinkComponent = Link,
  href,
  className,
  ...content
}: PageActionContent & { href: string; className?: string; as?: ComponentType<ComponentProps<typeof Link>> }) {
  return (
    <LinkComponent href={href} className={cn(root, surface[content.variant ?? "primary"], hover[content.variant ?? "primary"], className)}>
      <PageActionFace {...content} />
    </LinkComponent>
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
    className={cn(root, surface[variant ?? "primary"], !disabled && hover[variant ?? "primary"], "disabled:cursor-not-allowed disabled:opacity-55", className)}
    {...props}
  >
    <PageActionFace
      icon={icon}
      label={label}
      labelDetail={labelDetail}
      variant={variant}
    />
  </button>
));
PageAction.displayName = "PageAction";

// Holds a page's one to three commands; they wrap rather than scroll on narrow screens. A detail
// page can place the same group under its heading on phones and in a vertical rail on desktop.
export function PageActionGroup({ className, children, role, "aria-label": ariaLabel, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-wrap items-start gap-2", className)}
      role={role ?? (ariaLabel ? "group" : undefined)}
      aria-label={ariaLabel}
      {...props}
    >
      {children}
    </div>
  );
}
