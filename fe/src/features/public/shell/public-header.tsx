"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useRef, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { PublicAccountMenu } from "@/features/public/shell/public-account-menu";
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { cn } from "@/lib/utils/cn";

const navigation = [
  { href: "/announcements", label: "Announcements" },
  { href: "/resources", label: "Resources" },
] as const;

function Brand() {
  return (
    <Link
      href="/"
      className="flex min-h-11 min-w-0 max-w-full flex-wrap items-center gap-2 rounded-sm @max-[16rem]:basis-full @max-[16rem]:gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
      aria-label="COMPASS home"
    >
      <Image
        src="/brand/ucn-logo.png"
        width={33}
        height={30}
        alt="University of Camarines Norte"
        className="h-8 w-auto object-contain @max-[16rem]:hidden"
        priority
      />
      <span className="h-7 w-px bg-border @max-[16rem]:hidden" aria-hidden="true" />
      <Image
        src="/brand/compass-mark.svg"
        width={34}
        height={34}
        alt=""
        aria-hidden="true"
      />
      <span className="font-heading text-lg font-bold tracking-[0.08em] text-brand-strong">
        COMPASS
      </span>
    </Link>
  );
}

// Three bars that fold into a close mark while the menu is open.
const menuBar =
  "absolute left-0 h-0.5 w-5 rounded-full bg-current transition-[translate,rotate,opacity] duration-200 ease-out";

function MobileMenu({
  pathname,
  signInHref,
}: {
  pathname: string;
  // Present only while signed out; a signed-in reader uses the account menu beside this button.
  signInHref?: string;
}) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const close = () => panelRef.current?.hidePopover();
  const closeOnEscape = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Escape" || !panelRef.current?.matches(":popover-open")) return;
    event.preventDefault();
    close();
    triggerRef.current?.focus();
  };

  return (
    <div className="@min-[42rem]:hidden">
      <button
        type="button"
        ref={triggerRef}
        onKeyDown={closeOnEscape}
        popoverTarget={panelId}
        aria-controls={panelId}
        aria-expanded={open}
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
        className="inline-flex size-11 items-center justify-center rounded-md border border-border bg-surface-raised text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        <span aria-hidden="true" className="relative h-3.5 w-5">
          <span className={cn(menuBar, "top-0", open && "translate-y-1.5 rotate-45")} />
          <span className={cn(menuBar, "top-1.5", open && "opacity-0")} />
          <span className={cn(menuBar, "top-3", open && "-translate-y-1.5 -rotate-45")} />
        </span>
      </button>

      {/* A native popover closes on outside taps; explicit Escape restores focus across engines. It
          sits in the top layer, where absolute positioning is page-relative, so it opens just
          below the header's menu button. */}
      <nav
        ref={panelRef}
        id={panelId}
        popover="auto"
        aria-label="Mobile public navigation"
        onKeyDown={closeOnEscape}
        onToggle={(event) => {
          const isOpen = event.newState === "open";
          setOpen(isOpen);
          if (isOpen) panelRef.current?.querySelector<HTMLAnchorElement>("a[href]")?.focus();
        }}
        className={cn(
          "fixed inset-auto m-0 w-[min(15rem,calc(100vw-2rem))] max-h-[min(32rem,calc(100dvh-2rem))] overflow-y-auto rounded-md border border-border bg-surface-raised p-1 text-ink shadow-dialog [position-area:bottom] [position-try-fallbacks:flip-block]",
          "origin-top-right -translate-y-1 scale-95 opacity-0 transition-[opacity,scale,translate,overlay,display] transition-discrete duration-150 ease-out",
          "open:translate-y-0 open:scale-100 open:opacity-100 starting:open:-translate-y-1 starting:open:scale-95 starting:open:opacity-0",
        )}
      >
        {navigation.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={close}
            aria-current={pathname.startsWith(item.href) ? "page" : undefined}
            className="flex min-h-11 items-center rounded-sm px-3 text-sm font-semibold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus aria-[current=page]:text-brand"
          >
            {item.label}
          </Link>
        ))}
        {signInHref ? (
          <>
            <div className="my-1 h-px bg-border" aria-hidden="true" />
            <Link
              href={signInHref}
              onClick={close}
              className={buttonVariants({ variant: "primary", className: "flex min-h-11 rounded-sm px-3" })}
            >
              Sign in to COMPASS
            </Link>
          </>
        ) : null}
      </nav>
    </div>
  );
}

export function PublicHeader() {
  const pathname = usePathname();
  const session = useAuthGetSession({ query: { retry: false, staleTime: 60_000 } });
  const user = session.isSuccess && session.data.data.authenticated ? session.data.data.user : null;

  return (
    <header className="relative z-30 border-b border-border bg-surface-raised">
      <div className="@container mx-auto max-w-6xl px-5 sm:px-8">
        <div className="flex min-h-18 flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2">
          <Brand />
          <div className="flex min-w-0 flex-wrap items-center gap-2 @max-[16rem]:gap-1">
            <nav aria-label="Public navigation" className="hidden items-center gap-1 @min-[42rem]:flex">
              {navigation.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={pathname.startsWith(item.href) ? "page" : undefined}
                  className="inline-flex min-h-10 items-center rounded-md px-3 text-sm font-semibold text-muted transition-colors hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus aria-[current=page]:text-brand"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            {/* Signed in, the reader's own menu replaces the Sign in button at every width. */}
            {user ? (
              <PublicAccountMenu user={user} />
            ) : (
              <Link
                href="/login"
                className={buttonVariants({ variant: "primary", className: "ml-2 hidden @min-[42rem]:inline-flex" })}
              >
                Sign in
              </Link>
            )}
            <AccessibilityControl placement="header" />
            <MobileMenu key={pathname} pathname={pathname} signInHref={user ? undefined : "/login"} />
          </div>
        </div>
      </div>
    </header>
  );
}
