"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelSection, RecordSummary } from "@/components/ui/panel";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { CounselingPageHeading, CounselingQueryError, EncounterDetailSkeleton, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import {
  getCounselingGetAppointmentReassignmentQueryKey,
  useCounselingDecideAppointmentReassignment,
  useCounselingGetAppointmentReassignment,
} from "@/lib/api/generated/counseling/counseling";
import type { CaseReassignmentAction, CaseReassignmentResponse } from "@/lib/api/generated/model";

import { reassignmentError, reassignmentRouteLabel, reassignmentStale, reassignmentStateLabel } from "./reassignment-presentation";

const labels: Record<CaseReassignmentAction, { confirm: string; pending: string; title: string }> = {
  approve: { confirm: "Approve reassignment", pending: "Approving…", title: "Approve this session reassignment?" },
  decline: { confirm: "Decline reassignment", pending: "Declining…", title: "Decline this session reassignment?" },
  withdraw: { confirm: "Withdraw request", pending: "Withdrawing…", title: "Withdraw this request?" },
};

export function ReassignmentReviewPage({ reassignmentId }: { reassignmentId: string }) {
  const query = useCounselingGetAppointmentReassignment(reassignmentId, { query: { retry: false, refetchOnWindowFocus: true } });
  const item = query.data?.data;
  return (
    <section className="space-y-5">
      <CounselingPageHeading
        title="Session reassignment"
        back={item ? <Link href={`/portal/appointments/${item.appointment.id}`} className={pageBackLinkClass}>Back to Appointment</Link> : undefined}
      />
      {query.isPending ? <EncounterDetailSkeleton /> : query.isError && !item ? (
        <CounselingQueryError message={reassignmentError(query.error, "Couldn't load this reassignment request.")} onRetry={() => void query.refetch()} />
      ) : item ? <Review item={item} onChanged={() => query.refetch()} /> : null}
    </section>
  );
}

function Review({ item, onChanged }: { item: CaseReassignmentResponse; onChanged: () => Promise<unknown> }) {
  const queryClient = useQueryClient();
  const decide = useCounselingDecideAppointmentReassignment({ mutation: { retry: false } });
  const [action, setAction] = useState<CaseReassignmentAction | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function confirm() {
    if (!action) return;
    setError(null);
    try {
      const response = await decide.mutateAsync({
        reassignmentId: item.id,
        data: { action, expected_version: item.version, reason: note.trim() || null },
      });
      queryClient.setQueryData(getCounselingGetAppointmentReassignmentQueryKey(item.id), response);
      setAction(null);
      setNotice(
        action === "approve"
          ? `Approved. The session is now with ${item.to_provider.display_name}.`
          : action === "decline"
            ? "Declined. The session stays with its current Counselor."
            : "Request withdrawn.",
      );
    } catch (caught) {
      setError(reassignmentError(caught, "Couldn't save the decision. Try again."));
      if (reassignmentStale(caught)) {
        setAction(null);
        await onChanged();
      }
    }
  }

  const open = (next: CaseReassignmentAction) => {
    setAction(next);
    setNote("");
    setError(null);
    setNotice(null);
  };

  return (
    <>
      {notice ? <Notice role="status">{notice}</Notice> : null}
      {error && !action ? <Notice role="alert" tone="danger">{error}</Notice> : null}
      <Panel aria-labelledby="reassignment-summary">
        <RecordSummary
          label="Case session"
          title={`${item.from_provider.display_name} → ${item.to_provider.display_name}`}
          titleId="reassignment-summary"
          status={<span className="text-sm font-semibold text-ink">{reassignmentStateLabel(item.state)}</span>}
          facts={[
            { label: "Student", value: item.student.display_name },
            { label: "Appointment", value: `${item.appointment.reference_code} · ${formatCounselingDateTime(item.appointment.starts_at)}` },
            { label: "Case", value: `${item.case_reference_code} · ${item.case_owner.display_name}` },
          ]}
        />
        <PanelSection title="Request" titleId="reassignment-request">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div><dt className="text-muted">Requested by</dt><dd className="text-ink">{item.requested_by.display_name} · {formatCounselingDateTime(item.requested_at)}</dd></div>
            <div><dt className="text-muted">Authorization</dt><dd className="text-ink">{reassignmentRouteLabel(item.route)}</dd></div>
            <div className="sm:col-span-2"><dt className="text-muted">Reason</dt><dd className="whitespace-pre-wrap text-ink">{item.reason}</dd></div>
            {item.decided_by ? (
              <div className="sm:col-span-2"><dt className="text-muted">Decided by</dt><dd className="text-ink">{item.decided_by.display_name} · {formatCounselingDateTime(item.decided_at)}{item.decision_reason ? ` — ${item.decision_reason}` : ""}</dd></div>
            ) : null}
          </dl>
          <p className="mt-4 text-sm text-muted">Only this session moves. The case, its records and its other sessions stay with {item.case_owner.display_name}.</p>
        </PanelSection>
        {item.can_approve || item.can_withdraw ? (
          <PanelBody className="flex flex-wrap gap-3 border-t border-border">
            {item.can_approve ? <Button onClick={() => open("approve")}>Approve</Button> : null}
            {item.can_approve ? <Button variant="secondary" onClick={() => open("decline")}>Decline</Button> : null}
            {item.can_withdraw ? <Button variant="secondary" onClick={() => open("withdraw")}>Withdraw request</Button> : null}
          </PanelBody>
        ) : null}
      </Panel>

      <ConsequentialActionDialog
        open={action !== null}
        title={action ? labels[action].title : ""}
        confirmLabel={action ? labels[action].confirm : ""}
        pendingLabel={action ? labels[action].pending : ""}
        pending={decide.isPending}
        error={error}
        onOpenChange={(next) => { if (!next) setAction(null); }}
        onConfirm={() => void confirm()}
        choices={action && action !== "withdraw" ? (
          <div className="grid gap-1.5">
            <Label htmlFor="reassignment-decision-note">Note (optional)</Label>
            <Textarea id="reassignment-decision-note" maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} />
          </div>
        ) : undefined}
      >
        {action === "approve" ? (
          <p>{item.appointment.reference_code} moves from {item.from_provider.display_name} to {item.to_provider.display_name}. The Student and both Counselors are notified. COMPASS checks the schedule again before saving.</p>
        ) : action === "decline" ? (
          <p>The session stays with {item.from_provider.display_name}. {item.requested_by.display_name} is notified.</p>
        ) : (
          <p>The session stays with {item.from_provider.display_name}.</p>
        )}
      </ConsequentialActionDialog>
    </>
  );
}
