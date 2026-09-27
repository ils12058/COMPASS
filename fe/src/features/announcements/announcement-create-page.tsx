"use client";

import { AnnouncementForm } from "@/features/announcements/announcement-form";
import { ContentPageHeading } from "@/features/content/content-shared";

export function AnnouncementCreatePage() {
  return (
    <section>
      <ContentPageHeading title="Create Announcement" backHref="/portal/announcements" backLabel="Announcements">
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          New Announcements are saved as drafts. Readers see an Announcement only after it is published.
        </p>
      </ContentPageHeading>
      <AnnouncementForm announcement={null} />
    </section>
  );
}
