import { AnnouncementPreview } from "@/features/public/announcements/announcement-preview";
import { PublicHero } from "@/features/public/home/public-hero";
import { ResourcePreview } from "@/features/public/resources/resource-preview";

export default function HomePage() {
  return (
    <main>
      <PublicHero />
      <AnnouncementPreview />
      <ResourcePreview />
    </main>
  );
}
