"use client";

import Link from "next/link";

import {
  ContentDetailSkeleton,
  ContentNotice,
  ContentPageHeading,
  PublicationStatusBadge,
} from "@/features/content/content-shared";
import { ResourceUnavailable } from "@/features/resources/resource-detail-page";
import { shouldHideResourceData } from "@/features/resources/resource-errors";
import { ResourceForm } from "@/features/resources/resource-form";
import { useResourcesGetManaged } from "@/lib/api/generated/resources/resources";
import { ResourceStatusValue } from "@/lib/api/generated/model";

export function ResourceEditPage({ resourceId }: { resourceId: string }) {
  const detail = useResourcesGetManaged(resourceId, { query: { retry: false } });
  const backHref = `/portal/resources/${resourceId}`;

  if (detail.isPending) return <ContentDetailSkeleton label="Loading Resource…" />;
  // A failed refresh keeps the form; its unsaved text stays in place.
  if (!detail.data || (detail.isError && shouldHideResourceData(detail.error))) {
    return <ResourceUnavailable error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  const item = detail.data.data;

  return (
    <section>
      <ContentPageHeading title="Edit Resource" backHref={backHref} backLabel="Back to Resource">
        <div className="mt-3">
          <PublicationStatusBadge status={item.status} />
        </div>
      </ContentPageHeading>

      {item.status === ResourceStatusValue.ARCHIVED ? (
        <div className="mt-6 space-y-4">
          <ContentNotice tone="info">Archived Resources cannot be edited.</ContentNotice>
          <Link href={backHref} className="text-sm font-semibold text-brand underline">
            View the Resource
          </Link>
        </div>
      ) : (
        <>
          {item.status === ResourceStatusValue.PUBLISHED ? (
            <div className="mt-6">
              <ContentNotice tone="info">
                This Resource is published. Saved changes are visible to readers immediately.
              </ContentNotice>
            </div>
          ) : null}
          <ResourceForm key={item.id} resource={item} />
        </>
      )}
    </section>
  );
}
