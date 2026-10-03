"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Panel, PanelHeader } from "@/components/ui/panel";
import type { CounselingAccess } from "@/features/counseling/counseling-access";
import { counselingErrorCode, counselingErrorMessage, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import {
  getCounselingGetAssignedSharedSummaryQueryKey,
  useCounselingGetAssignedSharedSummary,
  useCounselingPublishAssignedSharedSummary,
  useCounselingPutAssignedSharedSummary,
} from "@/lib/api/generated/counseling/counseling";

export function SharedSummarySection({
  encounterId,
  access,
  onPublished,
}: {
  encounterId: string;
  access: CounselingAccess;
  onPublished?: () => void;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | undefined>(undefined);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishOpen, setPublishOpen] = useState(false);
  const summaryQuery = useCounselingGetAssignedSharedSummary(encounterId, {
    query: {
      enabled: access.canViewAssignedSummaries,
      retry: false,
    },
  });
  const save = useCounselingPutAssignedSharedSummary({ mutation: { retry: false } });
  const publish = useCounselingPublishAssignedSharedSummary({ mutation: { retry: false } });
  const summary = summaryQuery.data?.data;
  const absent = summaryQuery.isError &&
    counselingErrorCode(summaryQuery.error) === "shared_summary_not_found";
  const canManage = access.canManageAssignedSummaries;
  const value = draft ?? summary?.content ?? "";
  const dirty = value !== (summary?.content ?? "");

  if (!access.canViewAssignedSummaries) return null;

  async function saveDraft() {
    if (save.isPending || !canManage || !dirty) return;
    setSaveError(null);
    try {
      const response = await save.mutateAsync({ encounterId, data: { content: value } });
      setDraft(response.data.content);
      queryClient.setQueryData(getCounselingGetAssignedSharedSummaryQueryKey(encounterId), response);
    } catch (caught) {
      setSaveError(counselingErrorMessage(caught, "The Shared Summary draft could not be saved."));
      if (counselingErrorCode(caught) === "shared_summary_already_published") {
        void summaryQuery.refetch();
      }
    }
  }

  async function publishSummary() {
    if (publish.isPending || !canManage || !value.trim()) return;
    setPublishError(null);
    try {
      const response = await publish.mutateAsync({ encounterId });
      setPublishOpen(false);
      setDraft(response.data.content);
      queryClient.setQueryData(getCounselingGetAssignedSharedSummaryQueryKey(encounterId), response);
      onPublished?.();
    } catch (caught) {
      setPublishError(counselingErrorMessage(caught, "The Shared Summary could not be published."));
      if (counselingErrorCode(caught) === "shared_summary_already_published") {
        void summaryQuery.refetch();
      }
    }
  }

  return (
    <Panel aria-labelledby="shared-summary-heading">
      <PanelHeader title="Shared Summary" titleId="shared-summary-heading" />
      <div className="px-4 py-4 *:first:mt-0 sm:px-5">
      {summaryQuery.isPending ? <p aria-busy="true" className="mt-3 text-sm text-muted">Loading Shared Summary…</p> : summaryQuery.isError && !absent ? <p role="alert" className="mt-3 text-sm text-danger">{counselingErrorMessage(summaryQuery.error, "Shared Summary could not be loaded.")}</p> : summary?.published_at ? (
        <div className="mt-4">
          <p className="text-sm font-semibold text-success">Published to Student · {formatCounselingDateTime(summary.published_at)}</p>
          <div className="mt-4 whitespace-pre-wrap break-words text-sm leading-7 text-ink">{summary.content}</div>
        </div>
      ) : canManage ? (
        <div className="mt-4 max-w-4xl">
          <p className="text-sm text-muted">This draft is private to you until you publish it to the Student.</p>
          {absent ? <p className="mt-2 text-sm text-muted">No Shared Summary has been drafted yet.</p> : null}
          <div className="mt-4 grid gap-2">
            <Label htmlFor={`shared-summary-${encounterId}`}>Shared Summary draft</Label>
            <Textarea id={`shared-summary-${encounterId}`} value={value} disabled={save.isPending || publish.isPending} onChange={(event) => { setDraft(event.target.value); setSaveError(null); setPublishError(null); }} rows={9} />
          </div>
          {saveError ? <p role="alert" className="mt-3 text-sm text-danger">{saveError}</p> : null}
          {publishError && !publishOpen ? <p role="alert" className="mt-3 text-sm text-danger">{publishError}</p> : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <Button variant="secondary" disabled={!dirty || save.isPending || publish.isPending} onClick={() => void saveDraft()} aria-busy={save.isPending}>{save.isPending ? "Saving draft…" : "Save draft"}</Button>
            <Button disabled={!value.trim() || dirty || save.isPending || publish.isPending} onClick={() => { setPublishError(null); setPublishOpen(true); }}>Publish to Student</Button>
          </div>
          <ConsequentialActionDialog
            open={publishOpen}
            title="Publish this Shared Summary to the Student?"
            confirmLabel="Publish summary"
            cancelLabel="Keep draft"
            pendingLabel="Publishing…"
            pending={publish.isPending}
            confirmDisabled={!value.trim()}
            error={publishError}
            onOpenChange={setPublishOpen}
            onConfirm={() => void publishSummary()}
          >
            <p>
              After publication, the summary becomes visible to the Student and
              is locked from ordinary editing.
            </p>
          </ConsequentialActionDialog>
        </div>
      ) : absent ? (
        <p className="mt-3 text-sm text-muted">No Shared Summary has been drafted yet.</p>
      ) : (
        <div className="mt-3">
          <p className="text-sm text-muted">This Shared Summary is a Counselor-authored message intended for the Student.</p>
          <div className="mt-4 whitespace-pre-wrap break-words text-sm leading-7 text-ink">{summary?.content}</div>
        </div>
      )}
      </div>
    </Panel>
  );
}
