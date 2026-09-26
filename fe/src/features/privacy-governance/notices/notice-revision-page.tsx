"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
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
  PRIVACY_PAGE_SIZE,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyPageHeader,
  PrivacyRecordUnavailable,
  privacyPaths,
  RevisionStatusBadge,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import { formatDateOnly, formatDateTime, isFutureDateInput } from "@/lib/date-time";
import { RevisionStatusValue, type RevisionResponse } from "@/lib/api/generated/model";
import {
  usePrivacyGovernanceGetNotice,
  usePrivacyGovernanceGetNoticeRevision,
  usePrivacyGovernanceListNoticeRevisions,
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
      <form className="grid max-w-3xl gap-5" onSubmit={(event) => void submit(event)}>
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
        <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
          <Button variant="secondary" disabled={update.isPending} onClick={() => onDone(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save draft"}
          </Button>
        </div>
      </form>
      {action.stepUpDialog}
    </>
  );
}

function PublishReadiness({ revision }: { revision: RevisionResponse }) {
  if (!revision.effective_on) {
    return (
      <p className="text-sm text-muted">
        Set an effective date before publishing. It must be today or earlier.
      </p>
    );
  }
  if (isFutureDateInput(revision.effective_on)) {
    return (
      <p className="text-sm text-muted">
        This draft is effective {formatLongDate(revision.effective_on)}. It can be
        published on or after that date.
      </p>
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
  const latest = usePrivacyGovernanceListNoticeRevisions(
    noticeId,
    { page: 1, page_size: PRIVACY_PAGE_SIZE },
    { query: { enabled: Boolean(noticeId), retry: false } },
  );
  const publish = usePrivacyGovernancePublishNoticeRevision();
  const action = usePrivacyAction();
  const [editing, setEditing] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);

  if (detail.isPending) return <PrivacyDetailSkeleton label="Loading notice revision…" />;
  if (detail.isError) {
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
  const hasPublished =
    latest.data?.data.items.some(
      (item) => item.status === RevisionStatusValue.PUBLISHED,
    ) ?? false;

  async function confirmPublish() {
    const result = await action.run(
      () => publish.mutateAsync({ revisionId }),
      "The revision could not be published.",
      { onStepUpRequired: () => setPublishOpen(false) },
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
            <span>Updated {formatDateTime(revision.updated_at)}</span>
          </>
        }
        action={
          editable && !editing ? (
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
              <Button
                onClick={() => {
                  action.reset();
                  setPublishOpen(true);
                }}
              >
                Publish
              </Button>
            </>
          ) : null
        }
      />

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
      {editable && !editing ? (
        <div className="mb-4">
          <PublishReadiness revision={revision} />
        </div>
      ) : null}
      {!isDraft ? (
        <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
          Published and historical revisions cannot be edited. Create a new revision
          instead.
        </p>
      ) : family && !family.is_active ? (
        <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
          This notice is retired, so this draft cannot be edited or published.
        </p>
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
        <div className="max-w-4xl divide-y divide-border border-y border-border">
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
                    formatDateTime(revision.published_at)
                  ) : (
                    <span className="text-muted">Not published</span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold text-muted">Created</dt>
                <dd className="mt-1 text-sm text-ink">
                  {formatDateTime(revision.created_at)}
                </dd>
              </div>
            </dl>
          </DetailSection>
        </div>
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
