"use client";

import { Menu } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { NotificationBell } from "@/features/notifications/components/notification-bell";
import { PublicMaintenanceNotice } from "@/features/platform/platform-public-maintenance-notice";
import { PortalNavigation } from "@/features/portal/components/portal-navigation";
import { PortalUserMenu } from "@/features/portal/components/portal-user-menu";

export function PortalShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-dvh bg-body lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      {/* The first Tab stop on every portal page. It stays out of the grid while hidden, and
          following it moves focus past the navigation to the page content. */}
      <a
        href="#main-content"
        className="sr-only text-sm font-semibold text-brand focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:border focus:border-border-strong focus:bg-surface-raised focus:px-4 focus:py-3 focus:shadow-dialog focus:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Skip to main content
      </a>
      <aside className="hidden bg-brand-strong lg:block">
        {/* The menu stays in view while long pages scroll, and scrolls on its own when it is
            taller than the screen. */}
        <div className="sticky top-0 h-dvh">
          <PortalNavigation />
        </div>
      </aside>

      <div className="min-w-0">
        <header className="flex min-h-18 items-center justify-between gap-4 border-b border-border bg-surface-raised px-4 sm:px-6 lg:justify-end lg:px-8">
          <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
            <DialogTrigger asChild>
              <button
                type="button"
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md border border-border bg-surface-raised text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus lg:hidden"
                aria-label="Open portal navigation"
              >
                <Menu size={21} aria-hidden="true" />
              </button>
            </DialogTrigger>
            <DialogContent
              className="left-0 top-0 h-dvh max-h-dvh w-[18rem] max-w-[85vw] translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-0 data-[state=closed]:animate-[portal-drawer-out_150ms_ease-in] data-[state=open]:animate-[portal-drawer-in_200ms_ease-out]"
              closeLabel="Close navigation"
              closeClassName="top-3.5 text-on-brand/80 hover:bg-on-brand/10 hover:text-on-brand focus-visible:ring-on-brand"
            >
              <DialogTitle className="sr-only">Portal navigation</DialogTitle>
              <PortalNavigation onNavigate={() => setMobileOpen(false)} />
            </DialogContent>
          </Dialog>
          <div className="flex shrink-0 items-center gap-2">
            <AccessibilityControl placement="header" />
            <NotificationBell />
            <PortalUserMenu />
          </div>
        </header>

        {/* tabIndex lets the skip link move focus here in every browser; the region itself draws
            no focus ring, and the next Tab continues to the first control in the content. */}
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto max-w-6xl px-5 py-7 focus:outline-none sm:px-8 sm:py-9"
        >
          <PublicMaintenanceNotice />
          {children}
        </main>
      </div>
    </div>
  );
}
