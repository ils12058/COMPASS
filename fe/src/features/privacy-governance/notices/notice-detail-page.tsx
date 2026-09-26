"use client";

import { keepPreviousData, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  emptyNoticeRevisionValues,
  noticeFieldLabels,
  noticeRevisionCreateRequest,
  NoticeRevisionFields,
  noticeRevisionValues,
  type NoticeRevisionValues,
} from "@/features/privacy-governance/notices/notice-revision-fields";
import {
  hasPrivacyConflictCode,
  PrivacyConflictCode,
  privacyErrorMessage,
} from "@/features/privacy-governance/privacy-governance-errors";
import { audienceSummary } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  ActionMessages,
  ActiveBadge,
  invalidatePrivacyRecords,
  PRIVACY_PAGE_SIZE,
  PrivacyConfirmDialog,
  PrivacyDetailSkeleton,
  PrivacyListSkeleton,
  PrivacyPageHeader,
  PrivacyQueryError,
  PrivacyRecordUnavailable,
  privacyPaths,
  recordLinkClass,
  RevisionStatusBadge,
  secondaryLinkClass,
  usePrivacyAccess,
  usePrivacyAction,
} from "@/features/privacy-governance/privacy-governance-shared";
import { formatDateOnly, formatDateTime } from "@/lib/date-time";
import type { NoticeResponse, RevisionResponse } from "@/lib/api/generated/model";
import {
  usePrivacyGovernanceCreateNoticeRevision,
  usePrivacyGovernanceGetNotice,
  usePrivacyGovernanceGetNoticeRevision,
  usePrivacyGovernanceListNoticeRevisions,
  usePrivacyGovernanceRetireNotice,
  usePrivacyGovernanceUpdateNotice,
} from "@/lib/api/generated/privacy-governance/privacy-governance";

function RenameNoticeForm({
  notice,
  onDone,
}: {
  notice: NoticeResponse;
  onDone: (saved: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const update = usePrivacyGovernanceUpdateNotice();
  const action = usePrivacyAction(noticeFieldLabels);
  const [name, setName] = useState(notice.name);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (name === notice.name) {
      onDone(false);
      return;
    }
    const result = await action.run(
      () => update.mutateAsync({ noticeId: notice.id, data: { name } }),
      "The notice name could not be saved.",
    );
    if (!result) return;
    await invalidatePrivacyRecords(queryClient, privacyPaths.notices);
    onDone(true);
  }

  return (
    <>
      <form
        className="mb-6 grid max-w-xl gap-3 border-y border-border py-5"
        onSubmit={(event) => void submit(event)}
      >
        <Label htmlFor="notice-rename">Notice name</Label>
        <Input
          id="notice-rename"
          required
          maxLength={160}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <ActionMessages error={action.error} notice={action.notice} className="" />
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" disabled={update.isPending} onClick={() => onDone(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save name"}
          </Button>
        </div>
      </form>
      {action.stepUpDialog}
    </>
  );
}

function CreateRevisionForm({
  notice,
  source,
  onCancel,
  onDraftExists,
}: {
  notice: NoticeResponse;
  source: RevisionResponse | undefined;
  onCancel: () => void;
  onDraftExists: (caught: unknown) => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = usePrivacyGovernanceCreateNoticeRevision();
  const action = usePrivacyAction(noticeFieldLabels);
  const [values, setValues] = useState<NoticeRevisionValues>(() =>
    source ? { ...noticeRevisionValues(source), effectiveOn: "" } : emptyNoticeRevisionValues,
  );
  const [audienceError, setAudienceError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (values.audiences.length === 0) {
      setAudienceError("Select at least one audience.");
      return;
    }
    setAudienceError(null);
    const result = await action.run(
      () =>
        create.mutateAsync({
          noticeId: notice.id,
          data: noticeRevisionCreateRequest(values),
        }),
      "The new revision could not be created.",
      {
        onError: (caught) => {
          if (hasPrivacyConflictCode(caught, PrivacyConflictCode.noticeDraftExists)) {
            onDraftExists(caught);
          }
        },
      },
    );
    if (!result) return;
    void invalidatePrivacyRecords(queryClient, privacyPaths.notices);
    router.push(`/portal/privacy/notice-revisions/${result.data.id}?created=1`);
  }

  return (
    <>
      <form
        aria-labelledby="new-revision-heading"
        className="mt-4 grid max-w-3xl gap-5 border-y border-border py-6"
        onSubmit={(event) => void submit(event)}
      >
        <div>
          <h3 id="new-revision-heading" className="font-heading text-lg font-semibold text-ink">
            New draft revision
          </h3>
          <p className="mt-1 text-sm leading-6 text-muted">
            {source
              ? `Starts from revision ${source.revision_number}. The draft is not shown to anyone until it is published.`
              : "The draft is not shown to anyone until it is published."}
          </p>
        </div>
        <NoticeRevisionFields
          idPrefix="new-revision"
          values={values}
          audienceError={audienceError}
          onChange={(next) => {
            setValues(next);
            if (next.audiences.length > 0) setAudienceError(null);
          }}
        />
        <ActionMessages error={action.error} notice={action.notice} className="" />
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" disabled={create.isPending} onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create draft revision"}
          </Button>
        </div>
      </form>
      {action.stepUpDialog}
    </>
  );
}

function RevisionRow({ revision }: { revision: RevisionResponse }) {
  const details = [
    revision.effective_on ? `Effective ${formatDateOnly(revision.effective_on)}` : "No effective date",
    revision.published_at ? `Published ${formatDateTime(revision.published_at)}` : null,
    audienceSummary(revision.audiences),
    revision.requires_acknowledgment ? "Acknowledgment requested" : "No acknowledgment requested",
  ].filter((value): value is string => Boolean(value));

  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={`/portal/privacy/notice-revisions/${revision.id}`}
          className={recordLinkClass}
        >
          Revision {revision.revision_number}
        </Link>
        <RevisionStatusBadge status={revision.status} />
      </div>
      <p className="mt-1 break-words text-sm text-ink">{revision.title}</p>
      <p className="mt-1 text-xs leading-5 text-muted">{details.join(" · ")}</p>
    </li>
  );
}

export function NoticeDetailPage() {
  const { noticeId } = useParams<{ noticeId: string }>();
  const searchParams = useSearchParams();
  const { canManage } = usePrivacyAccess();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [renaming, setRenaming] = useState(false);
  const [creatingRevision, setCreatingRevision] = useState(false);
  const [retireOpen, setRetireOpen] = useState(false);
  const notice = usePrivacyGovernanceGetNotice(noticeId, { query: { retry: false } });
  // A new draft starts from the current published revision, loaded only when needed.
  const currentRevisionId = notice.data?.data.current_revision?.id ?? "";
  const source = usePrivacyGovernanceGetNoticeRevision(currentRevisionId, {
    query: { enabled: creatingRevision && Boolean(currentRevisionId), retry: false },
  });
  const revisions = usePrivacyGovernanceListNoticeRevisions(
    noticeId,
    { page, page_size: PRIVACY_PAGE_SIZE },
    { query: { retry: false, placeholderData: keepPreviousData } },
  );
  const retire = usePrivacyGovernanceRetireNotice();
  const action = usePrivacyAction();

  if (notice.isPending) return <PrivacyDetailSkeleton label="Loading privacy notice…" />;
  if (notice.isError) {
    return (
      <PrivacyRecordUnavailable
        title="Privacy notice unavailable"
        error={notice.error}
        fallback="The privacy notice could not be loaded."
        backHref="/portal/privacy/notices"
        backLabel="Privacy Notices"
        onRetry={() => void notice.refetch()}
      />
    );
  }

  const family = notice.data.data;
  const manageable = canManage && family.is_active;
  const draft = family.draft_revision;
  const sourceRevision = source.data?.data;
  const sourcePending = Boolean(currentRevisionId) && source.isPending;
  const result = revisions.data?.data;

  async function confirmRetire() {
    const done = await action.run(
      () => retire.mutateAsync({ noticeId }),
      "The privacy notice could not be retired.",
      { onStepUpRequired: () => setRetireOpen(false) },
    );
    if (!done) return;
    setRetireOpen(false);
    action.setNotice("Privacy notice retired.");
    void invalidatePrivacyRecords(
      queryClient,
      privacyPaths.notices,
      privacyPaths.noticeRevisions,
      privacyPaths.myNotices,
      privacyPaths.publicNotices,
    );
  }

  return (
    <article>
      <PrivacyPageHeader
        title={family.name}
        backHref="/portal/privacy/notices"
        backLabel="Privacy Notices"
        meta={
          <>
            <span className="break-all font-mono text-ink">{family.code}</span>
            <ActiveBadge active={family.is_active} />
            <span>Updated {formatDateTime(family.updated_at)}</span>
          </>
        }
        action={
          manageable && !renaming ? (
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  action.reset();
                  setRenaming(true);
                }}
              >
                Rename
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  action.reset();
                  setRetireOpen(true);
                }}
              >
                Retire
              </Button>
            </>
          ) : null
        }
      />

      {searchParams.get("created") === "1" ? (
        <p role="status" className="mb-4 text-sm text-success">
          Privacy notice created with revision 1 as a draft.
        </p>
      ) : null}
      <ActionMessages
        error={retireOpen ? null : action.error}
        notice={action.notice}
        className="mb-4"
      />

      {renaming ? (
        <RenameNoticeForm
          notice={family}
          onDone={(saved) => {
            setRenaming(false);
            if (saved) action.setNotice("Notice name saved.");
          }}
        />
      ) : null}

      <section aria-labelledby="notice-revisions-heading" className="max-w-4xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2
            id="notice-revisions-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Revisions
          </h2>
          {manageable && !creatingRevision ? (
            draft ? (
              <Link
                href={`/portal/privacy/notice-revisions/${draft.id}`}
                className={secondaryLinkClass}
              >
                Open draft revision {draft.revision_number}
              </Link>
            ) : (
              <Button
                variant="secondary"
                onClick={() => {
                  action.reset();
                  setCreatingRevision(true);
                }}
              >
                Create new revision
              </Button>
            )
          ) : null}
        </div>

        {creatingRevision && sourcePending ? (
          <PrivacyListSkeleton rows={2} label="Loading the current revision…" />
        ) : creatingRevision && currentRevisionId && source.isError ? (
          <PrivacyQueryError
            error={source.error}
            fallback="The current revision could not be loaded to start a new draft."
            onRetry={() => void source.refetch()}
          />
        ) : creatingRevision ? (
          <CreateRevisionForm
            notice={family}
            source={sourceRevision}
            onCancel={() => setCreatingRevision(false)}
            onDraftExists={(caught) => {
              // Another draft exists: close the form and point to that draft.
              setCreatingRevision(false);
              action.setError(
                privacyErrorMessage(caught, "The new revision could not be created."),
              );
              void invalidatePrivacyRecords(
                queryClient,
                privacyPaths.notices,
                privacyPaths.noticeRevisions,
              );
            }}
          />
        ) : null}

        <div className="mt-4">
          {revisions.isPending ? (
            <PrivacyListSkeleton rows={3} label="Loading revisions…" />
          ) : revisions.isError && !result ? (
            <PrivacyQueryError
              error={revisions.error}
              fallback="Revisions could not be loaded."
              onRetry={() => void revisions.refetch()}
            />
          ) : result && result.items.length === 0 ? (
            <p className="border-y border-border py-6 text-sm text-muted">
              No revisions on this page.
            </p>
          ) : result ? (
            <>
              <ol className="divide-y divide-border border-y border-border">
                {result.items.map((revision) => (
                  <RevisionRow key={revision.id} revision={revision} />
                ))}
              </ol>
              {result.page > 1 || result.has_next ? (
                <CanonicalPagination
                  page={result.page}
                  hasNext={result.has_next}
                  onPageChange={setPage}
                  label="Revision pages"
                />
              ) : null}
            </>
          ) : null}
        </div>
      </section>

      <PrivacyConfirmDialog
        open={retireOpen}
        title="Retire this privacy notice?"
        description={
          <p>
            It will stop appearing as a current notice. Existing revisions and
            acknowledgment history will remain preserved.
          </p>
        }
        confirmLabel="Retire privacy notice"
        pendingLabel="Retiring…"
        pending={retire.isPending}
        error={retireOpen ? action.error : null}
        destructive
        onOpenChange={(open) => {
          setRetireOpen(open);
          if (!open) action.setError(null);
        }}
        onConfirm={() => void confirmRetire()}
      />
      {action.stepUpDialog}
    </article>
  );
}
