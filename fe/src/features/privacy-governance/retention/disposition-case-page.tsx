"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { pageSheetWidth } from "@/components/ui/page-width";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import {
  usePrivacyGovernanceApproveDispositionCase,
  usePrivacyGovernanceGetDispositionCase,
  usePrivacyGovernancePlaceDispositionHold,
  usePrivacyGovernanceReleaseDispositionHold,
  usePrivacyGovernanceRetryDispositionCase,
} from "@/lib/api/generated/privacy-governance/privacy-governance";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  ActionMessages,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
  textLinkClass,
  usePrivacyAction,
} from "../privacy-governance-shared";
import {
  categoryLabels,
  canConfirmDispositionReview,
  dispositionConsequence,
  invalidateRetention,
  isRetentionConflict,
  stateLabels,
  useRetentionAccess,
} from "./retention-shared";

export function DispositionCasePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { canView, canManage, canApprove } = useRetentionAccess();
  const client = useQueryClient();
  const detail = usePrivacyGovernanceGetDispositionCase(caseId, {
    query: {
      enabled: canView,
      retry: false,
      refetchInterval: 10000,
      refetchIntervalInBackground: false,
    },
  });
  const approve = usePrivacyGovernanceApproveDispositionCase({
    mutation: { retry: false },
  });
  const retry = usePrivacyGovernanceRetryDispositionCase({
    mutation: { retry: false },
  });
  const hold = usePrivacyGovernancePlaceDispositionHold({
    mutation: { retry: false },
  });
  const release = usePrivacyGovernanceReleaseDispositionHold({
    mutation: { retry: false },
  });
  const action = usePrivacyAction();
  // Freeze the exact reviewed revision when opening the confirmation, even if a query refreshes.
  const [review, setReview] = useState<{
    revision: number;
    retry: boolean;
  } | null>(null);
  const [reason, setReason] = useState("");
  const item = safeQueryData(detail)?.data;
  const pending =
    approve.isPending || retry.isPending || hold.isPending || release.isPending;
  if (!canView)
    return (
      <WorkspaceUnavailable title="Disposition case unavailable">
        This account cannot view retention governance.
      </WorkspaceUnavailable>
    );
  if (detail.isPending)
    return <PrivacyDetailSkeleton label="Loading disposition case…" />;
  if (!item)
    return (
      <PrivacyQueryError
        error={detail.error}
        fallback="The disposition case could not be loaded."
        onRetry={() => void detail.refetch()}
      />
    );
  const activeHold = item.holds.find((value) => value.released_at === null);
  const terminal = item.state === "PROCESSING" || item.state === "COMPLETED";
  const fresh = !detail.isError && !detail.isFetching;
  const retryable =
    (item.state === "FAILED" || item.state === "RECONCILIATION_REQUIRED") &&
    item.manual_retries < 3 &&
    item.blocker !== "EXTERNAL_STORAGE";

  async function refresh() {
    await detail.refetch();
    await invalidateRetention(client);
  }
  const recovery = {
    onStepUpRequired: () => setReview(null),
    onError: (caught: unknown) => {
      if (isRetentionConflict(caught)) {
        setReview(null);
        action.setNotice(
          "The case changed. The latest state is being loaded; review it again before approving.",
        );
        void refresh();
      }
    },
  };

  async function confirm() {
    if (!review || !item || !fresh) return;
    if (review.revision !== item.revision) {
      setReview(null);
      action.setNotice(
        "The case changed during review. Review its current state again.",
      );
      await refresh();
      return;
    }
    const result = await action.run(
      () =>
        review.retry
          ? retry.mutateAsync({
              caseId,
              data: { expected_revision: review.revision },
            })
          : approve.mutateAsync({
              caseId,
              data: { expected_revision: review.revision },
            }),
      "Disposition could not be approved.",
      recovery,
    );
    if (!result) return;
    setReview(null);
    action.setNotice(
      "Disposition approved. COMPASS will process this case in the background.",
    );
    await refresh();
  }

  async function placeHold(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!item || !fresh) return;
    const result = await action.run(
      () =>
        hold.mutateAsync({
          caseId,
          data: { expected_revision: item.revision, reason },
        }),
      "The hold could not be placed.",
      recovery,
    );
    if (!result) return;
    setReason("");
    action.setNotice("Hold placed. Disposition is prevented.");
    await refresh();
  }

  async function releaseHold() {
    if (!item || !fresh) return;
    const result = await action.run(
      () =>
        release.mutateAsync({
          caseId,
          data: { expected_revision: item.revision },
        }),
      "The hold could not be released.",
      recovery,
    );
    if (!result) return;
    action.setNotice("Hold released. A new disposition approval is required.");
    await refresh();
  }

  return (
    <article className={pageSheetWidth}>
      <PrivacyPageHeader
        title={categoryLabels[item.category]}
        backHref="/portal/privacy/retention"
        backLabel="Retention & Disposition"
        meta={<span>{stateLabels[item.state]}</span>}
      />
      {detail.isError ? (
        <RefreshFailureNotice
          onRetry={() => void detail.refetch()}
          retrying={detail.isFetching}
        />
      ) : null}
      <Panel>
        <PanelHeader title="Reviewed case" />
        <PanelBody>
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Case reference</dt>
              <dd className="font-mono break-all">{item.id}</dd>
            </div>
            <div>
              <dt className="text-muted">Rule</dt>
              <dd>
                <Link
                  className={textLinkClass}
                  href={`/portal/privacy/retention/rules/${item.rule_id}`}
                >
                  {item.rule_code}
                </Link>{" "}
                · Revision {item.rule_revision}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Disposition / frozen membership</dt>
              <dd>
                {item.action === "ANONYMIZE"
                  ? "Anonymize"
                  : "Delete provider artifact, keep evidence"}{" "}
                · {item.affected_count} record
              </dd>
            </div>
            <div>
              <dt className="text-muted">Retention boundary</dt>
              <dd>{formatInstitutionalDateTime(item.eligible_at)}</dd>
            </div>
            {item.blocker ? (
              <div>
                <dt className="text-muted">Blocker / outcome</dt>
                <dd>{item.blocker.replaceAll("_", " ").toLowerCase()}</dd>
              </div>
            ) : null}
            {item.approved_at ? (
              <div>
                <dt className="text-muted">Approved</dt>
                <dd>{formatInstitutionalDateTime(item.approved_at)}</dd>
              </div>
            ) : null}
            {item.started_at ? (
              <div>
                <dt className="text-muted">Processing started</dt>
                <dd>{formatInstitutionalDateTime(item.started_at)}</dd>
              </div>
            ) : null}
            {item.completed_at ? (
              <div>
                <dt className="text-muted">Verified completion</dt>
                <dd>{formatInstitutionalDateTime(item.completed_at)}</dd>
              </div>
            ) : null}
          </dl>
        </PanelBody>
      </Panel>
      {canApprove && (item.state === "READY" || retryable) ? (
        <Panel className="mt-5">
          <PanelHeader
            title={retryable ? "Review and retry" : "Review and approve"}
          />
          <PanelBody>
            <p className="mb-4 text-sm leading-6">
              {dispositionConsequence(item)}
            </p>
            <Button
              disabled={!fresh || pending || Boolean(activeHold)}
              onClick={() => {
                action.reset();
                setReview({ revision: item.revision, retry: retryable });
              }}
            >
              {retryable ? "Authorize retry" : "Approve disposition"}
            </Button>
          </PanelBody>
        </Panel>
      ) : null}
      {canManage && !terminal ? (
        <Panel className="mt-5">
          <PanelHeader title="Disposition hold" />
          <PanelBody>
            {activeHold ? (
              <>
                <p className="mb-2 text-sm font-semibold">
                  On hold since{" "}
                  {formatInstitutionalDateTime(activeHold.placed_at)}
                </p>
                <p className="mb-3 text-sm break-words">{activeHold.reason}</p>
                <p className="mb-3 text-sm text-muted">
                  Releasing this hold does not approve disposition.
                </p>
                <Button
                  variant="secondary"
                  disabled={!fresh || pending}
                  onClick={() => void releaseHold()}
                >
                  {release.isPending ? "Releasing…" : "Release hold"}
                </Button>
              </>
            ) : (
              <form
                className="grid gap-3"
                onSubmit={(event) => void placeHold(event)}
              >
                <Label htmlFor="hold-reason">Safe administrative reason</Label>
                <Input
                  id="hold-reason"
                  required
                  maxLength={240}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  aria-describedby="hold-reason-hint"
                />
                <p id="hold-reason-hint" className="text-sm text-muted">
                  Use a policy or review reference. Keep names, answers, and
                  counseling content out of this reason.
                </p>
                <div>
                  <Button
                    variant="secondary"
                    type="submit"
                    disabled={!fresh || pending}
                  >
                    {hold.isPending ? "Placing hold…" : "Place hold"}
                  </Button>
                </div>
              </form>
            )}
          </PanelBody>
        </Panel>
      ) : null}
      {item.holds.length ? (
        <Panel className="mt-5">
          <PanelHeader title="Hold history" />
          <ul className="divide-y divide-border">
            {item.holds.map((value) => (
              <li key={value.id} className="px-4 py-3 text-sm sm:px-5">
                <p>{value.reason}</p>
                <p className="mt-1 text-muted">
                  Placed {formatInstitutionalDateTime(value.placed_at)}
                  {value.released_at
                    ? ` · Released ${formatInstitutionalDateTime(value.released_at)}`
                    : " · Active"}
                </p>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
      {review && review.revision !== item.revision ? (
        <p role="status" className="mt-4 text-sm">
          This case changed during review. Review its current state and open
          approval again.
        </p>
      ) : null}
      <ActionMessages
        error={review?.revision === item.revision ? null : action.error}
        notice={action.notice}
      />
      <PrivacyConfirmDialog
        open={Boolean(review) && review?.revision === item.revision}
        title={
          review?.retry
            ? "Authorize a disposition retry?"
            : "Approve this disposition?"
        }
        description={
          <p>
            One {categoryLabels[item.category]} record is reviewed for{" "}
            {item.action === "ANONYMIZE"
              ? "anonymization"
              : "provider artifact deletion"}
            . {dispositionConsequence(item)}
          </p>
        }
        confirmLabel={review?.retry ? "Authorize retry" : "Approve disposition"}
        pendingLabel="Approving…"
        pending={approve.isPending || retry.isPending}
        confirmDisabled={
          !review ||
          !canConfirmDispositionReview(review.revision, item.revision, fresh)
        }
        error={action.error}
        destructive
        onOpenChange={(open) => {
          if (!open) setReview(null);
        }}
        onConfirm={() => void confirm()}
      />
      {action.stepUpDialog}
    </article>
  );
}
