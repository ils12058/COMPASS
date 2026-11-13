"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Notice } from "@/components/ui/notice";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { AppointmentsUnavailable, deliveryModeLabel } from "@/features/appointments/appointments-shared";
import { invalidateStudentScheduling } from "@/features/appointments/student-scheduling-invalidation";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  getCounselingGetMySessionProposalQueryKey,
  useCounselingAcceptSessionProposal,
  useCounselingDeclineSessionProposal,
  useCounselingGetMySessionProposal,
} from "@/lib/api/generated/counseling/counseling";
import { getStudentActionsListQueryKey } from "@/lib/api/generated/student-actions/student-actions";
import { DeliveryMode, type SessionProposalStudentResponse } from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/errors";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  isStaleProposalError,
  isUncertainProposalResult,
  proposalErrorCode,
  proposalErrorMessage,
  proposalStateLabel,
  purposeLabel,
} from "./session-proposal-presentation";

const backLink = <Link href="/portal/appointments" className={pageBackLinkClass}>Back to Appointments</Link>;

export function StudentSessionProposalPage({ proposalId }: { proposalId: string }) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  const queryClient = useQueryClient();
  const actionStatus = useActionStatus();
  const query = useCounselingGetMySessionProposal(proposalId, {
    query: { enabled: access.canManageSelf, retry: false, staleTime: 0, refetchOnWindowFocus: "always" },
  });
  const accept = useCounselingAcceptSessionProposal({ mutation: { retry: false } });
  const decline = useCounselingDeclineSessionProposal({ mutation: { retry: false } });
  const [selected, setSelected] = useState("");
  const [confirm, setConfirm] = useState<"accept" | "decline" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);

  if (!access.canManageSelf) return <AppointmentsUnavailable />;
  if (query.isPending) return <RowsSkeleton label="Loading proposed session…" />;
  const item = query.data?.data;
  if (!item) {
    const final = query.error instanceof CompassApiError && [403, 404].includes(query.error.status);
    return <>
      <PageHeader title="Proposed session" back={backLink} />
      <Notice tone="danger" role="alert" action={final ? undefined : <Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>
        {final ? "This proposed session isn't available to you." : "Couldn't load this proposed session. Try again."}
      </Notice>
    </>;
  }
  const choice = item.options.find((option) => option.id === selected) ?? null;
  const pending = accept.isPending || decline.isPending;

  function settle(next: SessionProposalStudentResponse, message: string) {
    queryClient.setQueryData(getCounselingGetMySessionProposalQueryKey(proposalId), (current: typeof query.data) => current ? { ...current, data: next } : current);
    setConfirm(null);
    setSelected("");
    actionStatus.show(message);
    void Promise.all([
      invalidateStudentScheduling(queryClient),
      queryClient.invalidateQueries({ queryKey: getStudentActionsListQueryKey() }),
    ]);
  }

  async function run(kind: "accept" | "decline") {
    if (pending || uncertain || !item) return;
    setError(null);
    try {
      const response = kind === "accept"
        ? await accept.mutateAsync({ proposalId, data: { option_id: selected, expected_version: item.version } })
        : await decline.mutateAsync({ proposalId, data: { expected_version: item.version } });
      settle(response.data, kind === "accept" ? "Appointment booked." : "Proposal declined.");
    } catch (caught) {
      const unknown = isUncertainProposalResult(caught);
      setUncertain(unknown);
      setConfirm(null);
      setError(unknown
        ? "Couldn't confirm your answer. Check your Appointments before trying again."
        : proposalErrorMessage(caught, kind === "accept" ? "That time couldn't be booked. Try again." : "Couldn't decline. Try again."));
      if (!unknown && (isStaleProposalError(caught) || proposalErrorCode(caught) === "session_proposal_time_unavailable")) {
        setSelected("");
        void query.refetch();
      }
    }
  }

  return (
    <article>
      <PageHeader
        title="Proposed session"
        description={<span className="inline-flex items-center gap-2"><PersonAvatar displayName={item.counselor.display_name} photoUrl={item.counselor.profile_photo_url} photoUpdatedAt={item.counselor.profile_photo_updated_at} size="compact" />{item.counselor.display_name}</span>}
        meta={<span className="text-sm font-semibold">{proposalStateLabel(item.state, "student")}</span>}
        back={backLink}
      />
      {query.isError ? <Notice tone="warning" role="status" className="mb-5" action={<Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button>}>Couldn&apos;t confirm the latest details.</Notice> : null}
      {error ? <Notice tone="danger" role="alert" className="mb-5">{error}</Notice> : null}
      <Outcome item={item} />
      <Panel as="div">
        <PanelSection title={purposeLabel(item.purpose)} titleId="proposal-purpose-heading" description={item.can_respond ? `Choose one time by ${formatInstitutionalDateTime(item.expires_at)}, or decline.` : undefined}>
          {item.can_respond ? (
            <fieldset disabled={pending || uncertain || query.isError} className="grid gap-3">
              <legend className="sr-only">Proposed times</legend>
              {item.options.map((option) => (
                <label key={option.id} className="flex min-h-11 cursor-pointer items-start gap-3 rounded-sm border border-border-strong bg-surface-raised px-3 py-2.5 text-sm text-ink focus-within:ring-2 focus-within:ring-focus has-[:checked]:border-brand has-[:checked]:bg-brand-wash">
                  <input type="radio" name="proposal-option" value={option.id} checked={selected === option.id} onChange={() => { setSelected(option.id); setError(null); }} className="mt-0.5 size-4 shrink-0 accent-brand" />
                  <span><span className="block font-semibold">{formatInstitutionalDateTime(option.starts_at)}</span><span className="block text-muted">{deliveryModeLabel(option.delivery_mode)}</span></span>
                </label>
              ))}
            </fieldset>
          ) : (
            <ul className="grid gap-2 text-sm">
              {item.options.map((option) => <li key={option.id} className={option.id === item.accepted_option_id ? "font-semibold" : "text-muted"}>{formatInstitutionalDateTime(option.starts_at)} · {deliveryModeLabel(option.delivery_mode)}{option.id === item.accepted_option_id ? " · Your choice" : ""}</li>)}
            </ul>
          )}
          {item.can_respond && item.options.some((option) => option.delivery_mode === DeliveryMode.ONLINE) ? <p className="mt-3 text-sm text-muted">Online sessions use E-Counseling. You&apos;ll be asked for E-Counseling consent before the session.</p> : null}
        </PanelSection>
        {item.can_respond ? (
          <PanelFooter>
            <Button disabled={!choice || pending || uncertain || query.isError || query.isFetching} onClick={() => { setError(null); setConfirm("accept"); }}>Accept time</Button>
            <Button variant="secondary" disabled={pending || uncertain || query.isError} onClick={() => { setError(null); setConfirm("decline"); }}>Decline</Button>
          </PanelFooter>
        ) : null}
      </Panel>
      <ConsequentialActionDialog
        open={confirm === "accept"}
        title="Book this session?"
        confirmLabel="Accept and book"
        pendingLabel="Booking…"
        pending={accept.isPending}
        error={null}
        onOpenChange={(open) => { if (!open) setConfirm(null); }}
        onConfirm={() => void run("accept")}
      >
        <p>{choice ? `${formatInstitutionalDateTime(choice.starts_at)} · ${deliveryModeLabel(choice.delivery_mode)}` : ""} with {item.counselor.display_name}.</p>
        <p>This books an Appointment under the usual Appointment rules, including cancellation. The other proposed times are released.</p>
      </ConsequentialActionDialog>
      <ConsequentialActionDialog
        open={confirm === "decline"}
        title="Decline this proposal?"
        confirmLabel="Decline proposal"
        pendingLabel="Declining…"
        pending={decline.isPending}
        error={null}
        onOpenChange={(open) => { if (!open) setConfirm(null); }}
        onConfirm={() => void run("decline")}
      >
        <p>No Appointment is booked. {item.counselor.display_name} sees that you declined and may contact you about another time.</p>
      </ConsequentialActionDialog>
      <ActionStatus status={actionStatus.status} onDismiss={actionStatus.dismiss} />
    </article>
  );
}

function Outcome({ item }: { item: SessionProposalStudentResponse }) {
  if (item.state === "ACCEPTED" && item.appointment) {
    return <Notice role="status" className="mb-5" action={<Link href={`/portal/appointments/${item.appointment.id}`} className={buttonVariants({ variant: "secondary" })}>Open Appointment</Link>}>
      Appointment {item.appointment.reference_code} is booked for {formatInstitutionalDateTime(item.appointment.starts_at)}.
      {item.appointment.delivery_mode === DeliveryMode.ONLINE ? " Give your E-Counseling consent from the Appointment before the session." : ""}
    </Notice>;
  }
  if (item.state === "PENDING") return null;
  const text = item.state === "DECLINED" ? "You declined this proposal. No Appointment was booked."
    : item.state === "WITHDRAWN" ? "Your Counselor withdrew this proposal. No Appointment was booked."
    : "This proposal is no longer open. No Appointment was booked.";
  return <Notice role="status" className="mb-5" action={<Link href="/portal/appointments/book" className={buttonVariants({ variant: "secondary" })}>Book an Appointment</Link>}>{text}</Notice>;
}
