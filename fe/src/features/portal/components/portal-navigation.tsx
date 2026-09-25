"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

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

function NavItem({
  href,
  current,
  onNavigate,
  children,
}: {
  href: string;
  current: boolean;
  onNavigate?: () => void;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={current ? "page" : undefined}
      className={
        "mt-2 flex min-h-11 items-center rounded-md px-3 text-sm font-semibold text-on-brand first:mt-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand " +
        (current ? "bg-on-brand/12" : "hover:bg-on-brand/10")
      }
    >
      {children}
    </Link>
  );
}

function NavSection({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <div className="mt-7 border-t border-on-brand/15 pt-5">
      {label ? (
        <p className="px-3 text-xs font-semibold uppercase tracking-wider text-on-brand/70">
          {label}
        </p>
      ) : null}
      {children}
    </div>
  );
}

export function PortalNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const isWithin = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");
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
  const hasRoutineInterviews = getRoutineInterviewAccess(user).hasWorkspace;
  const hasCounseling = getCounselingAccess(user).hasWorkspace;
  const hasReferrals = getReferralAccess(user).hasWorkspace;
  const hasCallSlips = getCallSlipAccess(user).hasWorkspace;
  const hasFeedback = getFeedbackAccess(user).hasWorkspace;
  const hasGoodMoral = getGoodMoralAccess(user).hasWorkspace;
  const hasExitInterviews = getExitInterviewAccess(user).hasWorkspace;
  const hasGraduateTracer = getGraduateTracerAccess(user).hasWorkspace;
  const hasGuidanceServices =
    hasServices ||
    hasAvailability ||
    hasAppointments ||
    hasInventory ||
    hasRoutineInterviews ||
    hasExitInterviews ||
    hasGraduateTracer ||
    hasCounseling ||
    hasReferrals ||
    hasCallSlips ||
    hasGoodMoral ||
    hasFeedback;
  const hasPlatformOperations = user.capabilities.includes(
    "platform_operations.view",
  );
  const hasReports = canAttemptReports(user);

  const guidanceLinks: { href: string; label: string; visible: boolean }[] = [
    { href: "/portal/services", label: "Services", visible: hasServices },
    { href: "/portal/appointments", label: "Appointments", visible: hasAppointments },
    { href: "/portal/availability", label: "Availability", visible: hasAvailability },
    { href: "/portal/inventory", label: "Individual Inventory", visible: hasInventory },
    { href: "/portal/routine-interviews", label: "Routine Interviews", visible: hasRoutineInterviews },
    { href: "/portal/exit-interviews", label: "Exit Interviews", visible: hasExitInterviews },
    { href: "/portal/graduate-tracer", label: "Graduate Tracer", visible: hasGraduateTracer },
    { href: "/portal/counseling", label: "Counseling", visible: hasCounseling },
    { href: "/portal/referrals", label: "Referrals", visible: hasReferrals },
    { href: "/portal/call-slips", label: "Call Slips", visible: hasCallSlips },
    { href: "/portal/good-moral", label: "Good Moral", visible: hasGoodMoral },
    { href: "/portal/feedback", label: "Feedback", visible: hasFeedback },
  ];

  return (
    <div className="flex min-h-full flex-col bg-brand-strong text-on-brand">
      <Link
        href="/portal"
        onClick={onNavigate}
        className="flex min-h-18 items-center gap-3 border-b border-on-brand/15 px-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand"
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
      </Link>
      <nav aria-label="Portal navigation" className="p-3">
        <NavItem href="/portal" current={pathname === "/portal"} onNavigate={onNavigate}>
          Overview
        </NavItem>
        {canManageAccounts ? (
          <NavSection label="Identity & Access">
            <NavItem href="/portal/accounts" current={isWithin("/portal/accounts")} onNavigate={onNavigate}>
              Accounts
            </NavItem>
          </NavSection>
        ) : null}
        {hasInstitution ? (
          <NavSection label="Institution">
            {hasOrganization ? (
              <NavItem href="/portal/organization" current={isWithin("/portal/organization")} onNavigate={onNavigate}>
                Organization
              </NavItem>
            ) : null}
            {hasAcademicYears ? (
              <NavItem href="/portal/academic-years" current={isWithin("/portal/academic-years")} onNavigate={onNavigate}>
                Academic Years
              </NavItem>
            ) : null}
            {hasInstitutionalForms ? (
              <NavItem href="/portal/institutional-forms" current={isWithin("/portal/institutional-forms")} onNavigate={onNavigate}>
                Institutional Forms
              </NavItem>
            ) : null}
          </NavSection>
        ) : null}
        {hasGuidanceServices ? (
          <NavSection label="Guidance Services">
            {guidanceLinks
              .filter((link) => link.visible)
              .map((link) => (
                <NavItem key={link.href} href={link.href} current={isWithin(link.href)} onNavigate={onNavigate}>
                  {link.label}
                </NavItem>
              ))}
          </NavSection>
        ) : null}
        {hasReports ? (
          <NavSection>
            <NavItem href="/portal/reports" current={isWithin("/portal/reports")} onNavigate={onNavigate}>
              Reports
            </NavItem>
          </NavSection>
        ) : null}
        {hasPlatformOperations ? (
          <NavSection label="Platform">
            <NavItem href="/portal/platform/health" current={isWithin("/portal/platform")} onNavigate={onNavigate}>
              Platform Operations
            </NavItem>
          </NavSection>
        ) : null}
      </nav>
    </div>
  );
}
