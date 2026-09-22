"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { PUBLIC_NAVIGATION, PUBLIC_SITE } from "@/features/public/config";
import { PublicAccountLink } from "@/features/public/components/public-account-link";
import { PublicBrand } from "@/features/public/components/public-brand";

function isActive(pathname: string | null, href: string) {
  if (!pathname) return false;
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function PublicSiteHeader({ overlay = false }: { overlay?: boolean }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className={overlay ? "public-header public-header--overlay" : "public-header"}>
      <div className="public-shell public-header__inner">
        <PublicBrand />

        <div className="public-header__actions">
          <nav className="public-nav" aria-label="Primary navigation">
            <ul>
              {PUBLIC_NAVIGATION.map((item) => {
                const current = isActive(pathname, item.href);

                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={current ? "public-nav__link is-current" : "public-nav__link"}
                      aria-current={current ? "page" : undefined}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>

          <PublicAccountLink
            className="public-auth-action public-auth-action__desktop"
            signedInLabel="Open workspace"
            signedOutLabel={PUBLIC_SITE.accountLabel.replace(" to COMPASS", "")}
          />

          <div className="public-mobile-nav">
            <DropdownMenu open={mobileOpen} onOpenChange={setMobileOpen} modal={false}>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="public-mobile-nav__trigger"
                  aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
                  aria-expanded={mobileOpen}
                >
                  {mobileOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                side="bottom"
                sideOffset={10}
                className="compass-surface public-mobile-nav__panel"
              >
                <nav aria-label="Mobile navigation">
                  {PUBLIC_NAVIGATION.map((item) => {
                    const current = isActive(pathname, item.href);

                    return (
                      <DropdownMenuItem
                        key={item.href}
                        asChild
                        className={current ? "public-mobile-nav__item is-current" : "public-mobile-nav__item"}
                      >
                        <Link href={item.href} aria-current={current ? "page" : undefined}>
                          {item.label}
                        </Link>
                      </DropdownMenuItem>
                    );
                  })}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild className="public-mobile-nav__item public-mobile-nav__item--auth">
                    <PublicAccountLink
                      signedInLabel="Open workspace"
                      signedOutLabel={PUBLIC_SITE.accountLabel}
                    />
                  </DropdownMenuItem>
                </nav>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </header>
  );
}
