"use client";

import { CircleAlert, ListPlus, NotebookPen, X } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ActionStatus, useActionStatus } from "@/components/ui/action-status";
import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { Notice } from "@/components/ui/notice";
import { PageAction } from "@/components/ui/page-action";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import {
  caseErrorMessage,
  caseEventSummary,
  caseOriginLabel,
  CASES_PATH,
  sessionCountLabel,
} from "@/features/counseling/cases/case-presentation";
import { AddSessionDialog, RemoveSessionDialog } from "@/features/counseling/cases/case-session-dialogs";
import { CaseStatusBadge } from "@/features/counseling/cases/case-status-badge";
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
import {
  getCounselingGetCaseQueryKey,
  getCounselingListMyCasesQueryKey,
  getCounselingListMyEncountersQueryKey,
  useCounselingGetCase,
  useCounselingLinkCaseSession,
} from "@/lib/api/generated/counseling/counseling";
import type {
  CounselingCaseDetailResponse,
  CounselingCaseSessionResponse,
} from "@/lib/api/generated/model";

const textLink = "font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";
const backLink = <Link href={CASES_PATH} className={pageBackLinkClass}>Back to Counseling</Link>;

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <div className="min-w-0"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm text-ink">{children}</dd></div>;
}

function Person({ person }: { person: { display_name: string; profile_photo_url: string | null; profile_photo_updated_at: string | null } }) {
  return <span className="inline-flex items-center gap-2"><PersonAvatar displayName={person.display_name} photoUrl={person.profile_photo_url} photoUpdatedAt={person.profile_photo_updated_at} size="compact" />{person.display_name}</span>;
}

// Where the case started. The originating record is named only while it is still the reader's own.
function originDescription(item: CounselingCaseDetailResponse): ReactNode {
  const label = caseOriginLabel(item.origin);
  if (item.source.appointment) {
    return <>{label} <Link href={`/portal/appointments/${item.source.appointment.id}`} className={textLink}>{item.source.appointment.reference_code}</Link></>;
  }
  if (item.source.encounter_id) {
    return <Link href={`/portal/counseling/encounters/${item.source.encounter_id}`} className={textLink}>{label}</Link>;
  }
  if (item.source.routine_interview_id) {
    return <Link href={`/portal/routine-interviews/${item.source.routine_interview_id}`} className={textLink}>{label}</Link>;
  }
  return label;
}

export function CaseOverviewPage({ caseId }: { caseId: string }) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const queryClient = useQueryClient();
  const allowed = access.isCounselor && access.canViewAssigned;
  const query = useCounselingGetCase(caseId, { query: { enabled: allowed, retry: false } });
  const actionStatus = useActionStatus();
  const linkOrigin = useCounselingLinkCaseSession({ mutation: { retry: false } });
  const [recordOpen, setRecordOpen] = useState(false);
  const [recordUncertain, setRecordUncertain] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [removing, setRemoving] = useState<CounselingCaseSessionResponse | null>(null);
  // Persistent, because the reader has to review the case again before acting.
  const [notice, setNotice] = useState<string | null>(null);
  const [originError, setOriginError] = useState<string | null>(null);
  const item = query.data?.data;

  if (!allowed) return <CounselingUnavailable title="Counseling case" />;
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

  async function addOriginSession(current: CounselingCaseDetailResponse) {
    if (!current.unlinked_origin_session || linkOrigin.isPending) return;
    setOriginError(null);
    actionStatus.dismiss();
    try {
      const response = await linkOrigin.mutateAsync({
        caseId,
        data: { encounter_id: current.unlinked_origin_session.encounter_id, expected_version: current.version },
      });
      applyChange(response.data, "Session added to this case.");
    } catch (caught) {
      setOriginError(caseErrorMessage(caught, "The session couldn't be added. Check the case and try again."));
      void query.refetch();
    }
  }

  const canManage = item.can_manage && !query.isError;
  const origin = item.unlinked_origin_session;

  return (
    <article>
      <CounselingPageHeading
        title={item.student.display_name}
        description={`Case ${item.reference_code}${item.student.institutional_id ? ` · Institutional ID ${item.student.institutional_id}` : ""}`}
        back={backLink}
        action={canManage ? (
          <>
            {recordUncertain ? (
              <PageAction icon={CircleAlert} label="Unconfirmed" labelDetail="recording result" disabled />
            ) : (
              <PageAction
                icon={recordOpen ? X : NotebookPen}
                label={recordOpen ? "Close" : "Record session"}
                labelDetail={recordOpen ? "recording" : "for this case"}
                variant={recordOpen ? "secondary" : "primary"}
                aria-expanded={recordOpen}
                onClick={() => { actionStatus.dismiss(); setRecordOpen((open) => !open); }}
              />
            )}
            {recordOpen ? null : (
              <PageAction icon={ListPlus} label="Add recorded session" variant="secondary" onClick={() => { actionStatus.dismiss(); setAddOpen(true); }} />
            )}
          </>
        ) : undefined}
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
          <Fact label="Opened">{formatCounselingDateTime(item.opened_at)} · {originDescription(item)}</Fact>
        </dl>
      </Panel>

      {origin && canManage ? (
        <Notice
          className="mt-5"
          action={<Button variant="secondary" disabled={linkOrigin.isPending} aria-busy={linkOrigin.isPending} onClick={() => void addOriginSession(item)}>{linkOrigin.isPending ? "Adding session…" : "Add to this case"}</Button>}
        >
          <p className="text-ink">The session recorded {formatCounselingDateTime(origin.started_at)} for the {caseOriginLabel(item.origin)} this case started from isn&apos;t in the case yet.</p>
          {originError ? <p role="alert" className="mt-2 text-danger">{originError}</p> : null}
        </Notice>
      ) : null}

      <Panel className="mt-5" aria-labelledby="case-sessions-heading">
        <PanelHeader title="Sessions" titleId="case-sessions-heading" context={item.session_count > 0 ? sessionCountLabel(item.session_count) : null} />
        {item.sessions.length === 0 ? (
          <PanelMessage>No sessions are in this case yet.</PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
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
                          ? <Link href={`/portal/counseling/encounters/${session.encounter_id}`} className={textLink}>{when}</Link>
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

      <Panel className="mt-5" aria-labelledby="case-history-heading">
        <PanelHeader title="Case history" titleId="case-history-heading" />
        <ol className="divide-y divide-border">
          {item.history.map((event) => (
            <li key={event.id} className="px-4 py-3 sm:px-5">
              <p className="text-sm text-ink">{caseEventSummary(event)}</p>
              <p className="mt-0.5 text-xs text-muted">{formatCounselingDateTime(event.occurred_at)} · {event.actor.display_name}{event.primary_counselor.id !== event.actor.id ? ` · Responsible counselor: ${event.primary_counselor.display_name}` : ""}</p>
            </li>
          ))}
        </ol>
      </Panel>

      {canManage ? (
        <>
          <AddSessionDialog open={addOpen} onOpenChange={setAddOpen} caseItem={item} onChanged={applyChange} onStale={reloadAfterStale} />
          <RemoveSessionDialog session={removing} onClose={() => setRemoving(null)} caseItem={item} onChanged={applyChange} onStale={reloadAfterStale} />
        </>
      ) : null}
      <ActionStatus status={actionStatus.status} onDismiss={actionStatus.dismiss} />
    </article>
  );
}
