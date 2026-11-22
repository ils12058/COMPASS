"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelSection, RecordSummary } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getAppointmentsGetCounselorRequestQueryKey,
  getAppointmentsListCounselorApprovalsQueryKey,
  getAppointmentsListCounselorRequestsQueryKey,
  useAppointmentsDecideCounselorRequest,
  useAppointmentsGetCounselorRequest,
} from "@/lib/api/generated/appointments/appointments";
import {
  CounselorBookingRequestState,
  CounselorRequestDecisionAction,
  type HeadCounselorRequestDetailResponse,
} from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

import { getAppointmentAccess } from "./appointments-access";
import {
  AppointmentsLocalNavigation,
  AppointmentsPageHeading,
  AppointmentsUnavailable,
} from "./appointments-shared";
import {
  counselorRequestErrorMessage,
  counselorRequestStateLabel,
  isCounselorRequestStaleError,
  studentCollegeLabel,
} from "./counselor-request-presentation";

export function HeadCounselorRequestDetailPage({ requestId }: { requestId: string }) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);

  if (!access.canReviewCounselorRequests) {
    return (
      <section aria-labelledby="counselor-request-detail-unavailable">
        <AppointmentsLocalNavigation />
        <AppointmentsUnavailable>
          Only the Head Guidance Counselor can review student counselor requests.
        </AppointmentsUnavailable>
      </section>
    );
  }

  return <RequestDetailWorkspace requestId={requestId} />;
}

function RequestDetailWorkspace({ requestId }: { requestId: string }) {
  const query = useAppointmentsGetCounselorRequest(requestId, {
    query: { retry: false, refetchOnWindowFocus: true },
  });
  const item = query.data?.data;

  return (
    <section aria-labelledby="counselor-request-detail-heading" className="space-y-5">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="counselor-request-detail-heading"
        title="Different counselor request"
        back={
          <Link href="/portal/appointments/counselor-requests" className={pageBackLinkClass}>
            Back to counselor requests
          </Link>
        }
      />

      {query.isPending ? (
        <LoadingRegion label="Loading counselor request…">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="mt-4 h-48 w-full" />
        </LoadingRegion>
      ) : query.isError && !item ? (
        <Notice
          role="alert"
          tone="danger"
          action={
            <Button variant="secondary" onClick={() => void query.refetch()}>
              Retry
            </Button>
          }
        >
          {counselorRequestErrorMessage(query.error, "Couldn't load this counselor request.")}
        </Notice>
      ) : item ? (
        <RequestReview item={item} onReload={() => query.refetch()} />
      ) : null}
    </section>
  );
}

function RequestReview({
  item,
  onReload,
}: {
  item: HeadCounselorRequestDetailResponse;
  onReload: () => Promise<unknown>;
}) {
  const queryClient = useQueryClient();
  const decide = useAppointmentsDecideCounselorRequest({ mutation: { retry: false } });
  const [action, setAction] = useState<CounselorRequestDecisionAction | null>(null);
  const [approvedCounselorId, setApprovedCounselorId] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  function openDecision(next: CounselorRequestDecisionAction) {
    setAction(next);
    setNote("");
    setError(null);
    setNotice(null);
    if (next === CounselorRequestDecisionAction.APPROVE) {
      const preferredAvailable =
        item.preferred_counselor &&
        item.available_counselors.some((c) => c.id === item.preferred_counselor?.id);
      setApprovedCounselorId(preferredAvailable ? item.preferred_counselor!.id : "");
    } else {
      setApprovedCounselorId("");
    }
  }

  async function confirmDecision() {
    if (!action) return;
    if (action === CounselorRequestDecisionAction.APPROVE && !approvedCounselorId) {
      setError("Choose a counselor to approve.");
      return;
    }
    setError(null);
    try {
      const response = await decide.mutateAsync({
        requestId: item.id,
        data: {
          action,
          approved_counselor_id:
            action === CounselorRequestDecisionAction.APPROVE ? approvedCounselorId : null,
          note: note.trim() || null,
          expected_version: item.version,
        },
      });
      queryClient.setQueryData(getAppointmentsGetCounselorRequestQueryKey(item.id), response);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getAppointmentsListCounselorRequestsQueryKey() }),
        queryClient.invalidateQueries({
          queryKey: getAppointmentsListCounselorApprovalsQueryKey(),
        }),
        invalidateGuidanceWork(queryClient),
      ]);
      const chosenName = response.data.approved_counselor?.display_name;
      setAction(null);
      setNotice(
        action === CounselorRequestDecisionAction.APPROVE
          ? `Approved. ${item.student.display_name} can now book with ${chosenName ?? "the selected counselor"} until you change or end this approval.`
          : `Declined. ${item.student.display_name} has been notified and will continue booking with their assigned counselor.`,
      );
    } catch (caught) {
      setError(counselorRequestErrorMessage(caught, "Couldn't save your decision. Try again."));
      if (isCounselorRequestStaleError(caught)) {
        setAction(null);
        await onReload();
      }
    }
  }

  return (
    <>
      {notice ? (
        <Notice role="status" tone="success">
          {notice}
        </Notice>
      ) : null}
      {error && !action ? (
        <Notice role="alert" tone="danger">
          {error}
        </Notice>
      ) : null}

      <Panel aria-labelledby="counselor-request-summary">
        <RecordSummary
          label="Student counselor request"
          title={item.student.display_name}
          titleId="counselor-request-summary"
          status={
            <span className="text-sm font-semibold text-ink">
              {counselorRequestStateLabel(item.state)}
            </span>
          }
          facts={[
            {
              label: "Student",
              value: item.student.institutional_id
                ? `${item.student.display_name} (${item.student.institutional_id})`
                : item.student.display_name,
            },
            { label: "College", value: studentCollegeLabel(item.student) },
            {
              label: "Default counselor",
              value: item.default_counselor?.display_name ?? "No default counselor assigned",
            },
          ]}
        />

        <PanelSection title="Request details" titleId="counselor-request-details">
          <dl className="grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Requested counselor</dt>
              <dd className="mt-1 font-medium text-ink">
                {item.preferred_counselor?.display_name ?? "No preference"}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Submitted</dt>
              <dd className="mt-1 text-ink">{formatInstitutionalDateTime(item.created_at)}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-muted">Reason (visible only to the Head Guidance Counselor)</dt>
              <dd className="mt-1 whitespace-pre-wrap text-ink">
                {item.reason ?? "No reason provided."}
              </dd>
            </div>
            {item.current_approval ? (
              <div className="sm:col-span-2">
                <dt className="text-muted">Current approval</dt>
                <dd className="mt-1 text-ink">
                  {item.current_approval.counselor.display_name} · Approved{" "}
                  {formatInstitutionalDateTime(item.current_approval.approved_at)}{" "}
                  <Link
                    href="/portal/appointments/counselor-requests"
                    className="ml-2 font-semibold text-brand underline"
                  >
                    Manage approvals
                  </Link>
                </dd>
              </div>
            ) : null}
            {item.decided_by ? (
              <div className="sm:col-span-2">
                <dt className="text-muted">Decision</dt>
                <dd className="mt-1 text-ink">
                  {counselorRequestStateLabel(item.state)}
                  {item.approved_counselor ? ` · ${item.approved_counselor.display_name}` : ""}
                  {" · "}By {item.decided_by.display_name} on{" "}
                  {item.decided_at ? formatInstitutionalDateTime(item.decided_at) : ""}
                  {item.decision_note ? ` — ${item.decision_note}` : ""}
                </dd>
              </div>
            ) : null}
          </dl>
        </PanelSection>

        {item.can_decide ? (
          <PanelBody className="flex flex-wrap gap-3 border-t border-border">
            <Button
              type="button"
              onClick={() => openDecision(CounselorRequestDecisionAction.APPROVE)}
            >
              Approve
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => openDecision(CounselorRequestDecisionAction.DECLINE)}
            >
              Decline
            </Button>
          </PanelBody>
        ) : item.state === CounselorBookingRequestState.PENDING ? (
          <PanelBody className="border-t border-border">
            <Notice role="status">
              This request can be decided only when exactly one active Head Guidance Counselor is
              configured. Contact the Guidance Office.
            </Notice>
          </PanelBody>
        ) : null}
      </Panel>

      <ConsequentialActionDialog
        open={action !== null}
        title={
          action === CounselorRequestDecisionAction.APPROVE
            ? "Approve a different counselor?"
            : "Decline this request?"
        }
        confirmLabel={
          action === CounselorRequestDecisionAction.APPROVE ? "Approve request" : "Decline request"
        }
        pendingLabel={
          action === CounselorRequestDecisionAction.APPROVE ? "Approving…" : "Declining…"
        }
        pending={decide.isPending}
        error={error}
        confirmDisabled={
          action === CounselorRequestDecisionAction.APPROVE && !approvedCounselorId
        }
        onOpenChange={(next) => {
          if (!next) {
            setAction(null);
            setError(null);
          }
        }}
        onConfirm={() => void confirmDecision()}
        choices={
          <div className="space-y-4">
            {action === CounselorRequestDecisionAction.APPROVE ? (
              <div className="grid gap-1.5">
                <Label htmlFor="approve-counselor-picker">Approved counselor</Label>
                <Select
                  id="approve-counselor-picker"
                  value={approvedCounselorId}
                  onChange={(event) => setApprovedCounselorId(event.target.value)}
                  disabled={decide.isPending}
                >
                  <option value="">Choose a counselor…</option>
                  {item.available_counselors.map((counselor) => (
                    <option key={counselor.id} value={counselor.id}>
                      {counselor.display_name}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}

            <div className="grid gap-1.5">
              <Label htmlFor="counselor-decision-note">Note to the student (optional)</Label>
              <Textarea
                id="counselor-decision-note"
                rows={3}
                maxLength={500}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                disabled={decide.isPending}
              />
            </div>
          </div>
        }
      >
        {action === CounselorRequestDecisionAction.APPROVE ? (
          <p>
            <strong>{item.student.display_name}</strong> will be able to book Appointments with the
            chosen counselor until you change or end this approval. They will be notified in-app and
            by email.
          </p>
        ) : (
          <p>
            <strong>{item.student.display_name}</strong> will continue booking with their assigned
            counselor. They will be notified in-app and by email.
          </p>
        )}
      </ConsequentialActionDialog>
    </>
  );
}
