"use client";

import { Panel } from "@/components/ui/panel";
import { ServiceGroupSessionsStaffPanel } from "@/features/services/service-group-sessions-panel";
import { GroupSessionsGate, GroupSessionsHeading } from "./group-sessions-shared";

export function GroupSessionsStaffPage({ attendance = false }: { attendance?: boolean }) {
  return <GroupSessionsGate staff><GroupSessionsHeading /><Panel>
    <ServiceGroupSessionsStaffPanel attendanceOnly={attendance} />
  </Panel></GroupSessionsGate>;
}
