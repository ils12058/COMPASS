"use client";

import { ContentPageHeading } from "@/features/content/content-shared";
import { ResourceForm } from "@/features/resources/resource-form";

export function ResourceCreatePage() {
  return (
    <section>
      <ContentPageHeading title="Create Resource" backHref="/portal/resources" backLabel="Resources">
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
          New Resources are saved as drafts. Readers see a Resource only after it is published.
        </p>
      </ContentPageHeading>
      <ResourceForm resource={null} />
    </section>
  );
}
