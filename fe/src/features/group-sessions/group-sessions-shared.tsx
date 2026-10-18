"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { ContextHelp } from "@/components/ui/context-help";
import { PageHeader } from "@/components/ui/page-header";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { canBrowseGroupSessions, canManageGroupSessions, hasGroupSessionsWorkspace } from "./group-sessions-access";
import { CompassApiError } from "@/lib/api/errors";

export function groupSessionsError(error: unknown, fallback: string) {
  if (error instanceof CompassApiError) {
    if (error.status === 401) return "Your session has expired. Sign in again to continue.";
    if (error.status === 403) return "You don’t have access to this Group Sessions view.";
    if (error.status === 404) return "This group session is no longer available.";
    if (error.status === 503) return "Group Sessions are temporarily unavailable. Try again shortly.";
  }
  return fallback;
}

export function GroupSessionsHelp() {
  const { user } = usePortalSession();
  const student = canBrowseGroupSessions(user);
  return <ContextHelp title="Group Sessions" sections={student ? [
    { heading: "Browse and register", content: <p>Browse published sessions and open their details. Registration depends on your eligibility, the registration window, available seats, and other bookings. Any restriction appears beside the session.</p> },
    { heading: "Your registrations", content: <p>My Registrations includes upcoming and past sessions, cancellations, and recorded attendance. Return to Browse Sessions to cancel an upcoming registration when available.</p> },
  ] : [
    { heading: "Manage sessions", content: <p>Schedule a draft under an active Service that offers Group Sessions. Review the schedule, capacity, registration window and facilitators before publishing. Complete a published session after it ends, or cancel it with a reason.</p> },
    { heading: "Registrations and attendance", content: <p>Select a session to open its roster and record attendance. Only sessions and participant actions available to you appear. Withdrawing a draft keeps its record.</p> },
  ]} />;
}

export function GroupSessionsNavigation() {
  const { user } = usePortalSession();
  const path = usePathname();
  const tabs = canBrowseGroupSessions(user) ? [
    ["/portal/group-sessions/discover", "Browse Sessions"],
    ["/portal/group-sessions/my", "My Registrations"],
  ] : [
    ["/portal/group-sessions/manage", "Manage Sessions"],
    ["/portal/group-sessions/attendance", "Registrations & Attendance"],
  ];
  return <WorkspaceTabs label="Group Sessions navigation">{tabs.map(([href, label]) =>
    <Link key={href} href={href} className={workspaceTabClass(path === href)} aria-current={path === href ? "page" : undefined}>{label}</Link>
  )}</WorkspaceTabs>;
}

export function GroupSessionsHeading() {
  return <><PageHeader title="Group Sessions" help={<GroupSessionsHelp />} /><GroupSessionsNavigation /></>;
}

export function GroupSessionsGate({ children, staff = false }: { children: ReactNode; staff?: boolean }) {
  const { user } = usePortalSession();
  const allowed = staff ? canManageGroupSessions(user) : hasGroupSessionsWorkspace(user);
  return allowed ? children : <WorkspaceUnavailable title="Group Sessions unavailable">You don’t have access to this Group Sessions view.</WorkspaceUnavailable>;
}

export function GroupSessionsIndex() {
  const { user } = usePortalSession();
  const router = useRouter();
  const destination = canBrowseGroupSessions(user) ? "/portal/group-sessions/discover" : canManageGroupSessions(user) ? "/portal/group-sessions/manage" : "/portal";
  useEffect(() => { router.replace(destination); }, [destination, router]);
  return <div aria-busy="true"><Skeleton className="h-10 w-64" /><p className="sr-only">Opening Group Sessions…</p></div>;
}
