import { ExternalLink, FileText, Newspaper } from "lucide-react";
import Link from "next/link";

import type { ResourceReaderResponse } from "@/lib/api/generated/model";
import { formatPublicDate, labelFromEnum } from "@/features/public/utils";

const KIND_ICON = {
  ARTICLE: Newspaper,
  EXTERNAL_LINK: ExternalLink,
  FILE: FileText,
} as const;

export function ResourceCard({
  resource,
  compact = false,
}: {
  resource: ResourceReaderResponse;
  compact?: boolean;
}) {
  const Icon = KIND_ICON[resource.kind];

  return (
    <article className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
        <Icon aria-hidden="true" className="size-4 text-[var(--compass-support-strong)]" />
        <span>{labelFromEnum(resource.kind)}</span>
        <span aria-hidden="true">·</span>
        <span>{labelFromEnum(resource.category)}</span>
      </div>
      <h2 className={compact ? "font-heading text-lg font-bold" : "font-heading text-xl font-bold"}>
        <Link href={`/resources/${resource.id}`} className="no-underline hover:underline">
          {resource.title}
        </Link>
      </h2>
      <p className="mt-2 text-xs text-muted-foreground">
        Published {formatPublicDate(resource.published_at)}
      </p>
      <Link href={`/resources/${resource.id}`} className="mt-4 inline-flex text-sm font-semibold">
        View resource
      </Link>
    </article>
  );
}
