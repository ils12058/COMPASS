"use client";

import { Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useState } from "react";

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

function MobileMenu() {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md border border-border bg-surface-raised text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <X aria-hidden="true" size={21} /> : <Menu aria-hidden="true" size={21} />}
      </button>

      {open ? (
        <nav
          id={panelId}
          aria-label="Mobile public navigation"
          className="absolute inset-x-0 top-full z-20 border-y border-border bg-surface-raised px-5 py-4 shadow-sm"
        >
          <div className="mx-auto flex max-w-6xl flex-col">
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="flex min-h-11 items-center border-b border-border text-sm font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              >
                {item.label}
              </Link>
            ))}
            <Link
              href="/login"
              onClick={() => setOpen(false)}
              className="mt-3 inline-flex min-h-11 items-center justify-center rounded-md bg-brand px-4 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
            >
              Sign in to COMPASS
            </Link>
          </div>
        </nav>
      ) : null}
    </div>
  );
}

export function PublicHeader() {
  const pathname = usePathname();

  return (
    <header className="relative z-30 border-b border-border bg-surface-raised">
      <div className="mx-auto flex h-18 max-w-6xl items-center justify-between gap-6 px-5 sm:px-8">
        <Brand />
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
          <Link
            href="/login"
            className="ml-2 inline-flex min-h-10 items-center rounded-md border border-brand bg-brand px-4 text-sm font-semibold text-on-brand transition-colors hover:bg-brand-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
          >
            Sign in
          </Link>
        </nav>
        <MobileMenu key={pathname} />
      </div>
    </header>
  );
}
