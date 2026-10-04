"use client";

import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { ActivityFilterTools, activityTypeLabel, enumValue, useActivitySearchParams } from "@/features/activity/activity-filters";
import { activityErrorMessage } from "@/features/activity/activity-errors";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import { getMeListSupervisedStaffQueryKey, meListSupervisedStaff, useMeListSupervisedStaffActivity } from "@/lib/api/generated/activity/activity";
import { SupervisedActivityType } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export function useSupervisedStaff(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: getMeListSupervisedStaffQueryKey({ page_size: 50 }),
    queryFn: ({ pageParam, signal }) => meListSupervisedStaff({ page: pageParam, page_size: 50 }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (last) => last.data.has_next ? last.data.page + 1 : undefined,
    enabled, retry: false,
  });
}

export function SupervisedStaffActivity({ staffQuery }: { staffQuery: ReturnType<typeof useSupervisedStaff> }) {
  const { searchParams, page, update, setPage } = useActivitySearchParams();
  const search = searchParams.get("search") || undefined;
  const staff_id = searchParams.get("staff_id") || undefined;
  const event_type = enumValue(searchParams.get("event_type"), Object.values(SupervisedActivityType));
  const date_from = searchParams.get("date_from") || undefined;
  const date_to = searchParams.get("date_to") || undefined;
  const criteria = { search, staff_id, event_type, date_from, date_to };
  const activity = useMeListSupervisedStaffActivity({ ...criteria, page, page_size: 20 }, { query: { retry: false, placeholderData: keepPreviousData } });
  const result = safeQueryData(activity)?.data;
  const staff = safeQueryData(staffQuery)?.pages.flatMap((entry) => entry.data.items) ?? [];
  const filtered = Object.values(criteria).some(Boolean);
  const clear = () => update(Object.fromEntries(Object.keys(criteria).map((key) => [key, null])));

  return (
    <div aria-label="Supervised staff activity">
      <PanelHeader title="Supervised staff" context={activity.isFetching && !activity.isPending ? "Refreshing activity…" : result && !activity.isError ? describeResultPage({ count: result.items.length, page: result.page, hasNext: result.has_next, noun: { one: "event", other: "events" }, filtered }) : null} />
      {activity.isError && result ? <RefreshFailureNotice onRetry={() => void activity.refetch()} retrying={activity.isFetching} /> : null}
      {activity.isPending ? <RowsSkeleton label="Loading supervised staff activity…" rows={4} /> : null}
      {activity.isError && !result ? <PanelMessage tone="danger" role="alert" action={<Button variant="secondary" onClick={() => void activity.refetch()}>Retry</Button>}>{activityErrorMessage(activity.error, "Supervised staff activity could not be loaded.")}</PanelMessage> : null}
      {result?.items.length ? (
        <ol className="divide-y divide-border">
          {result.items.map((item) => (
            <li key={item.id} className="px-4 py-4 sm:px-5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <p className="break-words font-semibold text-ink">{item.staff.display_name}</p>
                <time dateTime={item.occurred_at} className="text-xs text-muted">{formatInstitutionalDateTime(item.occurred_at)}</time>
              </div>
              <p className="mt-1 text-sm font-semibold text-ink">{item.title}</p>
              <p className="mt-1 break-words text-sm text-muted">{item.description}</p>
            </li>
          ))}
        </ol>
      ) : result ? <PanelMessage action={filtered ? <Button variant="secondary" onClick={clear}>Clear filters</Button> : undefined}>{filtered ? "No matching activity." : "No activity has been recorded yet."}</PanelMessage> : null}
      {result ? <CanonicalPagination className="border-brand-line px-4 py-3 sm:px-5" page={result.page} hasNext={result.has_next} disabled={activity.isFetching} label="Supervised staff activity pages" onPageChange={setPage} /> : null}
      <ActivityFilterTools key={JSON.stringify(criteria)} applied={criteria} onApply={update} fields={[
        { name: "staff_id", label: "Staff member", options: staff.map((person) => ({ value: person.id, label: person.display_name })) },
        { name: "event_type", label: "Activity type", options: Object.values(SupervisedActivityType).map((type) => ({ value: type, label: activityTypeLabel(type) })) },
        { name: "date_from", label: "Date from", type: "date" }, { name: "date_to", label: "Date to", type: "date" },
      ]} extra={<>
        {staffQuery.hasNextPage ? <Button variant="secondary" disabled={staffQuery.isFetchingNextPage} onClick={() => void staffQuery.fetchNextPage()}>{staffQuery.isFetchingNextPage ? "Loading staff…" : "Load more staff"}</Button> : null}
        {staffQuery.isError ? <p role="alert" className="text-sm text-danger">Staff choices could not be refreshed. <Button variant="quiet" onClick={() => void staffQuery.refetch()}>Retry</Button></p> : null}
      </>} />
    </div>
  );
}
