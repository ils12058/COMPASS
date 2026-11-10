"use client";

import { ChevronDown, Ellipsis } from "lucide-react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState, type FocusEvent, type PointerEvent } from "react";

import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  portalNavigationGroups,
  type PortalWorkspaceLink,
} from "@/features/portal/components/portal-workspaces";
import {
  useNavigationAttention,
  type NavigationAttentionBadge,
} from "@/features/portal/components/portal-navigation-attention";
import { cn } from "@/lib/utils/cn";
import { useFacultyAvailability } from "@/features/faculty-referrals/availability";
import { facultyReferralsPath } from "@/features/faculty-referrals/access";

// Every dock destination keeps its icon in the same place whether or not its label shows, so the
// rail does not shift when it expands.
const itemClass =
  "flex min-h-11 w-full items-center gap-3 rounded-md px-4 text-sm transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand focus-visible:ring-offset-2 focus-visible:ring-offset-brand-strong";

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
      const dockRight = target.closest("aside")?.getBoundingClientRect().right ?? rect.right;
      setTip({ label, top: rect.top + rect.height / 2, left: Math.max(rect.right, dockRight) + 10 });
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
  badge,
}: {
  link: PortalWorkspaceLink;
  current: boolean;
  expanded: boolean;
  onNavigate?: () => void;
  tipProps: ReturnType<ReturnType<typeof useDockTips>["bind"]>;
  badge?: NavigationAttentionBadge | null;
}) {
  const Icon = link.icon;
  const ariaLabel = badge ? `${link.label}, ${badge.ariaDescription}` : undefined;

  return (
    <GuardedPortalLink
      href={link.href}
      onNavigate={onNavigate}
      aria-current={current ? "page" : undefined}
      aria-label={ariaLabel}
      className={cn(
        itemClass,
        // The current destination is a lit tile in the dock, not a stripe on its edge.
        current
          ? "bg-on-brand font-semibold text-brand-strong"
          : "font-medium text-on-brand/85 hover:bg-on-brand/10 hover:text-on-brand",
      )}
      {...tipProps}
    >
      <span className="relative inline-flex shrink-0">
        <Icon size={20} aria-hidden="true" className="shrink-0" />
        {!expanded && badge ? (
          <span
            aria-hidden="true"
            data-testid="nav-badge-collapsed"
            className={cn(
              "pointer-events-none absolute -right-2 -top-1.5 flex min-h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold leading-none shadow-xs",
              current ? "bg-brand-strong text-on-brand" : "bg-on-brand text-brand-strong",
            )}
          >
            {badge.display}
          </span>
        ) : null}
      </span>
      <span className={expanded ? "min-w-0 flex-1 break-words text-left" : "sr-only"}>{link.label}</span>
      {expanded && badge ? (
        <span
          aria-hidden="true"
          data-testid="nav-badge-expanded"
          className={cn(
            "ml-auto inline-flex min-h-5 min-w-5 shrink-0 items-center justify-center rounded-full px-1.5 text-xs font-semibold tabular-nums leading-none",
            current ? "bg-brand-strong text-on-brand" : "bg-on-brand/20 text-on-brand",
          )}
        >
          {badge.display}
        </span>
      ) : null}
    </GuardedPortalLink>
  );
}

// Keep native button disclosure behavior and the same guarded destination links in both shells.
function SecondaryNavigation({ label, links, activeHref, expanded, onNavigate, tips, attention }: {
  label: string;
  links: PortalWorkspaceLink[];
  activeHref?: string;
  expanded: boolean;
  onNavigate?: () => void;
  tips: ReturnType<typeof useDockTips>;
  attention: ReturnType<typeof useNavigationAttention>;
}) {
  const [open, setOpen] = useState(Boolean(activeHref));
  const contentId = useId();
  return (
    <div className="mt-2 border-t border-on-brand/15 pt-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        aria-label={`${label}, ${links.length} destinations`}
        onClick={() => setOpen(!open)}
        className={cn(itemClass, "font-medium text-on-brand/85 hover:bg-on-brand/10 hover:text-on-brand")}
        {...tips.bind(`${label} (${links.length})`)}
      >
        <Ellipsis size={20} aria-hidden="true" className="shrink-0" />
        <span className={expanded ? "min-w-0 flex-1 break-words text-left" : "sr-only"}>{label} ({links.length})</span>
        {expanded ? <ChevronDown size={16} aria-hidden="true" className={cn("shrink-0", open && "rotate-180")} /> : null}
      </button>
      <div id={contentId} hidden={!open} className="mt-1 space-y-1">
        {links.map((link) => (
          <NavItem key={link.href} link={link} current={link.href === activeHref}
            expanded={expanded} onNavigate={onNavigate} tipProps={tips.bind(link.label)} badge={attention.getBadge(link.href)} />
        ))}
      </div>
    </div>
  );
}

// Ordering follows the approved daily list only after the registry applies existing access gates.
export function PortalNavigation({ expanded, navigationId, onNavigate, className }: {
  expanded: boolean;
  navigationId?: string;
  onNavigate?: () => void;
  className?: string;
}) {
  const { user } = usePortalSession();
  const { availability } = useFacultyAvailability(user);
  const pathname = usePathname();
  const attention = useNavigationAttention(user);
  const { daily, secondary } = portalNavigationGroups(user, availability);
  const isCurrent = (link: PortalWorkspaceLink) => {
    if (!pathname) return false;
    if (link.href === "/portal") return pathname === "/portal";
    if (link.href === facultyReferralsPath) return pathname === facultyReferralsPath || (pathname.startsWith(facultyReferralsPath + "/") && !pathname.endsWith("/new"));
    const section = link.section ?? link.href;
    return pathname === section || pathname.startsWith(section + "/");
  };
  const activeSecondary = secondary.links.find(isCurrent)?.href;
  const tips = useDockTips(!expanded);
  const navRef = useRef<HTMLElement>(null);

  // A long dock scrolls on its own; also reveal a newly available current destination.
  useEffect(() => {
    navRef.current?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView({ block: "nearest" });
  }, [pathname, expanded, activeSecondary]);

  return (
    <div className={cn("flex h-full min-h-full flex-col bg-brand-strong text-on-brand", className)}>
      <GuardedPortalLink href="/portal" onNavigate={onNavigate}
        className="flex min-h-14 shrink-0 items-center gap-3 border-b border-on-brand/15 px-5.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-on-brand"
        aria-label="COMPASS Portal Home" {...tips.bind("COMPASS Home")}>
        <Image src="/brand/compass-mark.svg" width={32} height={32} alt="" aria-hidden="true" className="shrink-0" />
        <span aria-hidden="true" className={cn("font-heading text-lg font-bold tracking-[0.08em]", !expanded && "sr-only")}>COMPASS</span>
      </GuardedPortalLink>
      <nav ref={navRef} id={navigationId} aria-label="Portal navigation" onScroll={tips.clear}
        className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-3">
        <div className="space-y-1">
          {daily.map((link) => (
            <NavItem key={link.href} link={link} current={isCurrent(link)} expanded={expanded}
              onNavigate={onNavigate} tipProps={tips.bind(link.label)} badge={attention.getBadge(link.href)} />
          ))}
        </div>
        {secondary.links.length ? (
          <SecondaryNavigation key={`${user.id}:${pathname}:${activeSecondary ?? ""}`}
            label={secondary.label} links={secondary.links} activeHref={activeSecondary}
            expanded={expanded} onNavigate={onNavigate} tips={tips} attention={attention} />
        ) : null}
      </nav>
      {tips.element}
    </div>
  );
}
