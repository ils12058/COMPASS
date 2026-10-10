import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Panel, PanelHeader } from "@/components/ui/panel";
import { AnnouncementList } from "@/features/public/announcements/announcement-list";

export const publicPanelLinkClass =
  "inline-flex min-h-10 items-center gap-1.5 rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function AnnouncementPreview() {
  return (
    <Panel aria-labelledby="latest-announcements">
      <PanelHeader
        title="Latest announcements"
        titleId="latest-announcements"
        actions={
          <Link href="/announcements" className={publicPanelLinkClass}>
            View all announcements
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        }
      />
      <AnnouncementList mode="preview" />
    </Panel>
  );
}
