"use client";

import { Menu } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { NotificationBell } from "@/features/notifications/components/notification-bell";
import { PublicMaintenanceNotice } from "@/features/platform/platform-public-maintenance-notice";
import { PortalNavigation } from "@/features/portal/components/portal-navigation";
import { PortalUserMenu } from "@/features/portal/components/portal-user-menu";

export function PortalShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-dvh bg-body lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="hidden min-h-dvh lg:block">
        <PortalNavigation />
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
            <DialogContent className="left-0 top-0 h-dvh max-h-dvh w-[18rem] max-w-[85vw] translate-x-0 translate-y-0 rounded-none border-y-0 border-l-0 p-0">
              <DialogTitle className="sr-only">Portal navigation</DialogTitle>
              <PortalNavigation onNavigate={() => setMobileOpen(false)} />
            </DialogContent>
          </Dialog>
          <div className="flex shrink-0 items-center gap-2">
            <NotificationBell />
            <PortalUserMenu />
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-12">
          <PublicMaintenanceNotice />
          {children}
        </main>
      </div>
    </div>
  );
}
