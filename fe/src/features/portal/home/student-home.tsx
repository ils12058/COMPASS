import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { Panel, PanelHeader } from "@/components/ui/panel";
import { OverviewAnnouncements } from "@/features/portal/home/overview-announcements";
import { StudentHomeAttention } from "@/features/portal/home/student-home-attention";
import { getStudentHomeDestinations } from "@/features/portal/home/student-home-presentation";
import type { OverviewAttentionData } from "@/features/portal/home/overview-work";
import type { UserSummary } from "@/lib/api/generated/model";

export function StudentHome({ user, attention, summary }: {
  user: UserSummary;
  attention: OverviewAttentionData;
  summary: ReactNode;
}) {
  const destinations = getStudentHomeDestinations(user);
  return (
    <div className="@container grid gap-5">
      <StudentHomeAttention data={attention} />
      <div className="grid items-start gap-5 @min-[58rem]:grid-cols-[minmax(0,1fr)_minmax(0,21rem)]">
        {destinations.length > 0 ? (
          <Panel className="@container border-0 bg-transparent [overflow-wrap:anywhere]" aria-labelledby="student-home-services-heading">
            <PanelHeader className="border-border px-0 sm:px-0" title="Guidance services" titleId="student-home-services-heading" />
            <ul className="grid @min-[32rem]:grid-cols-2">
              {destinations.map((destination) => (
                <li key={destination.href} className="border-t border-border first:border-t-0 @min-[32rem]:even:border-l @min-[32rem]:even:[&>a]:pl-4 @min-[32rem]:[&:nth-child(2)]:border-t-0">
                  <Link href={destination.href} className="group flex min-h-11 items-center justify-between gap-3 py-3 pr-3 text-sm transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus">
                    <span className="min-w-0">
                      <span className="block font-semibold text-brand group-hover:underline">{destination.label}</span>
                    </span>
                    <ArrowRight aria-hidden="true" className="h-4 w-4 shrink-0" />
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
        ) : null}
        {summary}
      </div>
      <OverviewAnnouncements />
    </div>
  );
}
