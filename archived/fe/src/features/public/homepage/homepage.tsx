import { AnnouncementPreview } from "@/features/public/homepage/announcement-preview";
import { HomepageHero } from "@/features/public/homepage/homepage-hero";
import { HomepageStart } from "@/features/public/homepage/homepage-start";
import { OfficeContactSection } from "@/features/public/homepage/office-contact-section";
import { ResourcePreview } from "@/features/public/homepage/resource-preview";

export function Homepage() {
  return (
    <>
      <HomepageHero />
      <HomepageStart />
      <AnnouncementPreview />
      <section className="mx-auto w-full max-w-7xl px-5 py-12 sm:px-8">
        <div className="grid gap-6 rounded-2xl border bg-card p-7 sm:p-9 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <p className="text-sm font-semibold text-[var(--compass-brand-gold)]">Guidance support</p>
            <h2 className="mt-1 font-heading text-3xl font-bold">A clearer path to office services</h2>
            <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
              COMPASS brings Guidance and Counseling Office access into one university platform.
              Public pages explain the basics; signed-in users can view the services and actions
              available to their account.
            </p>
          </div>
        </div>
      </section>
      <ResourcePreview />
      <OfficeContactSection />
    </>
  );
}
