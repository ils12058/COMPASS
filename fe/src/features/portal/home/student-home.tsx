import type { ReactNode } from "react";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import { StudentHomeAttention } from "@/features/portal/home/student-home-attention";
import { getStudentHomeDestinations } from "@/features/portal/home/student-home-presentation";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";
import type { UserSummary } from "@/lib/api/generated/model";
import { HomeShortcuts } from "./home-shortcuts";

export function StudentHome({ user, attention, summary }: {
  user: UserSummary; attention: OverviewAttentionData; summary: ReactNode;
}) {
  return <div className="@container grid min-w-0 gap-5">
    <StudentHomeAttention data={attention} />
    <div className="grid min-w-0 items-start gap-5 @min-[52rem]:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <HomeShortcuts title="Guidance services" titleId="student-home-services-heading" destinations={getStudentHomeDestinations(user)} />
      {summary}
    </div>
    <OverviewAnnouncements />
  </div>;
}
