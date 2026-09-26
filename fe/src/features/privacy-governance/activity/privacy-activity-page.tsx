"use client";

import { keepPreviousData } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { activityCategoryLabels } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  EmptyListState,
  PRIVACY_PAGE_SIZE,
  PrivacyListSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
  privacySelectClass,
  RefreshingNotice,
  useListSearchParams,
} from "@/features/privacy-governance/privacy-governance-shared";
import { formatDateTime } from "@/lib/date-time";
import {
  PrivacyActivityCategory,
  type PrivacyActivityItemResponse,
} from "@/lib/api/generated/model";
import { usePrivacyGovernanceListActivity } from "@/lib/api/generated/privacy-governance/privacy-governance";

const artifactLabels: Record<string, string> = {
  graduate_tracer: "Graduate Tracer",
  student_profiling: "Student Profiling",
  good_moral_certificate: "Good Moral certificate",
};

function artifactLabel(value: string): string {
  const known = artifactLabels[value];
  if (known) return known;
  const words = value.replaceAll("_", " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function categoryFrom(value: string | null): PrivacyActivityCategory | undefined {
  return Object.values(PrivacyActivityCategory).find((category) => category === value);
}

// Only the curated fields the API returns are shown. Identity is omitted when
// the backend suppresses it, rather than shown as an unknown person.
function ActivityItem({ item }: { item: PrivacyActivityItemResponse }) {
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="font-semibold text-ink">{item.title}</p>
        <time dateTime={item.occurred_at} className="text-xs text-muted">
          {formatDateTime(item.occurred_at)}
        </time>
      </div>
      <p className="mt-1 max-w-3xl break-words text-sm text-ink">{item.description}</p>
      <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <div>
          <dt className="inline">Category: </dt>
          <dd className="inline">{activityCategoryLabels[item.category]}</dd>
        </div>
        {item.actor_display_name ? (
          <div>
            <dt className="inline">By: </dt>
            <dd className="inline">{item.actor_display_name}</dd>
          </div>
        ) : null}
        {item.artifact_type ? (
          <div>
            <dt className="inline">Artifact: </dt>
            <dd className="inline">
              {artifactLabel(item.artifact_type)}
              {item.artifact_format ? ` (${item.artifact_format})` : null}
            </dd>
          </div>
        ) : null}
        {item.scope ? (
          <div className="max-w-full">
            <dt className="inline">Scope: </dt>
            <dd className="inline break-words">{item.scope}</dd>
          </div>
        ) : null}
        {item.resource_reference ? (
          <div className="max-w-full">
            <dt className="inline">Reference: </dt>
            <dd className="inline break-all font-mono">{item.resource_reference}</dd>
          </div>
        ) : null}
      </dl>
    </li>
  );
}

export function PrivacyActivityPage() {
  const { searchParams, page, update, setPage } = useListSearchParams();
  const category = categoryFrom(searchParams.get("category"));
  const query = usePrivacyGovernanceListActivity(
    { page, page_size: PRIVACY_PAGE_SIZE, ...(category ? { category } : {}) },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const result = query.data?.data;

  return (
    <section>
      <PrivacyPageHeader
        title="Privacy & Security Activity"
        description="A curated record of privacy-relevant events. It is not the full audit trail."
      />

      <div className="grid max-w-64 gap-2">
        <label htmlFor="privacy-activity-category" className="text-sm font-medium text-ink">
          Category
        </label>
        <select
          id="privacy-activity-category"
          className={privacySelectClass}
          value={category ?? ""}
          onChange={(event) => update({ category: categoryFrom(event.target.value) ?? null })}
        >
          <option value="">All activity</option>
          {Object.values(PrivacyActivityCategory).map((option) => (
            <option key={option} value={option}>
              {activityCategoryLabels[option]}
            </option>
          ))}
        </select>
      </div>

      {query.isPending ? (
        <div className="mt-5">
          <PrivacyListSkeleton label="Loading privacy and security activity…" />
        </div>
      ) : query.isError && !result ? (
        <div className="mt-5">
          <PrivacyQueryError
            error={query.error}
            fallback="Privacy and security activity could not be loaded."
            onRetry={() => void query.refetch()}
          />
        </div>
      ) : result && result.items.length === 0 ? (
        category ? (
          <EmptyListState
            message={`No ${activityCategoryLabels[category].toLowerCase()} activity.`}
            action={
              <Button variant="secondary" onClick={() => update({ category: null })}>
                Show all activity
              </Button>
            }
          />
        ) : (
          <EmptyListState
            message={
              page === 1
                ? "No privacy or security activity has been recorded."
                : "No activity on this page."
            }
          />
        )
      ) : result ? (
        <>
          <RefreshingNotice show={query.isFetching} label="Refreshing activity…" />
          <ol className="mt-5 divide-y divide-border border-y border-border">
            {result.items.map((item) => (
              <ActivityItem key={item.id} item={item} />
            ))}
          </ol>
          {result.page > 1 || result.has_next ? (
            <CanonicalPagination
              page={result.page}
              hasNext={result.has_next}
              onPageChange={setPage}
              label="Activity pages"
            />
          ) : null}
        </>
      ) : null}
    </section>
  );
}
