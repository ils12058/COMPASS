import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { ResourceList } from "@/features/public/resources/resource-list";

export function ResourcePreview() {
  return (
    <section aria-labelledby="guidance-resources" className="bg-surface-muted">
      <div className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-18">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <h2 id="guidance-resources" className="font-heading text-3xl font-bold tracking-tight text-ink">
            Guidance resources
          </h2>
          <Link
            href="/resources"
            className="inline-flex min-h-10 items-center gap-2 rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Browse resources
            <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
        <ResourceList mode="preview" />
      </div>
    </section>
  );
}
