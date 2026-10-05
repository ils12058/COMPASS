"use client";

import { Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Image from "next/image";
import { useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { PrivacyNoticePrompt } from "@/features/account/privacy/privacy-notice-prompt";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { NotificationBell } from "@/features/notifications/components/notification-bell";
import { NotificationFreshness } from "@/features/notifications/notification-freshness";
import { MaintenanceNotice } from "@/features/platform/maintenance-presentation";
import { PortalNavigation } from "@/features/portal/components/portal-navigation";
import { PortalCommandPalette } from "@/features/portal/components/portal-command-palette";
import { PortalUserMenu } from "@/features/portal/components/portal-user-menu";
import { cn } from "@/lib/utils/cn";

const DOCK_NAVIGATION_ID = "portal-dock-navigation";

// The portal frame: a dock on wide screens, a drawer on small ones, a slim top bar for the account
// controls, and the workspace. The dock starts with its labels showing, and the icon button at the
// start of the top bar folds it to an icon rail and back. The choice lives here, so it holds while
// the reader moves between pages.
//
// The shell gives pages the full workspace width. A page that is not a collection, such as a form
// or a record, bounds its own width. `--portal-content-inset` is where the workspace starts, so
// controls that float over a page (FloatingListTools) center on the workspace, not the window.
export function PortalShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  // Labels show from the start; the reader can fold the dock to an icon rail for more room.
  const [dockExpanded, setDockExpanded] = useState(true);

  return (
    <div
      data-dock={dockExpanded ? "expanded" : "collapsed"}
      className={cn(
        "min-h-dvh bg-body lg:flex",
        "[--portal-content-inset:0px] [--portal-dock-width:4.75rem] data-[dock=expanded]:[--portal-dock-width:16rem] lg:[--portal-content-inset:var(--portal-dock-width)]",
      )}
    >
      <NotificationFreshness />
      {/* The first Tab stop on every portal page. It stays out of the layout while hidden, and
          following it moves focus past the navigation to the page content. */}
      <a
        href="#main-content"
        className="sr-only text-sm font-semibold text-brand focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:border focus:border-border-strong focus:bg-surface-raised focus:px-4 focus:py-3 focus:shadow-dialog focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Skip to main content
      </a>
      {/* The dock stays in view while long pages scroll; its destinations scroll on their own when
          they are taller than the screen. */}
      <aside className="sticky top-0 hidden h-dvh w-(--portal-dock-width) shrink-0 transition-[width] duration-200 ease-out lg:block">
        <PortalNavigation expanded={dockExpanded} navigationId={DOCK_NAVIGATION_ID} />
      </aside>

      <div className="min-w-0 flex-1">
        <header className="flex min-h-14 items-center justify-between gap-3 border-b border-border bg-surface-raised px-4 sm:px-6 lg:px-8">
          {/* The dock's own control stays outside its list of destinations. */}
          <button
            type="button"
            aria-expanded={dockExpanded}
            aria-controls={DOCK_NAVIGATION_ID}
            aria-label={dockExpanded ? "Collapse navigation" : "Expand navigation"}
            title={dockExpanded ? "Collapse navigation" : "Expand navigation"}
            onClick={() => setDockExpanded((current) => !current)}
            className="-ml-2 hidden min-h-11 min-w-11 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus lg:inline-flex"
          >
            {dockExpanded ? <PanelLeftClose size={20} aria-hidden="true" /> : <PanelLeftOpen size={20} aria-hidden="true" />}
          </button>
          <div className="flex min-w-0 items-center gap-2 lg:hidden">
            <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
              <DialogTrigger asChild>
                <button
                  type="button"
                  className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                  aria-label="Open portal navigation"
                >
                  <Menu size={21} aria-hidden="true" />
                </button>
              </DialogTrigger>
              <DialogContent
                className="left-0 top-[env(safe-area-inset-top)] h-[calc(100dvh-env(safe-area-inset-top)-env(safe-area-inset-bottom))] max-h-dvh w-[18rem] max-w-[85vw] translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-0 data-[state=closed]:animate-[portal-drawer-out_150ms_ease-in] data-[state=open]:animate-[portal-drawer-in_200ms_ease-out]"
                closeLabel="Close navigation"
                closeClassName="top-1.5 text-on-brand/80 hover:bg-on-brand/10 hover:text-on-brand focus-visible:ring-on-brand"
              >
                <DialogTitle className="sr-only">Portal navigation</DialogTitle>
                <PortalNavigation expanded onNavigate={() => setMobileOpen(false)} />
              </DialogContent>
            </Dialog>
            {/* Without the dock, the mark here keeps COMPASS and the way back to Overview in view. */}
            <GuardedPortalLink
              href="/portal"
              className="inline-flex min-h-11 items-center gap-2 rounded-md px-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              aria-label="COMPASS Portal Overview"
            >
              <Image src="/brand/compass-mark.svg" width={28} height={28} alt="" aria-hidden="true" />
              <span className="font-heading text-base font-bold tracking-[0.08em] text-brand-strong max-sm:sr-only">
                COMPASS
              </span>
            </GuardedPortalLink>
          </div>
          <div className="flex min-w-0 flex-1 justify-start">
            <PortalCommandPalette />
          </div>
          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            <AccessibilityControl placement="header" />
            <NotificationBell />
            <PortalUserMenu />
          </div>
        </header>

        {/* tabIndex lets the skip link move focus here in every browser; the region itself draws
            no focus ring, and the next Tab continues to the first control in the content. While a
            collection's floating list tools are on the page, the extra bottom space keeps its last
            records and pagination clear of them. */}
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto max-w-[96rem] px-4 py-5 focus:outline-none has-[[data-floating-list-tools]]:pb-(--list-tools-clearance) sm:px-6 lg:px-8 lg:py-6"
        >
          <MaintenanceNotice />
          {children}
        </main>
      </div>
      <PrivacyNoticePrompt />
    </div>
  );
}
