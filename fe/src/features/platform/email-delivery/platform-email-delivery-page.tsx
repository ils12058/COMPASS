"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  PlatformConfirmation,
  usePlatformAction,
} from "@/features/platform/platform-actions";
import {
  PlatformPageHeader,
  PlatformPagination,
  PlatformQueryError,
  PlatformRowsSkeleton,
  PlatformStatusBadge,
  PlatformTimestamp,
} from "@/features/platform/platform-presentation";
import type { EmailDeliveryItemResponse } from "@/lib/api/generated/model";
import {
  getPlatformOperationsGetEmailDeliverySummaryQueryKey,
  getPlatformOperationsListActivityQueryKey,
  getPlatformOperationsListEmailDeliveriesQueryKey,
  usePlatformOperationsGetEmailDeliverySummary,
  usePlatformOperationsListEmailDeliveries,
  usePlatformOperationsRetryEmailDelivery,
} from "@/lib/api/generated/platform-operations/platform-operations";

const PAGE_SIZE = 20;
const EMAIL_STATUSES = ["PENDING", "PROCESSING", "SENT", "FAILED", "CANCELLED"];
const RETRYABLE_FAILURE_CODES = new Set(["transport_error", "send_returned_zero"]);
const selectClass =
  "min-h-10 rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function retryEligible(delivery: EmailDeliveryItemResponse): boolean {
  return (
    delivery.status === "FAILED" &&
    RETRYABLE_FAILURE_CODES.has(delivery.failure_code)
  );
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
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("ALL");
  const [page, setPage] = useState(1);
  const [selectedDelivery, setSelectedDelivery] =
    useState<EmailDeliveryItemResponse | null>(null);
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
  const summaryData = summary.data?.data;
  const deliveryPage = deliveries.data?.data;

  async function requestRetry() {
    if (!selectedDelivery) return;

    const success = await action.run(
      () => retry.mutateAsync({ deliveryId: selectedDelivery.id }),
      "The retry request could not be completed.",
      () => setSelectedDelivery(null),
    );
    if (!success) return;

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
    <section>
      <PlatformPageHeader
        title="Email delivery"
        description="Operational delivery state only. Recipient identity and message content are not available here."
      />

      <section aria-labelledby="email-summary-heading" className="mb-9">
        <h2
          id="email-summary-heading"
          className="mb-3 font-heading text-xl font-semibold text-ink"
        >
          Delivery summary
        </h2>
        {summary.isPending ? <PlatformRowsSkeleton rows={2} /> : null}
        {summary.isError && !summaryData ? (
          <PlatformQueryError
            message="The email delivery summary could not be loaded."
            onRetry={() => void summary.refetch()}
          />
        ) : null}
        {summaryData ? (
          <dl className="grid gap-x-6 border-y border-border sm:grid-cols-2 lg:grid-cols-3">
            <div className="border-b border-border py-3">
              <dt className="text-xs font-medium text-muted">Pending</dt>
              <dd className="mt-1 text-lg font-semibold text-ink">
                {summaryData.pending_count}
              </dd>
            </div>
            <div className="border-b border-border py-3">
              <dt className="text-xs font-medium text-muted">Processing</dt>
              <dd className="mt-1 text-lg font-semibold text-ink">
                {summaryData.processing_count}
              </dd>
            </div>
            <div className="border-b border-border py-3">
              <dt className="text-xs font-medium text-muted">Failed</dt>
              <dd className="mt-1 text-lg font-semibold text-ink">
                {summaryData.failed_count}
              </dd>
            </div>
            <div className="border-b border-border py-3">
              <dt className="text-xs font-medium text-muted">Cancelled</dt>
              <dd className="mt-1 text-lg font-semibold text-ink">
                {summaryData.cancelled_count}
              </dd>
            </div>
            <div className="border-b border-border py-3">
              <dt className="text-xs font-medium text-muted">Sent today</dt>
              <dd className="mt-1 text-lg font-semibold text-ink">
                {summaryData.sent_today}
              </dd>
            </div>
            <div className="border-b border-border py-3">
              <dt className="text-xs font-medium text-muted">Due pending</dt>
              <dd className="mt-1 text-lg font-semibold text-ink">
                {summaryData.due_pending_count}
              </dd>
            </div>
            <div className="py-3 sm:col-span-2 lg:col-span-3">
              <dt className="text-xs font-medium text-muted">Oldest pending</dt>
              <dd className="mt-1 text-sm text-ink">
                <PlatformTimestamp value={summaryData.oldest_pending_at} />
              </dd>
            </div>
          </dl>
        ) : null}
      </section>

      <section aria-labelledby="email-list-heading">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <h2
            id="email-list-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Deliveries
          </h2>
          <div className="grid max-w-xs gap-2">
            <Label htmlFor="email-delivery-status">Status</Label>
            <select
              id="email-delivery-status"
              className={selectClass}
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="ALL">All statuses</option>
              {EMAIL_STATUSES.map((item) => (
                <option key={item} value={item}>
                  {humanize(item)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {action.error ? (
          <p role="alert" className="mb-4 text-sm text-danger">
            {action.error}
          </p>
        ) : null}
        {action.notice ? (
          <p role="status" className="mb-4 text-sm text-success">
            {action.notice}
          </p>
        ) : null}
        {deliveries.isPending ? <PlatformRowsSkeleton rows={5} /> : null}
        {deliveries.isError && !deliveryPage ? (
          <PlatformQueryError
            message="Email delivery records could not be loaded."
            onRetry={() => void deliveries.refetch()}
          />
        ) : null}

        {deliveryPage ? (
          deliveryPage.items.length ? (
            <>
              <div className="overflow-x-auto border-y border-border">
                <table className="min-w-[58rem] border-collapse text-left text-sm">
                  <caption className="sr-only">Email delivery operations</caption>
                  <thead className="bg-surface-muted text-xs text-muted">
                    <tr>
                      <th scope="col" className="sticky left-0 z-10 bg-surface-muted px-3 py-3 font-semibold">
                        Delivery
                      </th>
                      <th scope="col" className="px-3 py-3 font-semibold">Status</th>
                      <th scope="col" className="px-3 py-3 font-semibold">Attempts</th>
                      <th scope="col" className="px-3 py-3 font-semibold">Created</th>
                      <th scope="col" className="px-3 py-3 font-semibold">Timing</th>
                      <th scope="col" className="px-3 py-3 font-semibold">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {deliveryPage.items.map((delivery) => (
                      <tr key={delivery.id}>
                        <th scope="row" className="sticky left-0 z-10 max-w-64 bg-surface-raised px-3 py-4 text-left align-top font-medium">
                          <span className="block break-all text-sm font-semibold text-ink">
                            {delivery.event_code}
                          </span>
                          <code className="mt-1 block break-all text-[0.7rem] font-normal text-muted">
                            {delivery.id}
                          </code>
                        </th>
                        <td className="px-3 py-4 align-top">
                          <PlatformStatusBadge status={delivery.status} />
                          {delivery.failure_code ? (
                            <p className="mt-2 max-w-48 break-words text-xs text-muted">
                              {humanize(delivery.failure_code)}
                            </p>
                          ) : null}
                        </td>
                        <td className="px-3 py-4 align-top text-ink">
                          {delivery.attempt_count}
                        </td>
                        <td className="px-3 py-4 align-top text-xs text-ink">
                          <PlatformTimestamp value={delivery.created_at} />
                        </td>
                        <td className="px-3 py-4 align-top">
                          <Timing delivery={delivery} />
                        </td>
                        <td className="px-3 py-4 align-top">
                          {retryEligible(delivery) ? (
                            <Button
                              variant="secondary"
                              aria-label={`Request retry for ${delivery.event_code}, delivery ${delivery.id}`}
                              onClick={() => {
                                action.setError(null);
                                action.setNotice(null);
                                setSelectedDelivery(delivery);
                              }}
                            >
                              Request retry
                            </Button>
                          ) : (
                            <span className="text-xs text-muted">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-4">
                <PlatformPagination
                  page={deliveryPage.page}
                  hasNext={deliveryPage.has_next}
                  disabled={deliveries.isFetching}
                  onPageChange={setPage}
                />
              </div>
            </>
          ) : status === "ALL" ? (
            <p className="border-y border-border py-6 text-sm text-muted">
              No email deliveries are available.
            </p>
          ) : (
            <div className="border-y border-border py-6">
              <p className="text-sm text-muted">
                No email deliveries match the selected status.
              </p>
              <Button
                className="mt-3"
                variant="secondary"
                onClick={() => {
                  setStatus("ALL");
                  setPage(1);
                }}
              >
                Clear status filter
              </Button>
            </div>
          )
        ) : null}
      </section>

      {action.stepUpDialog}
      <PlatformConfirmation
        open={selectedDelivery !== null}
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
        {selectedDelivery ? (
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
    </section>
  );
}
