"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useMeListActivity, useMeListSecurityActivity } from "@/lib/api/generated/activity/activity";
import type { ActivityItemResponse, ActivityPageResponse } from "@/lib/api/generated/model";

const PAGE_SIZE = 20;

function ActivityList({
  page,
  data,
  emptyText,
  onPageChange,
}: {
  page: number;
  data: ActivityPageResponse;
  emptyText: string;
  onPageChange: (page: number) => void;
}) {
  const items: ActivityItemResponse[] = data.items;
  return (
    <div className="mt-6">
      {items.length === 0 ? <p className="border-t border-border py-7 text-sm text-muted">{emptyText}</p> : (
        <ol className="divide-y divide-border border-y border-border">
          {items.map((item) => (
            <li key={item.id} className="py-5">
              <time dateTime={item.occurred_at} className="text-xs font-medium text-muted">
                {new Date(item.occurred_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
              </time>
              <p className="mt-2 font-heading text-lg font-semibold text-ink">{item.title}</p>
              <p className="mt-1 text-sm leading-6 text-muted">{item.description}</p>
            </li>
          ))}
        </ol>
      )}
      <div className="mt-5 flex items-center justify-between gap-3">
        <Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</Button>
        <span className="text-sm text-muted">Page {data.page}</span>
        <Button variant="secondary" disabled={!data.has_next} onClick={() => onPageChange(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

export function ActivityPage() {
  const [view, setView] = useState<"my" | "security">("my");
  const [myPage, setMyPage] = useState(1);
  const [securityPage, setSecurityPage] = useState(1);
  const my = useMeListActivity({ page: myPage, page_size: PAGE_SIZE }, { query: { enabled: view === "my", retry: false } });
  const security = useMeListSecurityActivity({ page: securityPage, page_size: PAGE_SIZE }, { query: { enabled: view === "security", retry: false } });
  const current = view === "my" ? my : security;

  return (
    <section aria-labelledby="activity-heading">
      <h1 id="activity-heading" className="font-heading text-3xl font-bold text-ink">Activity</h1>
      <div role="group" aria-label="Account activity view" className="mt-7 flex gap-5 border-b border-border">
        <button type="button" aria-pressed={view === "my"} onClick={() => setView("my")} className={`-mb-px min-h-11 border-b-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${view === "my" ? "border-brand text-brand" : "border-transparent text-muted"}`}>My activity</button>
        <button type="button" aria-pressed={view === "security"} onClick={() => setView("security")} className={`-mb-px min-h-11 border-b-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${view === "security" ? "border-brand text-brand" : "border-transparent text-muted"}`}>Security activity</button>
      </div>
      <div aria-label={view === "my" ? "My activity" : "Security activity"}>
        {current.isPending ? <p role="status" className="mt-7 text-sm text-muted">Loading activity…</p> : null}
        {current.isError ? (
          <div className="mt-7" role="alert">
            <p className="text-sm text-danger">{view === "my" ? "My activity" : "Security activity"} could not be loaded.</p>
            <Button variant="secondary" className="mt-3" onClick={() => void current.refetch()}>Retry</Button>
          </div>
        ) : null}
        {current.isSuccess ? (
          <ActivityList
            data={current.data.data}
            page={view === "my" ? myPage : securityPage}
            onPageChange={view === "my" ? setMyPage : setSecurityPage}
            emptyText={view === "my" ? "No account activity is available yet." : "No security activity is available yet."}
          />
        ) : null}
      </div>
    </section>
  );
}
