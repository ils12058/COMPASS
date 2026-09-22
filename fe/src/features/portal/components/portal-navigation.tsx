"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { usePortalSession } from "@/features/portal/components/portal-session";

export function PortalNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const canManageAccounts = user.capabilities.includes("accounts.manage");

  return (
    <div className="flex h-full flex-col bg-brand-strong text-on-brand">
      <Link
        href="/portal"
        onClick={onNavigate}
        className="flex min-h-18 items-center gap-3 border-b border-on-brand/15 px-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand"
        aria-label="COMPASS portal home"
      >
        <Image
          src="/brand/compass-mark.svg"
          width={36}
          height={36}
          alt=""
          aria-hidden="true"
        />
        <span className="font-heading text-lg font-bold tracking-[0.08em]">
          COMPASS
        </span>
      </Link>
      <nav aria-label="Portal navigation" className="p-3">
        <Link
          href="/portal"
          onClick={onNavigate}
          aria-current={pathname === "/portal" ? "page" : undefined}
          className={`flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand ${pathname === "/portal" ? "bg-on-brand/12" : "hover:bg-on-brand/10"}`}
        >
          Home
        </Link>
        {canManageAccounts ? (
          <div className="mt-7 border-t border-on-brand/15 pt-5">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-on-brand/70">
              Identity &amp; Access
            </p>
            <Link
              href="/portal/accounts"
              onClick={onNavigate}
              aria-current={
                pathname.startsWith("/portal/accounts") ? "page" : undefined
              }
              className={`mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand ${pathname.startsWith("/portal/accounts") ? "bg-on-brand/12" : "hover:bg-on-brand/10"}`}
            >
              Accounts
            </Link>
          </div>
        ) : null}
      </nav>
    </div>
  );
}
