"use client";

import { CircleAlert, WifiOff, Wrench } from "lucide-react";
import { useEffect, useRef } from "react";

import type { ServiceStatusView } from "@/lib/system/service-status";

type BannerStatus =
  | Extract<ServiceStatusView, { kind: "maintenance_active" }>
  | Extract<ServiceStatusView, { kind: "offline" | "unavailable" }>;

export function ServiceStatusBanner({ status }: { status: BannerStatus }) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }

    const root = document.documentElement;
    const updateHeight = () => {
      root.style.setProperty(
        "--compass-status-banner-height",
        `${Math.ceil(element.getBoundingClientRect().height)}px`,
      );
      root.dataset.compassStatusBanner = "visible";
    };

    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(element);

    return () => {
      observer.disconnect();
      root.style.setProperty("--compass-status-banner-height", "0px");
      delete root.dataset.compassStatusBanner;
    };
  }, []);

  const isActive = status.kind === "maintenance_active";
  const isOffline = status.kind === "offline";
  const Icon = isActive ? Wrench : isOffline ? WifiOff : CircleAlert;

  let title = "We’re having trouble checking COMPASS right now.";
  let copy = "You can continue browsing while we check again shortly.";

  if (isActive) {
    title = "Maintenance is in progress";
    copy = "Some parts of COMPASS are temporarily unavailable.";
  } else if (isOffline) {
    title = "You’re offline";
    copy =
      "Check your connection. COMPASS will reconnect when your device is online again.";
  }

  return (
    <aside
      ref={ref}
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 bottom-0 z-50 border-t bg-card shadow-[0_-8px_24px_rgba(34,42,45,0.12)]"
    >
      <div className="mx-auto flex w-full max-w-7xl items-start gap-3 px-5 py-3 sm:px-8">
        <Icon
          aria-hidden="true"
          className="mt-0.5 size-5 shrink-0 text-[var(--compass-support-strong)]"
        />
        <div className="min-w-0">
          <p className="text-sm font-bold">{title}</p>
          <p className="mt-0.5 text-sm leading-6 text-muted-foreground">{copy}</p>
          {isActive ? (
            <p className="mt-1 text-sm leading-6 text-foreground/80">
              {status.message}
            </p>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
