"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { focusHeading } from "@/lib/focus-heading";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { GoodMoralSection, goodMoralErrorMessage } from "@/features/good-moral/good-moral-shared";
import {
  goodMoralPrepareRequest,
  getGoodMoralGetRequestQueryKey,
  getGoodMoralListRequestsQueryKey,
} from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralOperationalDetailResponse } from "@/lib/api/generated/model";

export function GoodMoralPreparationSection({ item, onRefresh }: {
  item: GoodMoralOperationalDetailResponse;
  onRefresh: () => Promise<GoodMoralOperationalDetailResponse | undefined>;
}) {
  const client = useQueryClient();
  const [reviewedAt, setReviewedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const prepare = useMutation({
    mutationFn: (expectedUpdatedAt: string) => goodMoralPrepareRequest(item.id, {
      expected_resource_version: expectedUpdatedAt,
    }),
    retry: false,
  });

  async function confirm() {
    if (!reviewedAt) return;
    setError(null);
    try {
      await prepare.mutateAsync(reviewedAt);
      setCompleted(true);
      await Promise.all([
        client.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(item.id) }),
        client.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
      ]);
      await onRefresh();
    } catch (caught) {
      setReviewedAt(null);
      await onRefresh();
      setError(goodMoralErrorMessage(caught, "Preparation could not be confirmed. Review the latest request before trying again."));
    }
  }

  return <>
    <GoodMoralSection title="Certificate preparation">
      <p className="text-sm text-muted">{item.status === "READY_FOR_ISSUANCE"
        ? "This request is ready for a Counselor's final review and issuance."
        : "Check the certificate details and optional receipt facts before marking this request ready."}</p>
      {item.actions.can_prepare ? <Button className="mt-4" onClick={() => {
        setError(null);
        setCompleted(false);
        setReviewedAt(item.actions.request_version);
      }}>Mark ready for issuance</Button> : null}
      {error ? <p role="alert" className="mt-3 text-sm text-danger">{error}</p> : null}
    </GoodMoralSection>
    <ConsequentialActionDialog
      open={reviewedAt !== null}
      title="Mark this request ready for issuance?"
      confirmLabel="Mark ready"
      pendingLabel="Marking ready…"
      pending={prepare.isPending}
      error={null}
      onConfirm={() => void confirm()}
      onOpenChange={(open) => { if (!open) setReviewedAt(null); }}
      onCloseAutoFocus={(event) => { if (completed) { event.preventDefault(); focusHeading("good-moral-counselor-detail-heading"); } }}
      completed={completed ? { title: "Ready for issuance", children: "A Counselor can now review and issue this certificate." } : null}
    >
      <p>{item.applicant_name} · {item.variant === "CURRENT_STUDENT" ? "Current Student" : "Graduate"}</p>
      <p>Preparation records you as the preparer. A Counselor will perform the final review and issuance. Any later certificate correction will require preparation again.</p>
    </ConsequentialActionDialog>
  </>;
}
