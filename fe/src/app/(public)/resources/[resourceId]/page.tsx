import type { Metadata } from "next";
import Link from "next/link";

import { ResourceDetail } from "@/features/public/resources/resource-detail";

export const metadata: Metadata = { title: "Resource" };

export default async function ResourceDetailPage({
  params,
}: {
  params: Promise<{ resourceId: string }>;
}) {
  const { resourceId } = await params;

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
