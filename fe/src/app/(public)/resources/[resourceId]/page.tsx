import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

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
    <main className="bg-surface">
      <div className="mx-auto max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
        <Link href="/resources" className="mb-7 inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Back to resources
        </Link>
        <ResourceDetail resourceId={resourceId} />
      </div>
    </main>
  );
}
