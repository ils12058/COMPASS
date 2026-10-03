"use client";

import { AnnouncementForm } from "@/features/announcements/announcement-form";
import { ContentPageHeading } from "@/features/content/content-shared";

export function AnnouncementCreatePage() {
  return (
    <section>
      <ContentPageHeading title="Create Announcement" backHref="/portal/announcements" backLabel="Announcements">
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          New announcements are saved as drafts. Readers can see them after they are published.
        </p>
      </ContentPageHeading>
      <AnnouncementForm announcement={null} />
    </section>
  );
}
