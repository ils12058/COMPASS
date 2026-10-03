"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelFooter } from "@/components/ui/panel";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { useServerBoundary } from "@/features/freshness/use-server-boundary";
import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import {
  ACKNOWLEDGMENT_EXPLANATION,
  noticeFieldLabels,
  noticeRevisionChanges,
  NoticeRevisionFields,
  noticeRevisionValues,
  type NoticeRevisionValues,
} from "@/features/privacy-governance/notices/notice-revision-fields";
import { PlainTextBlock } from "@/features/privacy-governance/plain-text-block";
import {
  audienceSummary,
  formatLongDate,
} from "@/features/privacy-governance/privacy-governance-presentation";
import {
  ActionMessages,
  DetailSection,
  invalidatePrivacyRecords,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyRecordUnavailable,
  privacyPaths,
  RevisionStatusBadge,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import {
  hasPrivacyConflictCode,
  PrivacyConflictCode,
} from "@/features/privacy-governance/privacy-governance-errors";
import { formatDateOnly, formatInstitutionalDateTime, institutionalDateTimeInputToISO } from "@/lib/institutional-time";
import {
  NoticePublishBlocker,
  RevisionStatusValue,
  type RevisionResponse,
} from "@/lib/api/generated/model";
import {
  usePrivacyGovernanceGetNotice,
  usePrivacyGovernanceGetNoticeRevision,
  usePrivacyGovernancePublishNoticeRevision,
  usePrivacyGovernanceUpdateNoticeRevision,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function DraftEditor({
  revision,
  onDone,
}: {
  revision: RevisionResponse;
  onDone: (saved: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const update = usePrivacyGovernanceUpdateNoticeRevision();
  const action = usePrivacyAction(noticeFieldLabels);
  const [baseline] = useState(() => noticeRevisionValues(revision));
  const [values, setValues] = useState<NoticeRevisionValues>(baseline);
  const [audienceError, setAudienceError] = useState<string | null>(null);
  const dirty = Object.keys(noticeRevisionChanges(baseline, values)).length > 0;
  const { confirmDiscard } = useUnsavedNavigation();

  useUnsavedChangesGuard({
    dirty,
    message: "Discard your unsaved Privacy Notice revision changes?",
  });

  function cancel() {
    if (!dirty || confirmDiscard()) onDone(false);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (values.audiences.length === 0) {
      setAudienceError("Select at least one audience.");
      return;
    }
    setAudienceError(null);
    const changes = noticeRevisionChanges(baseline, values);
    if (Object.keys(changes).length === 0) {
      action.setError(null);
      action.setNotice("No changes to save.");
      return;
    }
    const result = await action.run(
      () => update.mutateAsync({ revisionId: revision.id, data: changes }),
      "The draft could not be saved.",
    );
    if (!result) return;
    await invalidatePrivacyRecords(
      queryClient,
      privacyPaths.noticeRevisions,
      privacyPaths.notices,
    );
    onDone(true);
  }

  return (
    <>
      <Panel as="div" className="max-w-4xl">
      <form onSubmit={(event) => void submit(event)}>
        <PanelBody className="grid gap-5">
        <NoticeRevisionFields
          idPrefix="draft-revision"
          values={values}
          audienceError={audienceError}
          onChange={(next) => {
            setValues(next);
            if (next.audiences.length > 0) setAudienceError(null);
          }}
        />
        <ActionMessages error={action.error} notice={action.notice} className="" />
        </PanelBody>
        <PanelFooter className="justify-end">
          <Button variant="secondary" disabled={update.isPending} onClick={cancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save draft"}
          </Button>
        </PanelFooter>
      </form>
      </Panel>
      {action.stepUpDialog}
    </>
  );
}

// Readiness is evaluated by COMPASS with the institution's date; publishing revalidates it.
function PublishReadiness({ revision }: { revision: RevisionResponse }) {
  const { blocker } = revision.publish_readiness;
  if (blocker === NoticePublishBlocker.EFFECTIVE_DATE_MISSING) {
    return (
      <Notice className="mb-5 max-w-4xl">
        Set an effective date before publishing. It must be today or earlier.
      </Notice>
    );
  }
  if (blocker === NoticePublishBlocker.EFFECTIVE_DATE_IN_FUTURE && revision.effective_on) {
    return (
      <Notice className="mb-5 max-w-4xl">
        This draft is effective {formatLongDate(revision.effective_on)}. It can be
        published on or after that date.
      </Notice>
    );
  }
  return null;
}

export function NoticeRevisionPage() {
  const { revisionId } = useParams<{ revisionId: string }>();
  const searchParams = useSearchParams();
  const { canManage } = usePrivacyAccess();
  const queryClient = useQueryClient();
  const detail = usePrivacyGovernanceGetNoticeRevision(revisionId, {
    query: { retry: false },
  });
  const noticeId = detail.data?.data.notice_id ?? "";
  const notice = usePrivacyGovernanceGetNotice(noticeId, {
    query: { enabled: Boolean(noticeId), retry: false },
  });
  const publish = usePrivacyGovernancePublishNoticeRevision();
  const action = usePrivacyAction();
  const [editing, setEditing] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const projectedRevision = detail.data?.data;
  const publishBoundary = projectedRevision?.status === RevisionStatusValue.DRAFT &&
    projectedRevision.publish_readiness.blocker === NoticePublishBlocker.EFFECTIVE_DATE_IN_FUTURE &&
    projectedRevision.effective_on
      ? institutionalDateTimeInputToISO(`${projectedRevision.effective_on}T00:00`)
      : null;
  useServerBoundary({
    boundary: publishBoundary,
    serverDate: detail.data?.headers.date,
    receivedAt: detail.dataUpdatedAt,
    onBoundary: () => { void detail.refetch(); },
  });

  if (detail.isPending) return <PrivacyDetailSkeleton label="Loading notice revision…" />;
  if ((detail.isError && !canShowLastKnownData(detail)) || !detail.data) {
    return (
      <PrivacyRecordUnavailable
        title="Notice revision unavailable"
        error={detail.error}
        fallback="The notice revision could not be loaded."
        backHref="/portal/privacy/notices"
        backLabel="Privacy Notices"
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const revision = detail.data.data;
  const family = notice.data?.data;
  const isDraft = revision.status === RevisionStatusValue.DRAFT;
  const editable = canManage && isDraft && family?.is_active === true;
  const publishReady = !detail.isError && revision.publish_readiness.ready;
  const hasPublished = family?.current_revision != null;

  async function confirmPublish() {
    const result = await action.run(
      () => publish.mutateAsync({ revisionId }),
      "The revision could not be published.",
      {
        onStepUpRequired: () => setPublishOpen(false),
        onError: (caught) => {
          // The state or institutional date changed after this page loaded; show current state.
          if (
            hasPrivacyConflictCode(caught, PrivacyConflictCode.noticeNotYetEffective) ||
            hasPrivacyConflictCode(caught, PrivacyConflictCode.noticeRevisionImmutable) ||
            hasPrivacyConflictCode(caught, PrivacyConflictCode.noticeRetired)
          ) {
            void invalidatePrivacyRecords(
              queryClient,
              privacyPaths.noticeRevisions,
              privacyPaths.notices,
            );
          }
        },
      },
    );
    if (!result) return;
    setPublishOpen(false);
    action.setNotice(`Revision ${revision.revision_number} published.`);
    void invalidatePrivacyRecords(
      queryClient,
      privacyPaths.noticeRevisions,
      privacyPaths.notices,
      privacyPaths.myNotices,
      privacyPaths.publicNotices,
    );
  }

  return (
    <article>
      <PrivacyPageHeader
        title={`Revision ${revision.revision_number}`}
        context={family ? `Privacy Notice · ${family.name}` : "Privacy Notice"}
        backHref={`/portal/privacy/notices/${revision.notice_id}`}
        backLabel={family ? family.name : "Privacy Notice"}
        meta={
          <>
            <RevisionStatusBadge status={revision.status} />
            <span>Updated {formatInstitutionalDateTime(revision.updated_at)}</span>
          </>
        }
        action={
          editable && !editing && !detail.isError ? (
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  action.reset();
                  setEditing(true);
                }}
              >
                Edit draft
              </Button>
              {publishReady ? (
                <Button
                  onClick={() => {
                    action.reset();
                    setPublishOpen(true);
                  }}
                >
                  Publish
                </Button>
              ) : null}
            </>
          ) : null
        }
      />
      {detail.isError ? <RefreshFailureNotice message="Latest revision state could not be checked. Showing the last confirmed revision; publishing is unavailable until a successful refresh." onRetry={() => void detail.refetch()} retrying={detail.isFetching} /> : null}

      {searchParams.get("created") === "1" && !editing ? (
        <p role="status" className="mb-4 text-sm text-success">
          Draft revision created.
        </p>
      ) : null}
      <ActionMessages
        error={publishOpen ? null : action.error}
        notice={action.notice}
        className="mb-4"
      />
      {editable && !editing ? <PublishReadiness revision={revision} /> : null}
      {!isDraft ? (
        <Notice className="mb-5 max-w-4xl">
          Published and historical revisions cannot be edited. Create a new revision
          instead.
        </Notice>
      ) : family && !family.is_active ? (
        <Notice className="mb-5 max-w-4xl">
          This notice is retired, so this draft cannot be edited or published.
        </Notice>
      ) : null}

      {editing ? (
        <DraftEditor
          key={revision.updated_at}
          revision={revision}
          onDone={(saved) => {
            setEditing(false);
            if (saved) action.setNotice("Draft saved.");
          }}
        />
      ) : (
        <Panel as="div" className="max-w-4xl">
          <DetailSection title="Notice title">
            <p className="break-words text-sm text-ink">{revision.title}</p>
          </DetailSection>
          <DetailSection title="Who should see this?">
            <p className="text-sm text-ink">{audienceSummary(revision.audiences)}</p>
          </DetailSection>
          <DetailSection title="Short explanation">
            <PlainTextBlock text={revision.summary} />
          </DetailSection>
          <DetailSection title="Notice text">
            <PlainTextBlock text={revision.body} />
          </DetailSection>
          <DetailSection title="Acknowledgment">
            <p className="text-sm text-ink">
              {revision.requires_acknowledgment
                ? "People are asked to acknowledge this revision."
                : "Acknowledgment is not requested for this revision."}
            </p>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-muted">
              {ACKNOWLEDGMENT_EXPLANATION}
            </p>
          </DetailSection>
          <DetailSection title="Dates">
            <dl className="grid max-w-3xl gap-4 sm:grid-cols-3">
              <div>
                <dt className="text-xs font-semibold text-muted">Effective date</dt>
                <dd className="mt-1 text-sm text-ink">
                  {revision.effective_on ? (
                    formatDateOnly(revision.effective_on)
                  ) : (
                    <span className="text-muted">Not set</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">Published</dt>
                <dd className="mt-1 text-sm text-ink">
                  {revision.published_at ? (
                    formatInstitutionalDateTime(revision.published_at)
                  ) : (
                    <span className="text-muted">Not published</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">Created</dt>
                <dd className="mt-1 text-sm text-ink">
                  {formatInstitutionalDateTime(revision.created_at)}
                </dd>
              </div>
            </dl>
          </DetailSection>
        </Panel>
      )}

      <PrivacyConfirmDialog
        open={publishOpen}
        title={`Publish revision ${revision.revision_number}?`}
        description={
          <>
            <p>
              Revision {revision.revision_number} will become the current notice.
              {hasPublished
                ? " The previously published revision will become historical."
                : null}
            </p>
            {revision.requires_acknowledgment ? (
              <p>
                People who acknowledged an earlier revision may need to acknowledge
                this new revision.
              </p>
            ) : null}
          </>
        }
        confirmLabel="Publish revision"
        pendingLabel="Publishing…"
        pending={publish.isPending}
        error={publishOpen ? action.error : null}
        onOpenChange={(open) => {
          setPublishOpen(open);
          if (!open) action.setError(null);
        }}
        onConfirm={() => void confirmPublish()}
      />
      {action.stepUpDialog}
    </article>
  );
}
