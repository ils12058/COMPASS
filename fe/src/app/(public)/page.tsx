import { AnnouncementPreview } from "@/features/public/announcements/announcement-preview";
import { PublicHero } from "@/features/public/home/public-hero";
import { QuickAccess } from "@/features/public/home/quick-access";
import { ResourcePreview } from "@/features/public/resources/resource-preview";

export default function HomePage() {
  return (
    <main>
      <PublicHero />
      {/* Below the introduction, the office's current information in clearly bounded regions:
          announcements and resources in the main column, service entry points beside them. On
          phones, quick access follows the announcements. When an account has no shortcuts the
          panel is absent and the main column takes the full width. */}
      <div className="mx-auto grid max-w-6xl items-start gap-5 px-5 py-7 sm:px-8 sm:py-9 lg:has-[[data-quick-access]]:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <AnnouncementPreview />
        <QuickAccess className="lg:col-start-2 lg:row-span-2 lg:row-start-1" />
        <ResourcePreview />
      </div>
    </main>
  );
}
