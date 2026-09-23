"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { InstitutionActionFeedback, FormRevisionStatusBadge } from "@/features/institution-configuration/institution-shared";
import { useInstitutionConfigurationAction } from "@/features/institution-configuration/institution-action";
import {
  getInstitutionalFormsRevisionsListQueryKey,
  useInstitutionalFormsRevisionsActivate,
  useInstitutionalFormsRevisionsDeactivate,
} from "@/lib/api/generated/institutional-forms/institutional-forms";
import { FormRevisionStatusValue } from "@/lib/api/generated/model";
import type { FormRevisionResponse } from "@/lib/api/generated/model";

type RevisionIntent = "activate" | "deactivate";

export function FormRevisionList({
  familyKey,
  familyTitle,
  revisions,
  canManage,
}: {
  familyKey: string;
  familyTitle: string;
  revisions: FormRevisionResponse[];
  canManage: boolean;
}) {
  const queryClient = useQueryClient();
  const activate = useInstitutionalFormsRevisionsActivate();
  const deactivate = useInstitutionalFormsRevisionsDeactivate();
  const action = useInstitutionConfigurationAction();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [target, setTarget] = useState<{
    revision: FormRevisionResponse;
    intent: RevisionIntent;
  } | null>(null);

  const otherActiveRevision =
    target?.intent === "activate" &&
    revisions.some(
      (revision) =>
        revision.id !== target.revision.id &&
        revision.status === FormRevisionStatusValue.ACTIVE,
    );

  function requestConfirmation(
    revision: FormRevisionResponse,
    intent: RevisionIntent,
  ) {
    action.resetFeedback();
    setTarget({ revision, intent });
    setConfirmOpen(true);
  }

  async function confirmLifecycleChange() {
    if (!target) return;
    const selected = target;
    const operation = () =>
      selected.intent === "activate"
        ? activate.mutateAsync({ revisionId: selected.revision.id })
        : deactivate.mutateAsync({ revisionId: selected.revision.id });
    const changed = await action.run(
      operation,
      selected.intent === "activate"
        ? "The Form Revision could not be activated."
        : "The Form Revision could not be deactivated.",
      {
        onStepUpRequired: () => setConfirmOpen(false),
        onStepUpVerified: () => setConfirmOpen(true),
      },
    );
    if (!changed) return;

    setConfirmOpen(false);
    setTarget(null);
    await queryClient.invalidateQueries({
      queryKey: getInstitutionalFormsRevisionsListQueryKey(familyKey),
    });
  }

  const revisionDescription = target
    ? `${target.revision.official_code ?? "Official code not recorded"}, official revision ${target.revision.official_revision ?? "not recorded"}`
    : "this Form Revision";

  return (
    <>
      <div className="min-w-0 overflow-x-auto rounded-sm border border-border">
        <table className="w-full min-w-[46rem] text-left text-sm">
          <caption className="sr-only">
            Form Revisions for {familyTitle}
          </caption>
          <thead className="border-b border-border bg-surface-muted text-xs font-semibold text-muted">
            <tr>
              <th scope="col" className="px-4 py-3">Official code</th>
              <th scope="col" className="px-4 py-3">Official revision</th>
              <th scope="col" className="px-4 py-3">Internal schema version</th>
              <th scope="col" className="px-4 py-3">Status</th>
              {canManage ? <th scope="col" className="px-4 py-3">Actions</th> : null}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {revisions.map((revision) => (
              <tr key={revision.id}>
                <td className="px-4 py-3 font-mono text-xs text-ink">
                  {revision.official_code ?? "Not recorded"}
                </td>
                <td className="px-4 py-3 text-ink">
                  {revision.official_revision ?? "Not recorded"}
                </td>
                <td className="px-4 py-3 text-ink">
                  {revision.internal_schema_version}
                </td>
                <td className="px-4 py-3">
                  <FormRevisionStatusBadge status={revision.status} />
                </td>
                {canManage ? (
                  <td className="px-4 py-3">
                    {revision.status === FormRevisionStatusValue.INACTIVE ? (
                      <Button
                        variant="secondary"
                        disabled={activate.isPending || deactivate.isPending}
                        onClick={() => requestConfirmation(revision, "activate")}
                      >
                        Activate
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        disabled={activate.isPending || deactivate.isPending}
                        onClick={() => requestConfirmation(revision, "deactivate")}
                      >
                        Deactivate
                      </Button>
                    )}
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AlertDialog
        open={confirmOpen}
        onOpenChange={(open) => {
          if (activate.isPending || deactivate.isPending) return;
          setConfirmOpen(open);
          if (!open) {
            setTarget(null);
            action.resetFeedback();
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle className="break-words">
            {target?.intent === "activate"
              ? `Activate ${revisionDescription}?`
              : `Deactivate ${revisionDescription}?`}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {target?.intent === "activate" ? (
              <>
                This revision will become the active revision for {familyTitle}. New records for workflows that bind to this family will use the active revision. Existing records retain the revision they were created with.
                {otherActiveRevision ? " The currently active revision will become inactive." : null}
              </>
            ) : (
              <>
                Some COMPASS workflows require an active supported revision, while others may operate without one. Deactivating this revision may prevent new records for this Form Family until another supported revision is activated. Existing records retain their saved Form Revision.
              </>
            )}
          </AlertDialogDescription>
          <InstitutionActionFeedback
            error={action.error}
            notice={action.notice}
          />
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button
                variant="secondary"
                disabled={activate.isPending || deactivate.isPending}
                onClick={() => {
                  setConfirmOpen(false);
                  setTarget(null);
                  action.resetFeedback();
                }}
              >
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant={target?.intent === "deactivate" ? "danger" : "primary"}
              disabled={!target || activate.isPending || deactivate.isPending}
              onClick={() => void confirmLifecycleChange()}
            >
              {activate.isPending || deactivate.isPending
                ? target?.intent === "activate"
                  ? "Activating…"
                  : "Deactivating…"
                : target?.intent === "activate"
                  ? "Activate revision"
                  : "Deactivate revision"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </>
  );
}
