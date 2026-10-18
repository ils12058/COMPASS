"use client";

import { GroupSessionsHeading } from "./group-sessions-shared";
import { Panel } from "@/components/ui/panel";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { ServiceGroupSessionsStudentPanel } from "@/features/services/service-group-sessions-panel";

export function GroupSessionsDiscoveryPage() {
  const { user } = usePortalSession();
  if (
    user.role !== "STUDENT" ||
    !user.capabilities.includes("appointments.view_self")
  ) {
    return (
      <WorkspaceUnavailable title="Group Sessions unavailable">
        Group Session discovery is available through Student scheduling access.
      </WorkspaceUnavailable>
    );
  }

  return (
    <>
      <GroupSessionsHeading />
      <Panel aria-label="Upcoming Group Sessions & Workshops">
        <ServiceGroupSessionsStudentPanel />
      </Panel>
    </>
  );
}
