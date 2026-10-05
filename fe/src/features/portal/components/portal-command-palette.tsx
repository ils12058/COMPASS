"use client";

import { Search } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { portalCommandDestinations, searchPortalCommands, type PortalCommandDestination } from "@/features/portal/components/portal-command-destinations";
import { hasOtherPortalModal, nextActiveCommandIndex, registerPortalCommandShortcut } from "@/features/portal/components/portal-command-keyboard";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { cn } from "@/lib/utils/cn";

export function PortalCommandSearch({ destinations, pathname, onNavigate }: {
  destinations: readonly PortalCommandDestination[];
  pathname: string;
  onNavigate: () => void;
}) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const results = searchPortalCommands(destinations, query);
  const active = results.length ? Math.min(activeIndex, results.length - 1) : -1;
  const listId = useId();
  const helpId = useId();
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    resultsRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [active, query]);

  return (
    <>
      <label htmlFor={`${listId}-search`} className="sr-only">Search COMPASS features</label>
      <Input
        id={`${listId}-search`}
        data-command-search
        role="combobox"
        aria-autocomplete="list"
        aria-expanded="true"
        aria-controls={listId}
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        aria-describedby={helpId}
        autoComplete="off"
        placeholder="Search COMPASS features…"
        value={query}
        onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); }}
        onKeyDown={(event) => {
          if (event.nativeEvent.isComposing || event.altKey || event.ctrlKey || event.metaKey) return;
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setActiveIndex(nextActiveCommandIndex(active, event.key === "ArrowDown" ? "down" : "up", results.length));
          } else if (event.key === "Enter" && active >= 0) {
            event.preventDefault();
            // Activate the real guarded link, including the existing unsaved-change confirmation.
            resultsRef.current?.querySelector<HTMLAnchorElement>('[aria-selected="true"]')?.click();
          }
        }}
      />
      <p id={helpId} className="sr-only">Search features, not records. Use Up and Down to choose a feature, Enter to open it, and Escape to close.</p>
      <div ref={resultsRef} id={listId} role="listbox" aria-label="COMPASS features" className="mt-3 max-h-[min(26rem,50dvh)] overflow-y-auto overscroll-contain">
        {results.map((destination, index) => {
          const Icon = destination.icon;
          return (
            <GuardedPortalLink
              key={`${destination.href}:${destination.label}`}
              id={`${listId}-${index}`}
              href={destination.href}
              prefetch={false}
              role="option"
              aria-selected={index === active}
              tabIndex={-1}
              onMouseDown={(event) => { if (event.button === 0) event.preventDefault(); }}
              onMouseMove={() => setActiveIndex(index)}
              onClick={(event) => {
                if (destination.href === pathname && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
                  event.preventDefault();
                  onNavigate(); // Keep current query parameters, editor state, and scroll position.
                }
              }}
              onNavigate={onNavigate}
              className={cn("flex min-h-11 items-center gap-3 rounded-sm px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus", index === active ? "bg-brand-wash text-brand-strong" : "text-ink hover:bg-surface-muted")}
            >
              <Icon size={18} aria-hidden="true" className="shrink-0 text-muted" />
              <span className="min-w-0 break-words">
                <span className="block font-semibold">{destination.label}</span>
                <span className="block text-xs leading-5 text-muted">{destination.breadcrumb}</span>
              </span>
            </GuardedPortalLink>
          );
        })}
      </div>
      {!results.length ? <p role="status" className="py-5 text-sm text-muted">No COMPASS features match your search.</p> : null}
      <p aria-hidden="true" className="mt-3 hidden border-t border-border pt-3 text-xs text-muted sm:block">↑↓ Navigate · Enter Open · Esc Close</p>
    </>
  );
}

export function PortalCommandPalette() {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const destinations = useMemo(() => portalCommandDestinations(user), [user]);
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const opener = useRef<HTMLElement | null>(null);

  // Mounted only with the authenticated PortalShell; public/auth routes never register it.
  useEffect(() => registerPortalCommandShortcut(() => setOpen((value) => !value), () => dialog.current), []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          ref={trigger}
          type="button"
          aria-label="Go to a COMPASS feature"
          aria-keyshortcuts="Meta+K Control+K"
          onClick={(event) => { if (hasOtherPortalModal(document, dialog.current)) event.preventDefault(); }}
          className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-md text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:w-full sm:max-w-xs sm:justify-start sm:border sm:border-border sm:px-3"
        >
          <Search size={18} aria-hidden="true" />
          <span className="hidden text-sm font-medium sm:inline">Go to…</span>
          <kbd aria-hidden="true" className="ml-auto hidden text-xs text-muted md:inline">⌘ / Ctrl K</kbd>
        </button>
      </DialogTrigger>
      <DialogContent
        ref={dialog}
        className="max-w-xl p-4 sm:p-5"
        onOpenAutoFocus={(event) => {
          opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
          event.preventDefault();
          dialog.current?.querySelector<HTMLInputElement>('[data-command-search]')?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          (opener.current?.isConnected ? opener.current : trigger.current)?.focus();
        }}
      >
        <DialogTitle>Go to a COMPASS feature</DialogTitle>
        <DialogDescription className="sr-only">Find a portal destination available to your account.</DialogDescription>
        <div className="mt-4">
          <PortalCommandSearch destinations={destinations} pathname={pathname} onNavigate={() => setOpen(false)} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
