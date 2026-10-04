"use client";

import { LayoutDashboard } from "lucide-react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FocusEvent, type PointerEvent } from "react";

import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  portalWorkspaceGroups,
  type PortalWorkspaceLink,
} from "@/features/portal/components/portal-workspaces";
import { cn } from "@/lib/utils/cn";

const overviewLink: PortalWorkspaceLink = { href: "/portal", label: "Overview", icon: LayoutDashboard };

// Every dock destination keeps its icon in the same place whether or not its label shows, so the
// rail does not shift when it expands.
const itemClass =
  "flex min-h-11 w-full items-center gap-3 rounded-md px-4 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand focus-visible:ring-offset-2 focus-visible:ring-offset-brand-strong";

type Tip = { label: string; top: number; left: number };

// The label beside a collapsed dock control, shown on hover and on keyboard focus. Each control
// already carries the same text as its accessible name, so the tip is hidden from assistive
// technology. It is fixed to the window so the dock's own scrolling does not clip it, it stays while
// the pointer moves onto it, and Escape dismisses it.
function useDockTips(enabled: boolean) {
  const [tip, setTip] = useState<Tip | null>(null);
  const hideTimer = useRef<number | undefined>(undefined);

  const cancelHide = useCallback(() => window.clearTimeout(hideTimer.current), []);
  const hide = useCallback(() => {
    window.clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => setTip(null), 80);
  }, []);
  const show = useCallback(
    (label: string, target: HTMLElement) => {
      if (!enabled) return;
      cancelHide();
      const rect = target.getBoundingClientRect();
      setTip({ label, top: rect.top + rect.height / 2, left: rect.right + 10 });
    },
    [cancelHide, enabled],
  );

  useEffect(() => {
    if (!tip) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setTip(null);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [tip]);

  useEffect(() => () => window.clearTimeout(hideTimer.current), []);

  const bind = (label: string) => ({
    onPointerEnter: (event: PointerEvent<HTMLElement>) => show(label, event.currentTarget),
    onPointerLeave: hide,
    onFocus: (event: FocusEvent<HTMLElement>) => show(label, event.currentTarget),
    onBlur: () => setTip(null),
  });

  const element =
    enabled && tip ? (
      <div
        aria-hidden="true"
        style={{ top: tip.top, left: tip.left }}
        onPointerEnter={cancelHide}
        onPointerLeave={hide}
        className="fixed z-50 -translate-y-1/2 whitespace-nowrap rounded-md border border-border bg-surface-raised px-2.5 py-1.5 text-sm font-semibold text-ink shadow-float"
      >
        {tip.label}
      </div>
    ) : null;

  return { bind, clear: () => setTip(null), element };
}

function NavItem({
  link,
  current,
  expanded,
  onNavigate,
  tipProps,
}: {
  link: PortalWorkspaceLink;
  current: boolean;
  expanded: boolean;
  onNavigate?: () => void;
  tipProps: ReturnType<ReturnType<typeof useDockTips>["bind"]>;
}) {
  const Icon = link.icon;

  return (
    <GuardedPortalLink
      href={link.href}
      onNavigate={onNavigate}
      aria-current={current ? "page" : undefined}
      className={cn(
        itemClass,
        // The current destination is a lit tile in the dock, not a stripe on its edge.
        current
          ? "bg-on-brand font-semibold text-brand-strong"
          : "font-medium text-on-brand/85 hover:bg-on-brand/10 hover:text-on-brand",
      )}
      {...tipProps}
    >
      <Icon size={20} aria-hidden="true" className="shrink-0" />
      <span className={expanded ? "min-w-0 truncate" : "sr-only"}>{link.label}</span>
    </GuardedPortalLink>
  );
}

// The portal's destinations, from portalWorkspaceGroups. On wide screens this is the dock: it shows
// labels until the reader collapses it to an icon rail (`expanded` false) with the top bar's button.
// In the small-screen drawer it always shows labels, and `onNavigate` closes the drawer.
export function PortalNavigation({
  expanded,
  navigationId,
  onNavigate,
}: {
  expanded: boolean;
  navigationId?: string;
  onNavigate?: () => void;
}) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const isWithin = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");
  const visibleGroups = portalWorkspaceGroups(user);
  const tips = useDockTips(!expanded);
  const navRef = useRef<HTMLElement>(null);

  // A long dock scrolls on its own; keep the current destination in view as the reader moves.
  useEffect(() => {
    navRef.current
      ?.querySelector<HTMLElement>('[aria-current="page"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [pathname, expanded]);

  return (
    <div className="flex h-full min-h-full flex-col overflow-hidden bg-brand-strong text-on-brand">
      <GuardedPortalLink
        href="/portal"
        onNavigate={onNavigate}
        className="flex min-h-14 shrink-0 items-center gap-3 border-b border-on-brand/15 px-5.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-on-brand"
        aria-label="COMPASS Portal Overview"
        {...tips.bind("COMPASS Overview")}
      >
        <Image
          src="/brand/compass-mark.svg"
          width={32}
          height={32}
          alt=""
          aria-hidden="true"
          className="shrink-0"
        />
        <span
          aria-hidden="true"
          className={cn("font-heading text-lg font-bold tracking-[0.08em]", !expanded && "sr-only")}
        >
          COMPASS
        </span>
      </GuardedPortalLink>
      <nav
        ref={navRef}
        id={navigationId}
        aria-label="Portal navigation"
        onScroll={tips.clear}
        className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-3"
      >
        <NavItem
          link={overviewLink}
          current={pathname === "/portal"}
          expanded={expanded}
          onNavigate={onNavigate}
          tipProps={tips.bind(overviewLink.label)}
        />
        {visibleGroups.map((group) => (
          <div key={group.label} className="mt-2 border-t border-on-brand/15 pt-2">
            {/* A label only earns its place when it groups more than one destination. In the rail
                the line between groups does the grouping, and the label stays for screen readers. */}
            {group.links.length > 1 ? (
              <p
                className={
                  expanded
                    ? "truncate px-4 pb-1 pt-1 text-xs font-semibold uppercase tracking-wider text-on-brand/65"
                    : "sr-only"
                }
              >
                {group.label}
              </p>
            ) : null}
            <div className="space-y-1">
              {group.links.map((link) => (
                <NavItem
                  key={link.href}
                  link={link}
                  current={isWithin(link.section ?? link.href)}
                  expanded={expanded}
                  onNavigate={onNavigate}
                  tipProps={tips.bind(link.label)}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>
      {tips.element}
    </div>
  );
}
