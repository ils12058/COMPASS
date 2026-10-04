"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { dataTable } from "@/components/ui/data-table";
import { FloatingListTools, ListToolField } from "@/components/ui/floating-list-tools";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import {
  PlatformConfirmation,
  usePlatformAction,
} from "@/features/platform/platform-actions";
import { hasPlatformManage } from "@/features/platform/platform-gate";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { describeResultPage } from "@/features/portal/components/result-context";
import {
  emailDeliveryStatusLabels,
  PlatformPageHeader,
  PlatformRowsSkeleton,
  PlatformStatusBadge,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  EmailDeliveryFailureCode,
  EmailDeliveryRetryBlocker,
  EmailDeliveryStatusValue,
  type EmailDeliveryItemResponse,
} from "@/lib/api/generated/model";
import {
  getPlatformOperationsGetEmailDeliverySummaryQueryKey,
  getPlatformOperationsListActivityQueryKey,
  getPlatformOperationsListEmailDeliveriesQueryKey,
  usePlatformOperationsGetEmailDeliverySummary,
  usePlatformOperationsListEmailDeliveries,
  usePlatformOperationsRetryEmailDelivery,
} from "@/lib/api/generated/platform-operations/platform-operations";

const PAGE_SIZE = 20;
const summaryCell = "min-w-0 bg-surface-raised px-4 py-3.5 sm:px-5";
const EMAIL_STATUSES = Object.values(EmailDeliveryStatusValue);

const failureLabels: Record<EmailDeliveryFailureCode, string> = {
  [EmailDeliveryFailureCode.transport_error]: "Mail server could not be reached",
  [EmailDeliveryFailureCode.send_returned_zero]: "Mail server did not accept the message",
  [EmailDeliveryFailureCode.template_error]: "Email content could not be prepared",
  [EmailDeliveryFailureCode.recipient_inactive]: "Recipient account is inactive",
  [EmailDeliveryFailureCode.unknown_failure]: "Unclassified failure",
};

// Only reasons an operator cannot infer from the status column are explained.
const retryBlockerLabels: Partial<Record<EmailDeliveryRetryBlocker, string>> = {
  [EmailDeliveryRetryBlocker.FAILURE_NOT_RETRYABLE]: "Not retryable for this failure",
  [EmailDeliveryRetryBlocker.RECIPIENT_INACTIVE]: "Recipient account is inactive",
};

type StatusFilter = EmailDeliveryStatusValue | "ALL";

function statusFilterFrom(value: string): StatusFilter {
  return EMAIL_STATUSES.find((status) => status === value) ?? "ALL";
}

function Timing({ delivery }: { delivery: EmailDeliveryItemResponse }) {
  const primaryTime = delivery.sent_at ?? delivery.last_attempt_at ?? delivery.updated_at;
  const primaryLabel = delivery.sent_at
    ? "Sent"
    : delivery.last_attempt_at
      ? "Last attempt"
      : "Updated";

  return (
    <dl className="space-y-1 text-xs text-muted">
      <div>
        <dt className="inline font-medium">{primaryLabel}: </dt>
        <dd className="inline"><PlatformTimestamp value={primaryTime} /></dd>
      </div>
      {delivery.next_attempt_at ? (
        <div>
          <dt className="inline font-medium">Next attempt: </dt>
          <dd className="inline"><PlatformTimestamp value={delivery.next_attempt_at} /></dd>
        </div>
      ) : null}
    </dl>
  );
}

export function PlatformEmailDeliveryPage() {
  const { user } = usePortalSession();
  const canManage = hasPlatformManage(user);
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [page, setPage] = useState(1);
  const [selectedDelivery, setSelectedDelivery] =
    useState<EmailDeliveryItemResponse | null>(null);
  const [selectedDeliveryAt, setSelectedDeliveryAt] = useState(0);
  const summary = usePlatformOperationsGetEmailDeliverySummary({
    query: { retry: false, staleTime: 20_000 },
  });
  const params = {
    page,
    page_size: PAGE_SIZE,
    ...(status === "ALL" ? {} : { status }),
  };
  const deliveries = usePlatformOperationsListEmailDeliveries(params, {
    query: { retry: false, staleTime: 15_000 },
  });
  const retry = usePlatformOperationsRetryEmailDelivery();
  const action = usePlatformAction();
  const summaryData = summary.isError && !canShowLastKnownData(summary) ? undefined : summary.data?.data;
  const deliveryPage = deliveries.isError && !canShowLastKnownData(deliveries) ? undefined : deliveries.data?.data;
  const rowsStale = deliveries.isError && Boolean(deliveryPage);

  async function refreshEmailDelivery() {
    await Promise.all([summary.refetch(), deliveries.refetch()]);
  }

  async function requestRetry() {
    if (!canManage || !selectedDelivery || deliveries.isError || selectedDeliveryAt !== deliveries.dataUpdatedAt) return;

    let staleEligibility = false;
    const success = await action.run(
      async () => {
        try {
          return await retry.mutateAsync({ deliveryId: selectedDelivery.id });
        } catch (caught) {
          staleEligibility =
            caught instanceof CompassApiError &&
            readApiErrorCode(caught.body) === "email_delivery_not_retryable";
          throw caught;
        }
      },
      "The retry request could not be completed.",
      () => setSelectedDelivery(null),
    );
    if (!success) {
      // Eligibility can change between reading the list and retrying; show current state.
      if (staleEligibility) {
        void queryClient.invalidateQueries({
          queryKey: getPlatformOperationsListEmailDeliveriesQueryKey(),
        });
      }
      return;
    }

    setSelectedDelivery(null);
    action.setNotice("Retry requested. The delivery is pending another attempt.");
    void queryClient.invalidateQueries({
      queryKey: getPlatformOperationsListEmailDeliveriesQueryKey(),
    });
    void queryClient.invalidateQueries({
      queryKey: getPlatformOperationsGetEmailDeliverySummaryQueryKey(),
    });
    void queryClient.invalidateQueries({
      queryKey: getPlatformOperationsListActivityQueryKey(),
    });
  }

  return (
    <section aria-labelledby="platform-page-heading">
      <PlatformPageHeader
        title="Email delivery"
        description="Recipient details and message contents are not shown here."
        action={<Button variant="secondary" disabled={summary.isFetching || deliveries.isFetching} onClick={() => void refreshEmailDelivery()}>{summary.isFetching || deliveries.isFetching ? "Refreshing…" : "Refresh email delivery"}</Button>}
      />

      <Panel className="overflow-hidden" aria-labelledby="email-summary-heading">
        <PanelHeader title="Delivery summary" titleId="email-summary-heading" />
        {summary.isPending ? <PlatformRowsSkeleton label="Loading delivery summary…" rows={2} framed={false} /> : null}
        {summary.isError && !summaryData ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={<Button variant="secondary" onClick={() => void summary.refetch()}>Try again</Button>}
          >
            The email delivery summary could not be loaded.
          </PanelMessage>
        ) : null}
        {summary.isError && summaryData ? (
          <div className="px-4 sm:px-5">
            <RefreshFailureNotice message="Latest delivery summary could not be refreshed. Showing the last confirmed summary." onRetry={() => void summary.refetch()} retrying={summary.isFetching} />
          </div>
        ) : null}
        {summaryData ? (
          <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3">
            <div className={summaryCell}>
              <dt className="text-sm font-medium text-muted">Pending</dt>
              <dd className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ink">
                {summaryData.pending_count}
              </dd>
            </div>
            <div className={summaryCell}>
              <dt className="text-sm font-medium text-muted">Processing</dt>
              <dd className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ink">
                {summaryData.processing_count}
              </dd>
            </div>
            <div className={summaryCell}>
              <dt className="text-sm font-medium text-muted">Failed</dt>
              <dd className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ink">
                {summaryData.failed_count}
              </dd>
            </div>
            <div className={summaryCell}>
              <dt className="text-sm font-medium text-muted">Cancelled</dt>
              <dd className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ink">
                {summaryData.cancelled_count}
              </dd>
            </div>
            <div className={summaryCell}>
              <dt className="text-sm font-medium text-muted">Sent today</dt>
              <dd className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ink">
                {summaryData.sent_today}
              </dd>
            </div>
            <div className={summaryCell}>
              <dt className="text-sm font-medium text-muted">Due pending</dt>
              <dd className="mt-1 font-heading text-2xl font-semibold tabular-nums text-ink">
                {summaryData.due_pending_count}
              </dd>
            </div>
            <div className={`${summaryCell} col-span-2 sm:col-span-3`}>
              <dt className="text-sm font-medium text-muted">Oldest pending</dt>
              <dd className="mt-1 text-sm text-ink">
                <PlatformTimestamp value={summaryData.oldest_pending_at} />
              </dd>
            </div>
          </dl>
        ) : null}
      </Panel>

      {/* One status choice, applied on change. */}
      <FloatingListTools label="Delivery filters" compact>
        <ListToolField label="Status" htmlFor="email-delivery-status">
          <Select
            id="email-delivery-status"
            value={status}
            onChange={(event) => {
              setStatus(statusFilterFrom(event.target.value));
              setPage(1);
            }}
          >
            <option value="ALL">All statuses</option>
            {EMAIL_STATUSES.map((item) => (
              <option key={item} value={item}>
                {emailDeliveryStatusLabels[item]}
              </option>
            ))}
          </Select>
        </ListToolField>
      </FloatingListTools>

      {action.error ? (
        <p role="alert" className="mt-3 text-sm text-danger">
          {action.error}
        </p>
      ) : null}
      {action.notice ? (
        <p role="status" className="mt-3 text-sm text-success">
          {action.notice}
        </p>
      ) : null}
      {rowsStale ? <RefreshFailureNotice message="Latest delivery rows could not be refreshed. Showing the last confirmed rows. Retry eligibility must be checked again." onRetry={() => void deliveries.refetch()} retrying={deliveries.isFetching} /> : null}

      <Panel className={rowsStale ? undefined : "mt-5"} aria-labelledby="email-list-heading">
        <PanelHeader
          title="Deliveries"
          titleId="email-list-heading"
          context={
            deliveries.isFetching && !deliveries.isPending
              ? "Refreshing email deliveries…"
              : deliveryPage && !deliveries.isError
                ? describeResultPage({
                    count: deliveryPage.items.length,
                    page: deliveryPage.page,
                    hasNext: deliveryPage.has_next,
                    noun: { one: "delivery", other: "deliveries" },
                    filtered: status !== "ALL",
                  })
                : null
          }
        />
        {deliveries.isPending ? <PlatformRowsSkeleton label="Loading email deliveries…" rows={5} framed={false} /> : null}
        {deliveries.isError && !deliveryPage ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={<Button variant="secondary" onClick={() => void deliveries.refetch()}>Try again</Button>}
          >
            Email delivery records could not be loaded.
          </PanelMessage>
        ) : null}

        {deliveryPage ? (
          deliveryPage.items.length ? (
            <div className={dataTable.scroll}>
              <table className={`${dataTable.table} min-w-[58rem]`}>
                <caption className="sr-only">Email delivery operations</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>
                      Delivery
                    </th>
                    <th scope="col" className={dataTable.headerCell}>Status</th>
                    <th scope="col" className={dataTable.headerCell}>Attempts</th>
                    <th scope="col" className={dataTable.headerCell}>Created</th>
                    <th scope="col" className={dataTable.headerCell}>Timing</th>
                    {canManage ? (
                      <th scope="col" className={dataTable.headerCell}>Action</th>
                    ) : null}
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                {deliveryPage.items.map((delivery) => (
                  <tr key={delivery.id} className={dataTable.row}>
                    <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} max-w-64 text-left font-medium`}>
                      <span className="block break-all text-sm font-semibold text-ink">
                        {delivery.event_code}
                      </span>
                      <code className="mt-1 block break-all text-[0.7rem] font-normal text-muted">
                        {delivery.id}
                      </code>
                    </th>
                    <td className={dataTable.cell}>
                      <PlatformStatusBadge status={delivery.status} />
                      {delivery.failure_code ? (
                        <p className="mt-2 max-w-48 break-words text-xs text-muted">
                          {failureLabels[delivery.failure_code]}
                        </p>
                      ) : null}
                    </td>
                    <td className={`${dataTable.cell} text-ink`}>
                      {delivery.attempt_count}
                    </td>
                    <td className={`${dataTable.cell} text-xs text-ink`}>
                      <PlatformTimestamp value={delivery.created_at} />
                    </td>
                    <td className={dataTable.cell}>
                      <Timing delivery={delivery} />
                    </td>
                    {canManage ? (
                      <td className={dataTable.cell}>
                        {delivery.manual_retry_allowed && !rowsStale ? (
                          <Button
                            variant="secondary"
                            aria-label={`Request retry for ${delivery.event_code}, delivery ${delivery.id}`}
                            onClick={() => {
                              action.setError(null);
                              action.setNotice(null);
                              setSelectedDelivery(delivery);
                              setSelectedDeliveryAt(deliveries.dataUpdatedAt);
                            }}
                          >
                            Request retry
                          </Button>
                        ) : delivery.manual_retry_blocker &&
                          retryBlockerLabels[delivery.manual_retry_blocker] ? (
                          <span className="text-xs text-muted">
                            {retryBlockerLabels[delivery.manual_retry_blocker]}
                          </span>
                        ) : (
                          <span className="text-xs text-muted">—</span>
                        )}
                      </td>
                    ) : null}
                  </tr>
                ))}
                </tbody>
              </table>
            </div>
          ) : status === "ALL" ? (
            <PanelMessage>No email deliveries are available.</PanelMessage>
          ) : (
            <PanelMessage
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setStatus("ALL");
                    setPage(1);
                  }}
                >
                  Clear status filter
                </Button>
              }
            >
              No email deliveries match the selected status.
            </PanelMessage>
          )
        ) : null}
        {deliveryPage ? (
          <CanonicalPagination
            className="border-brand-line px-4 py-3 sm:px-5"
            page={deliveryPage.page}
            hasNext={deliveryPage.has_next}
            disabled={deliveries.isFetching}
            label="Email delivery pages"
            onPageChange={setPage}
          />
        ) : null}
      </Panel>

      {action.stepUpDialog}
      {canManage ? (
        <PlatformConfirmation
          open={selectedDelivery !== null && !deliveries.isError && selectedDeliveryAt === deliveries.dataUpdatedAt}
          title="Request an email delivery retry?"
          confirmLabel="Request retry"
          pendingLabel="Requesting…"
          pending={retry.isPending}
          error={action.error}
          variant="primary"
          onOpenChange={(open) => {
            if (!open && !retry.isPending) {
              setSelectedDelivery(null);
              action.setError(null);
            }
          }}
          onConfirm={() => void requestRetry()}
        >
          {selectedDelivery && !deliveries.isError && selectedDeliveryAt === deliveries.dataUpdatedAt ? (
            <>
              <p>
                Request another attempt for <strong>{selectedDelivery.event_code}</strong>.
                This returns the delivery to pending and queues delivery work; it
                does not guarantee an immediate successful email.
              </p>
              <p className="break-all font-mono text-xs">Delivery ID: {selectedDelivery.id}</p>
            </>
          ) : null}
        </PlatformConfirmation>
      ) : null}
    </section>
  );
}
