"use client";

import { CircleAlert, FolderCheck, NotebookPen, RotateCcw, X } from "lucide-react";
import { usePathname, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { Notice } from "@/components/ui/notice";
import { PageAction, PageActionLink } from "@/components/ui/page-action";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import {
  caseErrorMessage,
  caseOriginLabel,
  CASES_PATH,
  caseSessionOffers,
  sessionCountLabel,
} from "@/features/counseling/cases/case-presentation";
import { AddSessionDialog, RemoveSessionDialog } from "@/features/counseling/cases/case-session-dialogs";
import { CaseStatusBadge } from "@/features/counseling/cases/case-status-badge";
import { CaseAppointmentsPanel } from "@/features/counseling/cases/case-appointments-panel";
import { LinkAppointmentDialog, UnlinkAppointmentDialog } from "@/features/counseling/cases/case-appointment-dialogs";
import { CaseNextActionsPanel } from "@/features/counseling/cases/case-next-actions-panel";
import { CaseHistoryPanel } from "@/features/counseling/cases/case-history-panel";
import { useProtectedCase } from "@/features/counseling/cases/use-protected-case";
import { closureReasonLabels, closureOutcomeLabels } from "@/features/counseling/cases/closure-presentation";
import { CaseContinuityPanel } from "@/features/counseling/continuity/case-continuity-panel";
import { followupActionLabel } from "@/features/guidance-followups/followups-presentation";
import { useFollowupsFreshness } from "@/features/guidance-followups/followups-data";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  CounselingPageHeading,
  CounselingQueryError,
  CounselingUnavailable,
  EncounterDetailSkeleton,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { RecordEncounterForm } from "@/features/counseling/record-encounter-form";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { portalReturnHref, withWorkflowReturn, workflowBackLabel } from "@/features/portal/workflow-navigation";
import {
  getCounselingGetCaseQueryKey,
  getCounselingListMyCasesQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingLinkCaseSession,
} from "@/lib/api/generated/counseling/counseling";
import type {
  CounselingCaseDetailResponse,
  CounselingCaseAppointmentResponse,
  CounselingCaseSessionResponse,
} from "@/lib/api/generated/model";
import { focusHeading } from "@/lib/focus-heading";

const textLink = "font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="min-w-0"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm text-ink">{children}</dd></div>;
}

function Person({ person }: { person: { display_name: string; profile_photo_url: string | null; profile_photo_updated_at: string | null } }) {
  return <span className="inline-flex items-center gap-2"><PersonAvatar displayName={person.display_name} photoUrl={person.profile_photo_url} photoUpdatedAt={person.profile_photo_updated_at} size="compact" />{person.display_name}</span>;
}

// Where the case started. The originating record is named only while it is still the reader's own.
function originDescription(item: CounselingCaseDetailResponse, returnTo: string): ReactNode {
  const label = caseOriginLabel(item.origin);
  if (item.source.appointment) {
    return <>{label} <Link href={withWorkflowReturn(`/portal/appointments/${item.source.appointment.id}`, returnTo)} className={textLink}>{item.source.appointment.reference_code}</Link></>;
  }
  if (item.source.encounter_id) {
    return <Link href={withWorkflowReturn(`/portal/counseling/encounters/${item.source.encounter_id}`, returnTo)} className={textLink}>{label}</Link>;
  }
  if (item.source.routine_interview_id) {
    return <Link href={withWorkflowReturn(`/portal/routine-interviews/${item.source.routine_interview_id}`, returnTo)} className={textLink}>{label}</Link>;
  }
  return label;
}

export function CaseOverviewPage({ caseId }: { caseId: string }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const params = useSearchParams();
  const here = `${pathname}${params.size ? `?${params}` : ""}`;
  const back = portalReturnHref(params.get("return_to"), CASES_PATH);
  const backLink = <Link href={back} className={pageBackLinkClass}>{workflowBackLabel(back)}</Link>;
  const access = getCounselingAccess(user);
  const queryClient = useQueryClient();
  const allowed = access.isCounselor && access.canViewAssigned;
  const query = useProtectedCase(caseId, allowed);
  useFollowupsFreshness(allowed && user.capabilities.includes("guidance_followups.view"));
  const actionStatus = useActionStatus();
  const linkOrigin = useCounselingLinkCaseSession({ mutation: { retry: false } });
  const [recordOpen, setRecordOpen] = useState(false);
  const [recordUncertain, setRecordUncertain] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [appointmentOpen, setAppointmentOpen] = useState(false);
  const [unlinking, setUnlinking] = useState<CounselingCaseAppointmentResponse | null>(null);
  const [addingOfferId, setAddingOfferId] = useState<string | null>(null);
  const [removing, setRemoving] = useState<CounselingCaseSessionResponse | null>(null);
  // Persistent, because the reader has to review the case again before acting.
  const [notice, setNotice] = useState<string | null>(null);
  const [originError, setOriginError] = useState<string | null>(null);
  const item = query.data?.data;

  if (!allowed) return <CounselingUnavailable title="Counseling case" />;
  if (query.privacy.blocked) return <><CounselingPageHeading title="Counseling case" back={backLink} /><CounselingQueryError message={caseErrorMessage(query.failure, "Protected case details have been cleared. Check access again to continue.")} onRetry={() => query.privacy.resume()} /></>;
  if (query.isPending) return <EncounterDetailSkeleton />;
  if ((query.isError && !canShowLastKnownData(query)) || !item) {
    return (
      <>
        <CounselingPageHeading title="Counseling case" back={backLink} />
        <CounselingQueryError message={caseErrorMessage(query.error, "Couldn't load this case. Try again.")} onRetry={() => void query.refetch()} />
      </>
    );
  }

  // A confirmed change replaces what is shown with the backend's own answer.
  function applyChange(next: CounselingCaseDetailResponse, message: string) {
    query.privacy.barrier.assertCurrent(query.privacy.generation);
    if (!navigator.onLine || document.visibilityState !== "visible") return;
    queryClient.setQueryData(getCounselingGetCaseQueryKey(caseId), (current: typeof query.data) => current ? { ...current, data: next } : current);
    setNotice(null);
    setOriginError(null);
    actionStatus.show(message);
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: getCounselingListMyCasesQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getCounselingListMyEncountersQueryKey() }),
    ]);
  }

  function reloadAfterStale() {
    actionStatus.dismiss();
    setNotice("This case changed before your action completed. The latest details are now shown.");
    void query.refetch();
  }

  async function addOfferedSession(current: CounselingCaseDetailResponse, encounterId: string) {
    if (linkOrigin.isPending) return;
    setAddingOfferId(encounterId);
    setOriginError(null);
    actionStatus.dismiss();
    try {
      const response = await linkOrigin.mutateAsync({
        caseId,
        data: { encounter_id: encounterId, expected_version: current.version },
      });
      applyChange(response.data, "Session added to this case.");
      focusHeading("case-sessions-heading");
    } catch (caught) {
      setOriginError(caseErrorMessage(caught, "The session couldn't be added. Check the case and try again."));
      void query.refetch();
    } finally {
      setAddingOfferId(null);
    }
  }

  const canManage = item.can_manage && item.status === "ACTIVE" && !query.isError;
  const canReopen = item.can_reopen && item.status === "CLOSED" && !query.isError;
  const offers = caseSessionOffers(item);

  return (
    <article>
      <CounselingPageHeading
        title={item.student.display_name}
        description={`Case ${item.reference_code}${item.student.institutional_id ? ` · Institutional ID ${item.student.institutional_id}` : ""}`}
        back={backLink}
        action={canManage ? (
          <>
            <PageAction
              icon={recordUncertain ? CircleAlert : recordOpen ? X : NotebookPen}
              label={recordUncertain ? "Unconfirmed" : recordOpen ? "Close" : "Record session"}
              labelDetail={recordUncertain ? "recording result" : recordOpen ? "recording" : "for this case"}
              variant={recordOpen ? "secondary" : "primary"}
              disabled={recordUncertain}
              aria-expanded={recordOpen}
              onClick={() => { actionStatus.dismiss(); setRecordOpen((open) => !open); }}
            />
            {!recordOpen ? <PageActionLink icon={FolderCheck} label="Close case" variant="secondary" href={withWorkflowReturn(`${pathname}/close`, here)} /> : null}
          </>
        ) : canReopen ? <PageActionLink icon={RotateCcw} label="Reopen case" href={withWorkflowReturn(`${pathname}/reopen`, here)} /> : undefined}
      />

      {query.isError ? <RefreshFailureNotice onRetry={() => void query.refetch()} /> : null}
      {notice ? <Notice role="status" tone="warning" className="mb-5">{notice}</Notice> : null}

      {recordOpen && canManage ? (
        <div className="mb-5">
          <RecordEncounterForm
            caseContext={{ caseId, student: item.student }}
            onCancel={() => setRecordOpen(false)}
            onUncertain={() => setRecordUncertain(true)}
            onCreated={async () => {
              setRecordOpen(false);
              setNotice(null);
              await Promise.all([
                query.refetch(),
                queryClient.invalidateQueries({ queryKey: getCounselingListMyCasesQueryKey() }),
              ]);
              actionStatus.show("Session recorded and added to this case.");
            }}
          />
        </div>
      ) : null}

      <Panel aria-labelledby="case-details-heading">
        <PanelHeader title="Case" titleId="case-details-heading" actions={<CaseStatusBadge status={item.status} />} />
        <dl className="grid gap-x-8 gap-y-4 px-4 py-4 sm:grid-cols-2 sm:px-5 lg:grid-cols-4">
          <Fact label="Responsible counselor"><Person person={item.primary_counselor} /></Fact>
          <Fact label="Completed sessions">{item.session_count}</Fact>
          <Fact label="Latest session">{item.latest_session_at ? formatCounselingDateTime(item.latest_session_at) : "No session yet"}</Fact>
          <Fact label="Next appointment">{item.next_appointment ? <>{item.next_appointment.record_accessible ? <Link href={withWorkflowReturn(`/portal/appointments/${item.next_appointment.id}`, here)} className={textLink}>{formatCounselingDateTime(item.next_appointment.starts_at)} · {item.next_appointment.reference_code}</Link> : <span>{formatCounselingDateTime(item.next_appointment.starts_at)} · {item.next_appointment.reference_code}</span>}{item.next_appointment.provider ? <span className="mt-1 block">{item.next_appointment.provider.display_name}</span> : null}</> : "No upcoming appointment is linked to this case."}</Fact>
          <Fact label="Next action">{!item.next_actions_available ? "Next actions are unavailable to your account." : item.next_action ? <><Link href={withWorkflowReturn(`/portal/follow-ups/${item.next_action.id}`, here)} className={textLink}>{followupActionLabel(item.next_action)}</Link><span className="mt-1 block">Due {formatCounselingDateTime(item.next_action.due_at)} · {item.next_action.assigned_to_name}</span></> : "No pending next action in this case."}</Fact>
          <Fact label="Opened">{formatCounselingDateTime(item.opened_at)} · {originDescription(item, here)}</Fact>
          {item.status === "CLOSED" && item.closure ? <>
            <Fact label="Closed">{formatCounselingDateTime(item.closure.closed_at)} · {item.closure.closed_by.display_name}</Fact>
            <Fact label="Closure reason">{closureReasonLabels[item.closure.reason]}</Fact>
            <Fact label="Outcome">{closureOutcomeLabels[item.closure.outcome]}</Fact>
          </> : null}
        </dl>
        {item.status === "CLOSED" && !query.isError && item.closure?.note ? <div className="border-t border-border px-4 py-4 sm:px-5"><h3 className="text-sm font-semibold text-brand">Confidential closure note</h3><p className="mt-2 whitespace-pre-wrap break-words text-sm">{item.closure.note}</p></div> : null}
      </Panel>

      {offers.length > 0 && canManage ? offers.map(offer => (
        <Notice
          key={offer.encounter_id}
          className="mt-5"
          action={<Button variant="secondary" disabled={linkOrigin.isPending} aria-busy={addingOfferId === offer.encounter_id} onClick={() => void addOfferedSession(item, offer.encounter_id)}>{addingOfferId === offer.encounter_id ? "Adding session…" : "Add to this case"}</Button>}
        >
          <p className="text-ink">The session recorded {formatCounselingDateTime(offer.started_at)} for {offer.appointment ? `Appointment ${offer.appointment.reference_code}` : `the ${caseOriginLabel(item.origin)} this case started from`} isn&apos;t in a case yet.</p>
          {originError ? <p role="alert" className="mt-2 text-danger">{originError}</p> : null}
        </Notice>
      )) : null}

      <CaseContinuityPanel item={item} returnTo={here} confirmed={!query.isError} />
      <CaseNextActionsPanel item={item} returnTo={here} confirmed={!query.isError} />
      <CaseAppointmentsPanel item={item} returnTo={here} confirmed={!query.isError} onLink={() => { actionStatus.dismiss(); setAppointmentOpen(true); }} onUnlink={link => { actionStatus.dismiss(); setUnlinking(link); }} />

      <Panel className="mt-5" aria-labelledby="case-sessions-heading">
        <PanelHeader title="Sessions" titleId="case-sessions-heading" context={item.session_count > 0 ? sessionCountLabel(item.session_count) : null} actions={canManage && !recordOpen ? <Button variant="secondary" onClick={() => { actionStatus.dismiss(); setAddOpen(true); }}>Add recorded session</Button> : undefined} />
        {item.sessions.length === 0 ? (
          <PanelMessage>No sessions are in this case yet.</PanelMessage>
        ) : (
          <div className={`${dataTable.scroll} relative`}>
            <table className={`${dataTable.table} min-w-[760px]`}>
              <caption className="sr-only">Completed sessions in this case</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}>Session</th>
                  <th scope="col" className={dataTable.headerCell}>Origin</th>
                  <th scope="col" className={dataTable.headerCell}>Delivery</th>
                  <th scope="col" className={dataTable.headerCell}>Recorded by</th>
                  <th scope="col" className={dataTable.headerCell}>Appointment</th>
                  {canManage ? <th scope="col" className={dataTable.headerCell}><span className="sr-only">Actions</span></th> : null}
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {item.sessions.map((session) => {
                  const when = `${formatCounselingDateTime(session.started_at)} – ${formatCounselingDateTime(session.ended_at)}`;
                  return (
                    <tr key={session.encounter_id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} min-w-56 font-normal`}>
                        {session.record_accessible
                          ? <Link href={withWorkflowReturn(`/portal/counseling/encounters/${session.encounter_id}`, here)} className={textLink}>{when}</Link>
                          : <span className="font-semibold text-ink">{when}</span>}
                      </th>
                      <td className={dataTable.cell}>{counselingEntryModeLabel(session.entry_mode)}</td>
                      <td className={dataTable.cell}>{counselingDeliveryModeLabel(session.delivery_mode)}</td>
                      <td className={dataTable.cell}><Person person={session.counselor} /></td>
                      <td className={dataTable.cell}>{session.appointment?.reference_code ?? "—"}</td>
                      {canManage ? (
                        <td className={`${dataTable.cell} text-right`}>
                          <Button variant="quiet" aria-label={`Remove the session of ${formatCounselingDateTime(session.started_at)} from this case`} onClick={() => { actionStatus.dismiss(); setRemoving(session); }}>Remove</Button>
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <CaseHistoryPanel item={item} />

      {canManage ? (
        <>
          <AddSessionDialog open={addOpen} onOpenChange={setAddOpen} caseItem={item} onChanged={applyChange} onStale={reloadAfterStale} />
          <RemoveSessionDialog session={removing} onClose={() => setRemoving(null)} caseItem={item} onChanged={applyChange} onStale={reloadAfterStale} />
          <LinkAppointmentDialog open={appointmentOpen} onOpenChange={setAppointmentOpen} caseItem={item} onChanged={applyChange} onStale={reloadAfterStale} />
          <UnlinkAppointmentDialog link={unlinking} onClose={() => setUnlinking(null)} caseItem={item} onChanged={applyChange} onStale={reloadAfterStale} />
        </>
      ) : null}
      <ActionStatus status={actionStatus.status} onDismiss={actionStatus.dismiss} />
    </article>
  );
}
