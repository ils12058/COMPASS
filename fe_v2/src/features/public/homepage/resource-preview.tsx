"use client";

import Link from "next/link";

import { MarkdownContent } from "@/features/public/components/markdown-content";
import { LANDING_PAGE } from "@/features/public/config";
import { formatPublicDate, labelFromEnum, safePublicUrl } from "@/features/public/utils";
import { useResourcesListPublic } from "@/lib/api/generated/resources/resources";

import { ArrowLink, PaperSheet } from "./preview-primitives";

export function ResourcePreview() {
  const { resources } = LANDING_PAGE;
  const query = useResourcesListPublic(
    { page: 1, page_size: 3 },
    { query: { retry: 1, refetchOnWindowFocus: false } },
  );
  const items = query.data?.data?.items ?? [];

  return (
    <section className="landing-resources-section" aria-labelledby="resources-heading">
      <div className="public-shell landing-section">
        <div className="landing-section__heading">
          <div>
            <p className="landing-eyebrow">{resources.eyebrow}</p>
            <h2 id="resources-heading">{resources.title}</h2>
            <p>{resources.description}</p>
          </div>
          <Link className="landing-heading-link" href={resources.href}>
            {resources.link}
            <span aria-hidden="true">→</span>
          </Link>
        </div>

        {query.isPending ? (
          <p role="status" className="landing-data-state">
            Loading resources…
          </p>
      ) : query.isError ? (
        <p role="status" className="landing-data-state">
          We couldn’t load resources right now. Please try again later.
        </p>
      ) : items.length === 0 ? (
        <p className="landing-data-state">
          No resources to show right now.
        </p>
        ) : (
          <div className="landing-resources-grid">
            {items.map((item) => {
              const date = formatPublicDate(item.published_at);
              const meta = [labelFromEnum(item.category), labelFromEnum(item.kind), date]
                .filter(Boolean)
                .join(" · ");
              const externalUrl = safePublicUrl(item.external_url);

              return (
                <PaperSheet key={item.id} tone="plain">
                  <p className="landing-content-meta">{meta || "Guidance resource"}</p>
                  <h3>{item.title}</h3>
                  <MarkdownContent source={item.body_markdown} compact />
                  <div className="landing-resource-links">
                    <ArrowLink href={`/resources/${item.id}`}>View resource</ArrowLink>
                    {externalUrl ? (
                      <a
                        className="landing-content-link"
                        href={externalUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Open link
                        <span aria-hidden="true">↗</span>
                      </a>
                    ) : null}
                  </div>
                </PaperSheet>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
