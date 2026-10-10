"use client";

import { Search, SlidersHorizontal, X } from "lucide-react";
import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils/cn";

// Many features remount their filter form when the applied filters change, which takes the control
// that submitted it along. The new tools return focus to the matching control if nothing else has
// it shortly after.
let focusAfterApply: { target: "filters" | "bar"; until: number } | null = null;

// Find and refine tools for one collection in the authenticated portal, floating near the bottom
// of the workspace instead of standing between the page header and the records. The bar holds the
// collection's search (`children`), a Filters button that counts the structured filters in use, and
// the form's submit when the filters apply together. Pagination stays with the results.
//
// The structured filters open in a native modal <dialog>: anchored above the bar on wider screens
// and as a bottom sheet on phones. The dialog stays in the DOM while closed, so its fields stay in
// the feature's <form> and keep applying — the same rule as FilterToolbar's folded filters. The
// browser provides the modal semantics, Escape, the inert page behind, and the return of focus to
// the Filters button.
//
// The tools center on the portal workspace through the shell's `--portal-content-inset`, and the
// shell keeps the last records clear of them while they are on the page (`--list-tools-clearance`).
//
// How filters apply stays the feature's decision, as with FilterToolbar. When the search and
// filters apply together, wrap the tools in the feature's <form role="search" aria-label="…"> and
// pass `submits`. Without `submits`, each control applies on its own.
export function FloatingListTools({
  label,
  children,
  filters,
  filterCount = 0,
  filtersClassName,
  submits = false,
  invalid = false,
  compact = false,
  clear,
}: {
  // Names the tools when they are not already inside a named search form.
  label?: string;
  // What stays in the bar: a ListSearchField, or a ListToolField for a list whose only filter is
  // one short choice.
  children?: ReactNode;
  // The structured filters, each in a FilterField.
  filters?: ReactNode;
  // How many structured filters differ from their defaults in the applied results.
  filterCount?: number;
  // Column layout for the filter fields, for example "md:grid-cols-3".
  filtersClassName?: string;
  // The search and filters apply together through the surrounding form's submit.
  submits?: boolean;
  // The filters hold a value the feature refuses to apply, such as a From date after the To date.
  // Submitting then opens the panel, where the feature shows why, instead of closing it.
  invalid?: boolean;
  // The bar holds a ListToolField rather than a search.
  compact?: boolean;
  // The feature's Clear control (a Link or a quiet Button), passed only while something is applied.
  clear?: ReactNode;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const backdropPress = useRef(false);
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const titleId = useId();
  // A search field fills the bar; a single ListToolField keeps the bar to its own width.
  const hasSearch = Boolean(children) && !compact;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  // Applying the filters, from the bar or from the panel, closes the panel. The decision waits for
  // the feature's own submit handler, which may refuse the filters and say why in the panel.
  const invalidRef = useRef(invalid);
  useLayoutEffect(() => {
    invalidRef.current = invalid;
  }, [invalid]);
  useEffect(() => {
    const form = rootRef.current?.closest("form");
    if (!form) return;
    let timer: number | undefined;
    const onSubmit = (event: SubmitEvent) => {
      const fromPanel = Boolean(event.submitter && dialogRef.current?.contains(event.submitter));
      focusAfterApply = { target: fromPanel ? "filters" : "bar", until: Date.now() + 2000 };
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setOpen(invalidRef.current), 0);
    };
    form.addEventListener("submit", onSubmit);
    const pending = focusAfterApply;
    const active = document.activeElement;
    if (pending && pending.until > Date.now() && (!active || active === document.body)) {
      const bar = rootRef.current?.querySelector<HTMLElement>("input, select, button");
      (pending.target === "filters" ? triggerRef.current ?? bar : bar)?.focus();
      focusAfterApply = null;
    }
    return () => {
      form.removeEventListener("submit", onSubmit);
      window.clearTimeout(timer);
    };
  }, []);

  const submitBar = submits ? (
    <Button type="submit" className="shrink-0">
      {hasSearch ? "Search" : "Apply filters"}
    </Button>
  ) : null;

  return (
    <div
      ref={rootRef}
      data-floating-list-tools=""
      className="pointer-events-none fixed bottom-0 left-[var(--portal-content-inset,0px)] right-0 z-30 flex justify-center px-4 pb-(--list-tools-offset) transition-[left] duration-200 ease-out sm:px-6 lg:px-8 print:hidden"
    >
      <div
        role={label ? "group" : undefined}
        aria-label={label}
        className={cn(
          "pointer-events-auto flex h-(--list-tools-height) min-w-0 items-center gap-2 rounded-md border border-brand-line bg-surface-raised px-2 shadow-float",
          hasSearch ? "w-full max-w-2xl" : "max-w-full",
        )}
      >
        {children}
        {filters ? (
          <Button
            ref={triggerRef}
            type="button"
            variant="secondary"
            aria-haspopup="dialog"
            aria-expanded={open}
            aria-controls={panelId}
            className="shrink-0 px-3"
            onClick={() => setOpen(true)}
          >
            <SlidersHorizontal size={16} aria-hidden="true" />
            {/* On phones the icon and the count carry the button beside the search. */}
            <span className={hasSearch ? "max-sm:sr-only" : undefined}>Filters</span>
            {filterCount > 0 ? (
              <>
                <span aria-hidden="true" className="tabular-nums">
                  <span className={hasSearch ? "max-sm:hidden" : undefined}>· </span>
                  {filterCount}
                </span>
                <span className="sr-only">, {filterCount} in use</span>
              </>
            ) : null}
          </Button>
        ) : null}
        {/* Without anything in the bar, the panel's own Apply filters is the submit. */}
        {children ? submitBar : null}
        {!filters && clear ? <div className="shrink-0">{clear}</div> : null}
      </div>

      {filters ? (
        <dialog
          ref={dialogRef}
          id={panelId}
          aria-labelledby={titleId}
          onClose={() => {
            setOpen(false);
            // Browsers return focus to the Filters button; this covers one that does not.
            const active = document.activeElement;
            if (!active || active === document.body || dialogRef.current?.contains(active)) {
              triggerRef.current?.focus();
            }
          }}
          onPointerDown={(event) => {
            backdropPress.current = event.target === event.currentTarget;
          }}
          onClick={(event) => {
            // The panel fills the dialog box, so a click on the dialog itself is on the backdrop.
            if (event.target === event.currentTarget && backdropPress.current) setOpen(false);
          }}
          className={cn(
            "pointer-events-auto m-0 overflow-hidden border border-border bg-surface-raised p-0 text-ink shadow-dialog open:flex open:flex-col",
            // Phones: a bottom sheet over a dimmed page.
            "inset-x-0 bottom-0 top-auto h-auto max-h-[85dvh] w-full max-w-none rounded-t-md backdrop:bg-overlay",
            // Wider screens: a panel just above the bar, centered on the workspace.
            "md:bottom-[calc(var(--list-tools-offset)_+_var(--list-tools-height)_+_0.5rem)] md:left-[var(--portal-content-inset,0px)] md:right-0 md:mx-auto md:max-h-[min(36rem,calc(100dvh_-_8rem))] md:w-[min(42rem,calc(100vw_-_var(--portal-content-inset,0px)_-_3rem))] md:rounded-md md:backdrop:bg-transparent",
          )}
        >
          <div className="flex min-h-14 shrink-0 items-center border-b border-brand-line pl-4 pr-14 sm:pl-5">
            <h2 id={titleId} className="font-heading text-lg font-semibold text-ink">
              Filters
            </h2>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-5">
            <div className={cn("grid gap-x-4 gap-y-3 sm:grid-cols-2", filtersClassName)}>{filters}</div>
          </div>
          <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-brand-line bg-brand-wash px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 *:w-full sm:flex-row sm:justify-end sm:px-5 sm:*:w-auto">
            {clear}
            {submits ? (
              <Button type="submit">Apply filters</Button>
            ) : (
              <Button variant="secondary" onClick={() => setOpen(false)}>
                Show results
              </Button>
            )}
          </div>
          {/* Last in the panel, so the first Tab stop is the first filter. */}
          <button
            type="button"
            aria-label="Close filters"
            onClick={() => setOpen(false)}
            className="absolute right-1.5 top-1.5 inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </dialog>
      ) : null}
    </div>
  );
}

// The search field that leads the floating list tools. Its label is visually hidden: the icon,
// the placeholder, and the bar's position say what it is, and screen readers hear the label.
export function ListSearchField({
  id,
  label,
  className,
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { id: string; label: string }) {
  return (
    <div className={cn("relative min-w-0 flex-1", className)}>
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <Search
        size={17}
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
      />
      <Input id={id} type="search" className="pl-9" {...props} />
    </div>
  );
}

// A single labeled choice that stands in the bar on its own, for a collection whose only filter is
// one short select. Pass `compact` to FloatingListTools with it.
export function ListToolField({
  label,
  htmlFor,
  children,
}: {
  label: ReactNode;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3 pl-2">
      <Label htmlFor={htmlFor} className="shrink-0">
        {label}
      </Label>
      <div className="min-w-0 [&>select]:w-auto [&>select]:max-w-full">{children}</div>
    </div>
  );
}
