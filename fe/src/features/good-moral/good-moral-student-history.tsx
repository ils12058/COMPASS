"use client";

import { FileBadge } from "lucide-react";

import Link from "next/link";

import { PageActionLink } from "@/components/ui/page-action";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { GoodMoralHeading, GoodMoralListSkeleton, GoodMoralStatus, formatGoodMoralDateTime, goodMoralErrorMessage, goodMoralVariantLabel } from "@/features/good-moral/good-moral-shared";
import { useGoodMoralListMyRequests } from "@/lib/api/generated/good-moral/good-moral";

export function GoodMoralStudentHistory({
  canView,
  requestHref,
  requestLabel,
}: {
  canView: boolean;
  requestHref: string | null;
  requestLabel: string | null;
}) {
  const history = useGoodMoralListMyRequests({ query: { enabled: canView, retry: false } });
  const confirmed = safeQueryData(history);

  return (
    <section className="space-y-5" aria-labelledby="good-moral-student-heading">
      <GoodMoralHeading
        headingId="good-moral-student-heading"
        title="Good Moral"
        action={requestHref && requestLabel ? (
          <PageActionLink href={requestHref} icon={FileBadge} label="Request" labelDetail="Good Moral Certificate" />
        ) : undefined}
      />

      {canView ? (
        <Panel aria-labelledby="good-moral-my-requests-heading">
          <PanelHeader title="My requests" titleId="good-moral-my-requests-heading" />
          {history.isError && confirmed ? <div className="px-4 sm:px-5"><RefreshFailureNotice onRetry={() => void history.refetch()} retrying={history.isFetching} /></div> : null}
          {history.isPending ? (
            <GoodMoralListSkeleton label="Loading Good Moral requests…" framed={false} />
          ) : !confirmed ? (
            <PanelMessage
              role="alert"
              tone="danger"
              action={<Button variant="secondary" onClick={() => void history.refetch()}>Retry</Button>}
            >
              {goodMoralErrorMessage(history.error, "Your Good Moral requests could not be loaded.")}
            </PanelMessage>
          ) : confirmed.data.items.length === 0 ? (
            <PanelMessage>You do not have any Good Moral requests yet.</PanelMessage>
          ) : (
            <ol className="divide-y divide-border">
              {confirmed.data.items.map((item) => (
                <li key={item.id} className="grid gap-3 px-4 py-4 sm:grid-cols-[minmax(12rem,1fr)_auto] sm:items-center sm:px-5">
                  <div className="min-w-0">
                    <Link href={`/portal/good-moral/${item.id}`} className="font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                      {item.status === "ISSUED" ? `${goodMoralVariantLabel(item.variant)} certificate` : `${goodMoralVariantLabel(item.variant)} request`}
                    </Link>
                    <p className="mt-1 break-words text-sm text-muted">{item.applicant_name || "Applicant name not provided"}</p>
                    <p className="mt-1 text-xs text-muted">Requested {formatGoodMoralDateTime(item.created_at)}</p>
                    {item.issued_at ? <p className="mt-1 text-xs text-muted">Issued {formatGoodMoralDateTime(item.issued_at)}</p> : null}
                    {item.cancelled_at ? <p className="mt-1 text-xs text-muted">Cancelled {formatGoodMoralDateTime(item.cancelled_at)}</p> : null}
                  </div>
                  <div className="flex items-center justify-between gap-3 sm:justify-end">
                    <GoodMoralStatus status={item.status} />
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      ) : (
        <Panel as="div">
          <PanelMessage>Your request history is unavailable to this account.</PanelMessage>
        </Panel>
      )}
    </section>
  );
}
