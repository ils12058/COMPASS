"use client";

import { LayoutDashboard } from "lucide-react";
import Image from "next/image";
import { usePathname } from "next/navigation";

import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  portalWorkspaceGroups,
  type PortalWorkspaceLink,
} from "@/features/portal/components/portal-workspaces";
import { cn } from "@/lib/utils/cn";


function NavItem({
  link,
  current,
  onNavigate,
}: {
  link: PortalWorkspaceLink;
  current: boolean;
  onNavigate?: () => void;
}) {
  const Icon = link.icon;

  return (
    <GuardedPortalLink
      href={link.href}
      onNavigate={onNavigate}
      aria-current={current ? "page" : undefined}
      className={cn(
        "relative flex min-h-11 items-center gap-3 rounded-md px-3 text-sm text-on-brand/85 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand",
        current
          ? "bg-on-brand/15 font-semibold text-on-brand before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-on-brand"
          : "font-medium hover:bg-on-brand/10 hover:text-on-brand",
      )}
    >
      <Icon size={18} aria-hidden="true" className="shrink-0" />
      <span className="min-w-0">{link.label}</span>
    </GuardedPortalLink>
  );
}

export function PortalNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const isWithin = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");
  const visibleGroups = portalWorkspaceGroups(user);

  return (
    <div className="flex h-full min-h-full flex-col overflow-y-auto bg-brand-strong text-on-brand">
      <GuardedPortalLink
        href="/portal"
        onNavigate={onNavigate}
        className="flex min-h-18 shrink-0 items-center gap-3 border-b border-on-brand/15 px-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand"
        aria-label="COMPASS Portal Overview"
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
      </GuardedPortalLink>
      <nav aria-label="Portal navigation" className="p-3">
        <NavItem
          link={{ href: "/portal", label: "Overview", icon: LayoutDashboard }}
          current={pathname === "/portal"}
          onNavigate={onNavigate}
        />
        {visibleGroups.map((group) => (
          <div key={group.label} className="mt-3 border-t border-on-brand/10 pt-3">
            {/* A label only earns its place when it groups more than one destination. */}
            {group.links.length > 1 ? (
              <p className="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wider text-on-brand/60">
                {group.label}
              </p>
            ) : null}
            <div className="space-y-0.5">
              {group.links.map((link) => (
                <NavItem
                  key={link.href}
                  link={link}
                  current={isWithin(link.section ?? link.href)}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>
    </div>
  );
}
