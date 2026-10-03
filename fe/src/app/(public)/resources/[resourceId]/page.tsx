import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { pageBackLinkClass } from "@/components/ui/page-header";
import { ResourceDetail } from "@/features/public/resources/resource-detail";
import {
  isReaderUuid,
  resolveResourceReader,
} from "@/features/public/shared/server-reader";

const description = "Resource from the UCN Guidance and Counseling Office.";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}): Promise<Metadata> {
  const { resourceId } = await params;
  if (!isReaderUuid(resourceId)) {
    return {
      title: "Resource",
      description,
      robots: { index: false, follow: false },
    };
  }

  const resolution = await resolveResourceReader(resourceId);
  return {
    title: resolution.kind === "available" ? resolution.title : "Resource",
    description,
    robots:
      resolution.kind === "available" && resolution.indexable
        ? undefined
        : { index: false, follow: false },
  };
}

export default async function ResourceDetailPage({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}) {
  const { resourceId } = await params;
  if (!isReaderUuid(resourceId)) notFound();

  const resolution = await resolveResourceReader(resourceId);
  if (resolution.kind === "not-found") notFound();

  return (
    <main>
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 sm:py-9">
        <div className="max-w-4xl">
          <Link href="/resources" className={pageBackLinkClass}>
            Back to resources
          </Link>
          <ResourceDetail resourceId={resourceId} />
        </div>
      </div>
    </main>
  );
}
