import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Panel, PanelHeader } from "@/components/ui/panel";
import { publicPanelLinkClass } from "@/features/public/announcements/announcement-preview";
import { ResourceList } from "@/features/public/resources/resource-list";

export function ResourcePreview() {
  return (
    <Panel aria-labelledby="guidance-resources">
      <PanelHeader
        title="Guidance resources"
        titleId="guidance-resources"
        actions={
          <Link href="/resources" className={publicPanelLinkClass}>
            Browse resources
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        }
      />
      <ResourceList mode="preview" />
    </Panel>
  );
}
