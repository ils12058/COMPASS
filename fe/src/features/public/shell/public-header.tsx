"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useRef, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
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
      className="flex min-h-11 items-center gap-2 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
      aria-label="COMPASS home"
    >
      <Image
        src="/brand/ucn-logo.png"
        width={33}
        height={30}
        alt="University of Camarines Norte"
        className="h-8 w-auto object-contain"
        priority
      />
      <span className="h-7 w-px bg-border" aria-hidden="true" />
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
  const panelId = useId();
  const close = () => panelRef.current?.hidePopover();

  return (
    <div className="md:hidden">
      <button
        type="button"
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

      {/* A native popover closes on outside taps and Escape and returns focus to the button. It
          sits in the top layer, where absolute positioning is page-relative, so it opens just
          below the header's menu button. */}
      <nav
        ref={panelRef}
        id={panelId}
        popover="auto"
        aria-label="Mobile public navigation"
        onToggle={(event) => setOpen(event.newState === "open")}
        className={cn(
          "absolute inset-auto top-20 right-5 m-0 w-60 rounded-md border border-border bg-surface-raised p-1 text-ink shadow-dialog sm:right-8",
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
      <div className="mx-auto flex h-18 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
        <Brand />
        <div className="flex items-center gap-2">
        <nav aria-label="Public navigation" className="hidden items-center gap-1 md:flex">
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
            className={buttonVariants({ variant: "primary", className: "ml-2 hidden md:inline-flex" })}
          >
            Sign in
          </Link>
        )}
        <MobileMenu key={pathname} pathname={pathname} signInHref={user ? undefined : "/login"} />
        </div>
      </div>
    </header>
  );
}
