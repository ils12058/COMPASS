"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { PublicAccountAction } from "@/features/public/components/public-account-action";
import { PublicBrand } from "@/features/public/components/public-brand";
import { PUBLIC_NAVIGATION } from "@/features/public/config";
import { cn } from "@/lib/utils/cn";

function isActive(pathname: string, href: string): boolean {
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

export function PublicSiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b bg-[var(--compass-surface)]/95 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center gap-4 px-5 py-3 sm:px-8">
        <PublicBrand />

        <nav className="ml-auto hidden items-center gap-1 lg:flex" aria-label="Public navigation">
          {PUBLIC_NAVIGATION.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
              className={cn(
                "rounded-lg px-3 py-2 text-sm font-semibold no-underline",
                isActive(pathname, item.href)
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <PublicAccountAction className="ml-auto hidden sm:inline-flex lg:ml-2" />

        <button
          type="button"
          className="ml-auto inline-flex size-10 items-center justify-center rounded-lg border bg-card lg:hidden"
          aria-expanded={open}
          aria-controls="public-mobile-menu"
          aria-label={open ? "Close navigation menu" : "Open navigation menu"}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
        </button>
      </div>

      {open ? (
        <div id="public-mobile-menu" className="border-t bg-card lg:hidden">
          <nav
            className="mx-auto grid w-full max-w-7xl gap-1 px-5 py-4 sm:px-8"
            aria-label="Mobile public navigation"
          >
            {PUBLIC_NAVIGATION.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(pathname, item.href) ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-2.5 text-sm font-semibold no-underline",
                  isActive(pathname, item.href)
                    ? "bg-accent text-accent-foreground"
                    : "text-foreground hover:bg-muted",
                )}
                onClick={() => setOpen(false)}
              >
                {item.label}
              </Link>
            ))}
            <PublicAccountAction className="mt-2 sm:hidden" />
          </nav>
        </div>
      ) : null}
    </header>
  );
}
