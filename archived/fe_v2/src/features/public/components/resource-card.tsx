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
  const date = formatPublicDate(resource.published_at);

  return (
    <article className="landing-paper-sheet h-full" data-tone="plain">
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
        {date ? `Published ${date}` : "Publication date unavailable"}
      </p>
      <Link href={`/resources/${resource.id}`} className="mt-4 inline-flex text-sm font-semibold">
        View resource <span aria-hidden="true">↗</span>
      </Link>
    </article>
  );
}
