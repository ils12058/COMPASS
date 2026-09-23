"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { hasAvailabilityWorkspace } from "@/features/availability/availability-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function PortalNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const canManageAccounts = user.capabilities.includes("accounts.manage");
  const hasOrganization =
    user.capabilities.includes("organization.view") ||
    user.capabilities.includes("organization.manage");
  const hasServices = user.capabilities.includes("services.view");
  const hasAvailability = hasAvailabilityWorkspace(user);
  const hasAppointments = getAppointmentAccess(user).hasWorkspace;
  const hasGuidanceServices = hasServices || hasAvailability || hasAppointments;
  const hasPlatformOperations = user.capabilities.includes(
    "platform_operations.view",
  );

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
          className={
            "flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
            (pathname === "/portal"
              ? "bg-on-brand/12"
              : "hover:bg-on-brand/10")
          }
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
              className={
                "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                (pathname.startsWith("/portal/accounts")
                  ? "bg-on-brand/12"
                  : "hover:bg-on-brand/10")
              }
            >
              Accounts
            </Link>
          </div>
        ) : null}
        {hasOrganization ? (
          <div className="mt-7 border-t border-on-brand/15 pt-5">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-on-brand/70">
              Institution
            </p>
            <Link
              href="/portal/organization"
              onClick={onNavigate}
              aria-current={
                pathname.startsWith("/portal/organization")
                  ? "page"
                  : undefined
              }
              className={
                "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                (pathname.startsWith("/portal/organization")
                  ? "bg-on-brand/12"
                  : "hover:bg-on-brand/10")
              }
            >
              Organization
            </Link>
          </div>
        ) : null}
        {hasGuidanceServices ? (
          <div className="mt-7 border-t border-on-brand/15 pt-5">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-on-brand/70">
              Guidance Services
            </p>
            {hasServices ? (
              <Link
                href="/portal/services"
                onClick={onNavigate}
                aria-current={
                  pathname.startsWith("/portal/services")
                    ? "page"
                    : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/services")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Services
              </Link>
            ) : null}
            {hasAppointments ? (
              <Link
                href="/portal/appointments"
                onClick={onNavigate}
                aria-current={
                  pathname.startsWith("/portal/appointments") ? "page" : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/appointments")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Appointments
              </Link>
            ) : null}
            {hasAvailability ? (
              <Link
                href="/portal/availability"
                onClick={onNavigate}
                aria-current={
                  pathname.startsWith("/portal/availability")
                    ? "page"
                    : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/availability")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Availability
              </Link>
            ) : null}
          </div>
        ) : null}
        {hasPlatformOperations ? (
          <div className="mt-7 border-t border-on-brand/15 pt-5">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-on-brand/70">
              Platform
            </p>
            <Link
              href="/portal/platform/health"
              onClick={onNavigate}
              aria-current={
                pathname.startsWith("/portal/platform") ? "page" : undefined
              }
              className={
                "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                (pathname.startsWith("/portal/platform")
                  ? "bg-on-brand/12"
                  : "hover:bg-on-brand/10")
              }
            >
              Platform Operations
            </Link>
          </div>
        ) : null}
      </nav>
    </div>
  );
}
