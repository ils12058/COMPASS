"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { workspaceTabClass } from "@/components/ui/workspace-tabs";
import { SupervisedStaffActivity, useSupervisedStaff } from "./supervised-staff";
import { useActivitySearchParams } from "@/features/activity/activity-filters";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useMeListActivity, useMeListSecurityActivity } from "@/lib/api/generated/activity/activity";
import type { ActivityItemResponse, ActivityPageResponse } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

const PAGE_SIZE = 20;

function ActivityList({
  data,
  emptyText,
  onPageChange,
}: {
  data: ActivityPageResponse;
  emptyText: string;
  onPageChange: (page: number) => void;
}) {
  const items: ActivityItemResponse[] = data.items;
  return (
    <>
      {items.length === 0 ? <PanelMessage>{emptyText}</PanelMessage> : (
        <ol className="divide-y divide-border">
          {items.map((item) => (
            <li key={item.id} className="px-4 py-4 sm:px-5">
              <time dateTime={item.occurred_at} className="text-xs font-medium text-muted">
                {formatInstitutionalDateTime(item.occurred_at)}
              </time>
              <p className="mt-1 font-semibold text-ink">{item.title}</p>
              <p className="mt-1 text-sm leading-6 text-muted">{item.description}</p>
            </li>
          ))}
        </ol>
      )}
      <CanonicalPagination
        className="border-brand-line px-4 py-3 sm:px-5"
        page={data.page}
        hasNext={data.has_next}
        label="Activity pages"
        onPageChange={onPageChange}
      />
    </>
  );
}

export function ActivityPage() {
  const { user } = usePortalSession();
  const { searchParams, update } = useActivitySearchParams();
  const canSupervise = user.capabilities.includes("activity.supervised_staff.view");
  const staffQuery = useSupervisedStaff(canSupervise);
  const staffData = canSupervise ? safeQueryData(staffQuery) : undefined;
  const scoped = Boolean(staffData?.pages.some((page) => page.data.items.length));
  const requestedView = searchParams.get("view");
  const view = requestedView === "supervised" && canSupervise ? "supervised" : requestedView === "security" ? "security" : "my";
  function setView(next: "my" | "security" | "supervised") {
    update({ view: next === "my" ? null : next, search: null, staff_id: null, event_type: null, date_from: null, date_to: null });
  }
  const [myPage, setMyPage] = useState(1);
  const [securityPage, setSecurityPage] = useState(1);
  const my = useMeListActivity({ page: myPage, page_size: PAGE_SIZE }, { query: { enabled: view === "my", retry: false } });
  const security = useMeListSecurityActivity({ page: securityPage, page_size: PAGE_SIZE }, { query: { enabled: view === "security", retry: false } });
  const current = view === "my" ? my : security;
  const result = safeQueryData(current)?.data;

  return (
    <section aria-labelledby="activity-heading">
      <PageHeader title="Activity" headingId="activity-heading" />
      <Panel as="div">
      {/* The account views share one panel; the switch sits in its top band. */}
      <div role="group" aria-label="Account activity view" className="flex flex-wrap gap-x-6 border-b border-brand-line px-4 sm:px-5">
        <button type="button" aria-pressed={view === "my"} onClick={() => setView("my")} className={workspaceTabClass(view === "my")}>My activity</button>
        <button type="button" aria-pressed={view === "security"} onClick={() => setView("security")} className={workspaceTabClass(view === "security")}>Security activity</button>
        {scoped ? <button type="button" aria-pressed={view === "supervised"} onClick={() => setView("supervised")} className={workspaceTabClass(view === "supervised")}>Supervised staff</button> : null}
      </div>
      {view === "supervised" ? (
        scoped ? <SupervisedStaffActivity staffQuery={staffQuery} /> : staffQuery.isPending ? <RowsSkeleton label="Loading supervised staff…" rows={4} /> : staffQuery.isError ? <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void staffQuery.refetch()}>Retry</Button>}>Supervised staff could not be loaded.</PanelMessage> : <PanelMessage>No currently supervised staff.</PanelMessage>
      ) : <div aria-label={view === "my" ? "My activity" : "Security activity"}>
        {current.isPending ? <RowsSkeleton label="Loading activity…" rows={4} /> : null}
        {current.isError && result ? <RefreshFailureNotice onRetry={() => void current.refetch()} retrying={current.isFetching} /> : null}
        {current.isError && !result ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={<Button variant="secondary" onClick={() => void current.refetch()}>Retry</Button>}
          >
            {view === "my" ? "My activity" : "Security activity"} could not be loaded.
          </PanelMessage>
        ) : null}
        {result ? (
          <ActivityList
            data={result}
            onPageChange={view === "my" ? setMyPage : setSecurityPage}
            emptyText={view === "my" ? "No account activity is available yet." : "No security activity is available yet."}
          />
        ) : null}
      </div>}
      </Panel>
    </section>
  );
}
