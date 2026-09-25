"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { hasAvailabilityWorkspace } from "@/features/availability/availability-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { canAttemptReports } from "@/features/reports/reports-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import {
  canManageOrganization,
  canViewAcademicYears,
  canViewInstitutionalForms,
  canViewOrganization,
  hasInstitutionWorkspace,
} from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function PortalNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const canManageAccounts = user.capabilities.includes("accounts.manage");
  const hasOrganization =
    canViewOrganization(user) || canManageOrganization(user);
  const hasAcademicYears = canViewAcademicYears(user);
  const hasInstitutionalForms = canViewInstitutionalForms(user);
  const hasInstitution = hasInstitutionWorkspace(user);
  const hasServices = user.capabilities.includes("services.view");
  const hasAvailability = hasAvailabilityWorkspace(user);
  const hasAppointments = getAppointmentAccess(user).hasWorkspace;
  const hasInventory = getInventoryAccess(user).hasWorkspace;
  const routineAccess = getRoutineInterviewAccess(user);
  const hasCounseling = getCounselingAccess(user).hasWorkspace;
  const referralAccess = getReferralAccess(user);
  const callSlipAccess = getCallSlipAccess(user);
  const feedbackAccess = getFeedbackAccess(user);
  const goodMoralAccess = getGoodMoralAccess(user);
  const exitInterviewAccess = getExitInterviewAccess(user);
  const graduateTracerAccess = getGraduateTracerAccess(user);
  const hasGuidanceServices =
    hasServices ||
    hasAvailability ||
    hasAppointments ||
    hasInventory ||
    routineAccess.hasWorkspace ||
    exitInterviewAccess.hasWorkspace ||
    graduateTracerAccess.hasWorkspace ||
    hasCounseling ||
    referralAccess.hasWorkspace ||
    callSlipAccess.hasWorkspace ||
    goodMoralAccess.hasWorkspace ||
    feedbackAccess.hasWorkspace;
  const hasPlatformOperations = user.capabilities.includes(
    "platform_operations.view",
  );
  const hasReports = canAttemptReports(user);

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
        {hasInstitution ? (
          <div className="mt-7 border-t border-on-brand/15 pt-5">
            <p className="px-3 text-xs font-semibold uppercase tracking-wider text-on-brand/70">
              Institution
            </p>
            {hasOrganization ? (
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
            ) : null}
            {hasAcademicYears ? (
              <Link
                href="/portal/academic-years"
                onClick={onNavigate}
                aria-current={
                  pathname === "/portal/academic-years" ? "page" : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname === "/portal/academic-years"
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Academic Years
              </Link>
            ) : null}
            {hasInstitutionalForms ? (
              <Link
                href="/portal/institutional-forms"
                onClick={onNavigate}
                aria-current={
                  pathname === "/portal/institutional-forms"
                    ? "page"
                    : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname === "/portal/institutional-forms"
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Institutional Forms
              </Link>
            ) : null}
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
            {hasInventory ? (
              <Link
                href="/portal/inventory"
                onClick={onNavigate}
                aria-current={
                  pathname.startsWith("/portal/inventory") ? "page" : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/inventory")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Individual Inventory
              </Link>
            ) : null}
            {routineAccess.hasWorkspace ? (
              <Link
                href="/portal/routine-interviews"
                onClick={onNavigate}
                aria-current={
                  pathname.startsWith("/portal/routine-interviews")
                    ? "page"
                    : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/routine-interviews")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Routine Interviews
              </Link>
            ) : null}
            {exitInterviewAccess.hasWorkspace ? (
              <Link
                href="/portal/exit-interviews"
                onClick={onNavigate}
                aria-current={
                  pathname.startsWith("/portal/exit-interviews") ? "page" : undefined
                }
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/exit-interviews")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Exit Interviews
              </Link>
            ) : null}
            {graduateTracerAccess.hasWorkspace ? (
              <Link
                href="/portal/graduate-tracer"
                onClick={onNavigate}
                aria-current={pathname.startsWith("/portal/graduate-tracer") ? "page" : undefined}
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/graduate-tracer") ? "bg-on-brand/12" : "hover:bg-on-brand/10")
                }
              >
                Graduate Tracer
              </Link>
            ) : null}
            {hasCounseling ? (
              <Link
                href="/portal/counseling"
                onClick={onNavigate}
                aria-current={pathname.startsWith("/portal/counseling") ? "page" : undefined}
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/counseling") ? "bg-on-brand/12" : "hover:bg-on-brand/10")
                }
              >
                Counseling
              </Link>
            ) : null}
            {referralAccess.hasWorkspace ? (
              <Link
                href="/portal/referrals"
                onClick={onNavigate}
                aria-current={pathname.startsWith("/portal/referrals") ? "page" : undefined}
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/referrals")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Referrals
              </Link>
            ) : null}
            {callSlipAccess.hasWorkspace ? (
              <Link
                href="/portal/call-slips"
                onClick={onNavigate}
                aria-current={pathname.startsWith("/portal/call-slips") ? "page" : undefined}
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/call-slips")
                    ? "bg-on-brand/12"
                    : "hover:bg-on-brand/10")
                }
              >
                Call Slips
              </Link>
            ) : null}
            {goodMoralAccess.hasWorkspace ? (
              <Link
                href="/portal/good-moral"
                onClick={onNavigate}
                aria-current={pathname.startsWith("/portal/good-moral") ? "page" : undefined}
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/good-moral") ? "bg-on-brand/12" : "hover:bg-on-brand/10")
                }
              >
                Good Moral
              </Link>
            ) : null}
            {feedbackAccess.hasWorkspace ? (
              <Link
                href="/portal/feedback"
                onClick={onNavigate}
                aria-current={pathname.startsWith("/portal/feedback") ? "page" : undefined}
                className={
                  "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                  (pathname.startsWith("/portal/feedback") ? "bg-on-brand/12" : "hover:bg-on-brand/10")
                }
              >
                Feedback
              </Link>
            ) : null}
          </div>
        ) : null}
        {hasReports ? (
          <div className="mt-7 border-t border-on-brand/15 pt-5">
            <Link
              href="/portal/reports"
              onClick={onNavigate}
              aria-current={
                pathname.startsWith("/portal/reports") ? "page" : undefined
              }
              className={
                "flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
                (pathname.startsWith("/portal/reports")
                  ? "bg-on-brand/12"
                  : "hover:bg-on-brand/10")
              }
            >
              Reports
            </Link>
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
