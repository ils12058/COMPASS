"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { CounselingHelp } from "@/features/counseling/counseling-help";
import { GuidanceContextualMessages, GuidanceMessagesTrigger } from "@/features/guidance-messages/guidance-contextual-messages";
import { Button, buttonVariants } from "@/components/ui/button";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { workspaceTabClass } from "@/components/ui/workspace-tabs";
import { canShowLastKnownData, shouldHideProtectedData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { boundaryDelay, useServerBoundary } from "@/features/freshness/use-server-boundary";
import { InventoryReadOnly } from "@/features/inventory/read-only/inventory-read-only";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { RoutineCounselorEvaluationReadOnly } from "@/features/routine-interviews/routine-counselor-evaluation";
import { RoutineStudentIntakeReadOnly } from "@/features/routine-interviews/routine-student-intake";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { openCaseHref } from "@/features/counseling/cases/case-presentation";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { routineEvaluationStatusLabel, routineIntakeStatusLabel } from "@/features/routine-interviews/routine-interviews-shared";
import { contextEncounterPreset, recordEncounterPath } from "@/features/counseling/encounter-origin";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { finishCounselingNotice, finishCounselingState } from "@/features/counseling/finish-counseling-availability";
import { FinishCounselingDialog } from "@/features/counseling/finish-counseling-dialog";
import { invalidateAfterCounselingFinish } from "@/features/counseling/finish-counseling-refresh";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorCode,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingQueryError,
  CounselingUnavailable,
  CounselingWorkspaceSkeleton,
  contextEncounterState,
  contextEncounterStateLabels,
  expiredContextEncounterMessage,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import type {
  ContextHistoryKind,
  ContextHistoryStatus,
  CounselingContextHistoryResponse,
  CounselingContextInventoryResponse,
  CounselingContextOverviewResponse,
  CounselingContextSupportResponse,
  CounselingFinishResponse,
  CounselorRoutineDetailResponse,
} from "@/lib/api/generated/model";
import { AppointmentStatus, CounselingContextAnchorType, CounselingContextInventoryStatus } from "@/lib/api/generated/model";
import {
  useAppointmentsGet,
} from "@/lib/api/generated/appointments/appointments";
import {
  getCounselingContextGetInventoryQueryKey,
  getCounselingContextGetSupportIndicatorsQueryKey,
  getCounselingContextListHistoryQueryKey,
  useCounselingContextGetInventory,
  useCounselingContextGetOverview,
  useCounselingContextGetSupportIndicators,
  useCounselingContextListHistory,
  useCounselingGetEncounter,
} from "@/lib/api/generated/counseling/counseling";
import {
  useRoutineInterviewsGetAssigned,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

type ContextTabId = "OVERVIEW" | "ROUTINE" | "INVENTORY" | "SUPPORT_INDICATORS" | "HISTORY";
type ContextTab = { id: ContextTabId; label: string };
type QueryResultWithData<T> = {
  data?: { data: T };
  error: unknown;
  isPending: boolean;
  isError: boolean;
  isFetching: boolean;
  isPlaceholderData?: boolean;
  refetch: () => Promise<unknown>;
};

const historyKindLabels: Record<ContextHistoryKind, string> = {
  APPOINTMENT: "Appointment",
  REFERRAL: "Referral",
  CALL_SLIP: "Call Slip",
  ROUTINE_INTERVIEW: "Routine Interview",
};

const historyStatusLabels: Record<ContextHistoryStatus, string> = {
  SCHEDULED: "Scheduled",
  CANCELLED: "Cancelled",
  COMPLETED: "Completed",
  NO_SHOW: "No-show",
  RECORDED: "Recorded",
  RECEIVED: "Received",
  PENDING: "Pending",
  ENDED: "Ended",
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  VOIDED: "Voided",
};

function Metadata({ label, children }: { label: string; children: ReactNode }) {
  return <div className="min-w-0 py-2.5"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm text-ink">{children}</dd></div>;
}

export function CounselingWorkspace({
  anchorType,
  anchorId,
}: {
  anchorType: CounselingContextAnchorType;
  anchorId: string;
}) {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const [contextUnavailable, setContextUnavailable] = useState(false);
  const [contextRevision, setContextRevision] = useState(0);
  const access = getCounselingAccess(user);
  const allowed = access.isCounselor && access.canViewAssigned;
  const overview = useCounselingContextGetOverview(anchorType, anchorId, {
    query: { enabled: allowed, retry: false },
  });
  const validUntil = overview.data?.data.valid_until;
  const serverDate = overview.data?.headers.date;
  const invalidBoundary = Boolean(validUntil) && boundaryDelay(validUntil, serverDate, overview.dataUpdatedAt) === null;
  const boundaryReached = Boolean(validUntil) && boundaryDelay(validUntil, serverDate, overview.dataUpdatedAt) === 0;

  const clearContextReads = () => {
    for (const queryKey of [
      getCounselingContextGetInventoryQueryKey(anchorType, anchorId),
      getCounselingContextGetSupportIndicatorsQueryKey(anchorType, anchorId),
      getCounselingContextListHistoryQueryKey(anchorType, anchorId, { limit: 20 }),
    ]) queryClient.removeQueries({ queryKey, exact: true });
  };

  useServerBoundary({
    boundary: validUntil,
    serverDate,
    receivedAt: overview.dataUpdatedAt,
    onBoundary: () => {
      setContextUnavailable(true);
      clearContextReads();
    },
  });

  const reauthorize = async () => {
    const result = await overview.refetch();
    const next = result.data;
    if (result.isSuccess && next && (boundaryDelay(next.data.valid_until, next.headers.date, result.dataUpdatedAt) ?? 0) > 0) {
      setContextUnavailable(false);
      setContextRevision((revision) => revision + 1);
    }
  };

  const invalidateContext = (invalid: boolean) => {
    if (!invalid) return;
    setContextUnavailable(true);
    clearContextReads();
  };

  if (!allowed) return <CounselingUnavailable title="Counseling" />;

  let content: ReactNode;
  if (contextUnavailable || invalidBoundary || boundaryReached || shouldHideProtectedData(overview.error) || counselingErrorCode(overview.error) === "counseling_context_not_found") {
    content = <Notice role="alert" className="max-w-3xl px-5 py-6 sm:px-6" title={<h1 className="font-heading text-2xl font-semibold text-ink">Check Counseling access</h1>} action={<Button variant="secondary" onClick={() => void reauthorize()}>Check again</Button>}>Check your access again to view this information.</Notice>;
  } else if (overview.isPending) {
    content = <CounselingWorkspaceSkeleton />;
  } else if ((overview.isError && !canShowLastKnownData(overview)) || !overview.data?.data) {
    const expired = counselingErrorCode(overview.error) === "counseling_context_not_found";
    content = (
      <Notice
        role="alert"
        className="max-w-3xl px-5 py-6 sm:px-6"
        title={<h1 className="font-heading text-2xl font-semibold text-ink">Counseling context</h1>}
        action={
          <>
            {expired ? null : <Button variant="secondary" onClick={() => void overview.refetch()}>Retry</Button>}
            <Link href="/portal/counseling/encounters" className={buttonVariants({ variant: "secondary" })}>Session records</Link>
          </>
        }
      >
        <p>{expired ? "This counseling view is no longer available." : counselingErrorMessage(overview.error, "Couldn't load Counseling information. Try again.")}</p>
        {expired ? <p className="mt-2">Return to your encounters to continue.</p> : null}
      </Notice>
    );
  } else {
    content = <><CounselingWorkspaceContent key={contextRevision} anchorType={anchorType} anchorId={anchorId} overview={overview.data.data} access={access} onRefreshOverview={() => overview.refetch()} onContextInvalidated={invalidateContext} />{overview.isError ? <RefreshFailureNotice onRetry={() => void overview.refetch()} /> : null}</>;
  }

  // Messages belongs to the Appointment, not to this time-bounded context (ADR-103): the panel and
  // its draft stay while the context below expires, and the thread stays in /portal/messages. A
  // Routine Interview context has no Counseling thread anchor, so it offers no Messages.
  return (
    <GuidanceContextualMessages
      appointmentId={anchorId}
      counterpartName={overview.data?.data.student.display_name ?? "the Student"}
      enabled={anchorType === CounselingContextAnchorType.APPOINTMENT}
    >
      {content}
    </GuidanceContextualMessages>
  );
}

function CounselingWorkspaceContent({
  anchorType,
  anchorId,
  overview,
  access,
  onRefreshOverview,
  onContextInvalidated,
}: {
  anchorType: CounselingContextAnchorType;
  anchorId: string;
  overview: CounselingContextOverviewResponse;
  access: ReturnType<typeof getCounselingAccess>;
  onRefreshOverview: () => unknown;
  onContextInvalidated: (invalid: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { user } = usePortalSession();
  const [finishOpen, setFinishOpen] = useState(false);
  const [finishNotice, setFinishNotice] = useState<string | null>(null);
  const encounterActionsRef = useRef<HTMLDivElement>(null);
  const [contextExpired, setContextExpired] = useState(false);

  // Recording happens on the dedicated Record Counseling Encounter page (EC-WS-2); this read-only
  // context only says whether it can, and links there.
  const preset = contextEncounterPreset(anchorType, anchorId, overview);
  const encounterState = contextEncounterState(overview);
  const assignedEncounter = useCounselingGetEncounter(overview.matching_encounter?.id ?? "", {
    query: { enabled: access.canViewAssigned && Boolean(overview.matching_encounter), retry: false },
  });
  const canOpenEncounter = !assignedEncounter.isError &&
    assignedEncounter.data?.data.id === overview.matching_encounter?.id &&
    assignedEncounter.data?.data.counselor.id === user?.id &&
    assignedEncounter.data?.data.student.id === overview.student.id;
  // Linking changes the Routine Interview, so recording here also needs Routine management.
  const canRecord = access.canManageAssigned && (
    anchorType !== CounselingContextAnchorType.ROUTINE_INTERVIEW || getRoutineInterviewAccess(user).canManageAssigned
  );
  // Finish reads the Appointment itself: its status and Encounter fact are not part of the
  // time-bounded context projection. Only a confirmed read is used, never last-known data.
  const appointmentQuery = useAppointmentsGet(anchorId, {
    query: {
      enabled: anchorType === CounselingContextAnchorType.APPOINTMENT && access.canViewAssigned,
      retry: false,
    },
  });
  const appointment = anchorType === CounselingContextAnchorType.APPOINTMENT && appointmentQuery.isSuccess
    ? appointmentQuery.data.data
    : undefined;
  const finishState = appointment
    ? finishCounselingState(appointment, {
        canFinish: access.canManageAssigned && getAppointmentAccess(user).canManage,
      })
    : "UNAVAILABLE";
  const finishOffered = encounterState === "NOT_RECORDED" && finishState === "OFFERED";

  async function handleFinished(result: CounselingFinishResponse, wasCompleted: boolean) {
    setFinishOpen(false);
    await invalidateAfterCounselingFinish(queryClient, {
      appointmentId: anchorId,
      routineInterviewId: result.routine_interview_id,
    });
    setFinishNotice(finishCounselingNotice(result, { wasCompleted }));
    await onRefreshOverview();
  }

  // A conflict means the Appointment moved under this dialog: refresh and report, never resubmit.
  async function handleFinishStale(message: string) {
    setFinishOpen(false);
    setFinishNotice(`${message} The latest details are now shown.`);
    await onRefreshOverview();
  }

  async function checkFinishAgain(): Promise<boolean> {
    const result = await appointmentQuery.refetch();
    const latest = result.data?.data;
    if (!(latest?.status === AppointmentStatus.COMPLETED && latest?.counseling_encounter_recorded === true)) {
      return false;
    }
    setFinishOpen(false);
    await invalidateAfterCounselingFinish(queryClient, { appointmentId: anchorId });
    setFinishNotice("Counseling finished. The latest details are now shown.");
    await onRefreshOverview();
    return true;
  }

  useEffect(() => {
    if (contextExpired) onContextInvalidated(true);
  }, [contextExpired, onContextInvalidated]);

  const expiredEncounterMessage = expiredContextEncounterMessage(Boolean(overview.matching_encounter));

  return (
    <div>
      <CounselingPageHeading
        title="Counseling workspace"
        help={<CounselingHelp />}
        back={<Link href="/portal/counseling" className={pageBackLinkClass}>Back to Counseling</Link>}
        action={anchorType === CounselingContextAnchorType.APPOINTMENT ? <GuidanceMessagesTrigger /> : undefined}
      />
      {contextExpired ? (
        <Notice role="alert" tone="warning" title={<h2 className="font-heading text-xl font-semibold text-ink">Counseling workspace is no longer available</h2>}><p className="text-muted">These interaction details can no longer be reviewed here.</p>{expiredEncounterMessage ? <p className="mt-2 text-muted">{expiredEncounterMessage}</p> : null}</Notice>
      ) : (
        // Columns follow this workspace's own width, so an open Messages panel stacks them.
        <div className="@container/counseling"><div className="grid items-start gap-5 @[58rem]/counseling:grid-cols-[minmax(15rem,0.8fr)_minmax(0,2fr)]">
          <Panel aria-labelledby="counseling-interaction-heading">
            <PanelHeader title="Interaction" titleId="counseling-interaction-heading" />
            <dl className="divide-y divide-border px-4 sm:px-5">
              <Metadata label="Origin">{counselingEntryModeLabel(overview.entry_mode)}</Metadata>
              <Metadata label="Delivery">{counselingDeliveryModeLabel(overview.delivery_mode)}</Metadata>
              <Metadata label="Available until">{formatCounselingDateTime(overview.valid_until)}</Metadata>
              <Metadata label="Routine Interview">{overview.routine_interview ? `${routineIntakeStatusLabel(overview.routine_interview.intake_status)} Intake · ${routineEvaluationStatusLabel(overview.routine_interview.evaluation_status)} Evaluation` : "No linked Routine Interview"}</Metadata>
              <Metadata label="Counseling Encounter">{contextEncounterStateLabels[encounterState]}</Metadata>
            </dl>
            <div ref={encounterActionsRef}>
            {finishNotice ? <p role="status" className="mb-2 text-sm text-ink">{finishNotice}</p> : null}
            {overview.matching_encounter && encounterState === "RECORDED" ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><p className="text-sm text-muted">Completed interaction recorded {formatCounselingDateTime(overview.matching_encounter.started_at)} – {formatCounselingDateTime(overview.matching_encounter.ended_at)}.</p>{canOpenEncounter ? <Link href={`/portal/counseling/encounters/${overview.matching_encounter.id}`} className={buttonVariants({ variant: "secondary", className: "mt-3" })}>View encounter</Link> : null}</div>
            ) : overview.matching_encounter ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><p className="text-sm text-muted">A matching interaction recorded {formatCounselingDateTime(overview.matching_encounter.started_at)} – {formatCounselingDateTime(overview.matching_encounter.ended_at)} is not linked to this Routine Interview. If it is this interaction, choose it when finalizing the Counselor Evaluation.</p>{canOpenEncounter ? <Link href={`/portal/counseling/encounters/${overview.matching_encounter.id}`} className={buttonVariants({ variant: "secondary", className: "mt-3" })}>View encounter</Link> : null}</div>
            ) : anchorType === CounselingContextAnchorType.APPOINTMENT &&
              appointment?.counseling_encounter_recorded === true &&
              !overview.matching_encounter ? (
              // The Appointment's own Encounter fact comes from the Appointment read, so this still
              // shows when the context window no longer projects the record.
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><p className="text-sm text-muted">A Counseling Encounter is recorded for this Appointment. Review it in My Counseling Encounters.</p><Link href="/portal/counseling/encounters" className={buttonVariants({ variant: "secondary", className: "mt-3" })}>View encounters</Link></div>
            ) : canRecord && finishOffered ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><Button onClick={() => { setFinishNotice(null); setFinishOpen(true); }}>Finish counseling</Button><p className="mt-3 text-sm text-muted">{appointment?.status === AppointmentStatus.COMPLETED ? "Records the Encounter for this completed Appointment." : "Records the Encounter and completes this Appointment."}</p></div>
            ) : canRecord && preset ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><GuardedPortalLink href={recordEncounterPath(anchorType, anchorId)} className={buttonVariants({ variant: "secondary" })}>Record encounter</GuardedPortalLink><p className="mt-3 text-sm text-muted">Opens the Record Counseling Encounter page.</p></div>
            ) : canRecord ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><p className="text-sm text-muted">This interaction cannot be recorded here. Review its visit type and delivery mode.</p></div>
            ) : null}
            </div>
            {access.canManageAssigned ? (
              <div className="border-t border-brand-line px-4 py-3 sm:px-5"><GuardedPortalLink href={openCaseHref({ origin: anchorType === CounselingContextAnchorType.APPOINTMENT ? "APPOINTMENT" : "ROUTINE_INTERVIEW", sourceId: anchorId })} className="inline-flex min-h-11 items-center text-sm font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open a case from this {anchorType === CounselingContextAnchorType.APPOINTMENT ? "Appointment" : "Routine Interview"}</GuardedPortalLink></div>
            ) : null}
          </Panel>
          {appointment ? (
            <FinishCounselingDialog
              open={finishOpen}
              onOpenChange={setFinishOpen}
              appointment={appointment}
              onFinished={handleFinished}
              onStale={handleFinishStale}
              onCheckAgain={checkFinishAgain}
              onUncertainClose={() => setFinishNotice("The finish result is not confirmed. Check the Appointment details before trying again.")}
              // Finishing replaces the opener, so focus moves back to the action that remains.
              onCloseAutoFocus={(event) => {
                const action = encounterActionsRef.current?.querySelector<HTMLElement>("a, button");
                if (!action) return;
                event.preventDefault();
                action.focus();
              }}
            />
          ) : null}

          <CounselingContextPanel
            key={`${anchorType}-${anchorId}`}
            anchorType={anchorType}
            anchorId={anchorId}
            overview={overview}
            showInteractionFacts={false}
            onContextExpiredChange={setContextExpired}
          />
        </div></div>
      )}
    </div>
  );
}

export function CounselingContextPanel({
  anchorType,
  anchorId,
  overview,
  showInteractionFacts = true,
  showHeading = true,
  onContextExpiredChange,
}: {
  anchorType: CounselingContextAnchorType;
  anchorId: string;
  overview: CounselingContextOverviewResponse;
  // The standalone workspace already shows these facts in its Interaction panel. Embedded
  // workspaces retain them here, including the confidential-context access deadline.
  showInteractionFacts?: boolean;
  // False where a surrounding section already names it, such as E-Counseling's collapsible
  // Student information.
  showHeading?: boolean;
  onContextExpiredChange?: (expired: boolean) => void;
}) {
  const { user } = usePortalSession();
  const routineAccess = getRoutineInterviewAccess(user);
  const [activeTab, setActiveTab] = useState<ContextTabId>("OVERVIEW");
  const available = new Set(overview.available_sections);
  const tabs: ContextTab[] = [
    { id: "OVERVIEW", label: "Overview" },
    ...(overview.routine_interview ? [{ id: "ROUTINE" as const, label: "Routine Interview" }] : []),
    ...(available.has("INVENTORY") ? [{ id: "INVENTORY" as const, label: "Inventory" }] : []),
    ...(available.has("SUPPORT_INDICATORS") ? [{ id: "SUPPORT_INDICATORS" as const, label: "Support" }] : []),
    ...(available.has("HISTORY") ? [{ id: "HISTORY" as const, label: "History" }] : []),
  ];
  const tabIs = (tab: ContextTabId) => activeTab === tab;
  const inventory = useCounselingContextGetInventory(anchorType, anchorId, { query: { enabled: tabIs("INVENTORY") && available.has("INVENTORY"), retry: false } });
  const support = useCounselingContextGetSupportIndicators(anchorType, anchorId, { query: { enabled: tabIs("SUPPORT_INDICATORS") && available.has("SUPPORT_INDICATORS"), retry: false } });
  const history = useCounselingContextListHistory(anchorType, anchorId, { limit: 20 }, { query: { enabled: tabIs("HISTORY") && available.has("HISTORY"), retry: false } });
  const routine = useRoutineInterviewsGetAssigned(overview.routine_interview?.id ?? "", { query: { enabled: tabIs("ROUTINE") && Boolean(overview.routine_interview), retry: false } });
  const contextExpired = [inventory.error, support.error, history.error].some((error) => counselingErrorCode(error) === "counseling_context_not_found" || shouldHideProtectedData(error));
  const activeQuery = activeTab === "INVENTORY" ? inventory : activeTab === "SUPPORT_INDICATORS" ? support : activeTab === "HISTORY" ? history : activeTab === "ROUTINE" ? routine : null;

  useEffect(() => {
    onContextExpiredChange?.(contextExpired);
  }, [contextExpired, onContextExpiredChange]);

  function handleTabKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const current = tabs.findIndex((tab) => tab.id === activeTab);
    let next = current;
    if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    const tab = tabs[next];
    setActiveTab(tab.id);
    document.getElementById(`counseling-context-tab-${tab.id}`)?.focus();
  }

  return (
    <section className="min-w-0" aria-label="Student Counseling context">
      {showHeading ? <h2 className="font-heading text-lg font-semibold text-ink">Student information</h2> : null}
      {contextExpired ? (
        <Notice role="status" className={showHeading ? "mt-3" : undefined}>Student information isn’t available right now.</Notice>
      ) : (
        <>
          {/* Tabs sit on the canvas; each section brings its own surface. */}
          <div role="tablist" aria-label="Counseling context sections" onKeyDown={handleTabKeyDown} className={`${showHeading ? "mt-2 " : ""}flex max-w-full gap-x-5 overflow-x-auto border-b border-brand-line`}>
            {tabs.map((tab) => <button key={tab.id} id={`counseling-context-tab-${tab.id}`} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls="counseling-context-panel" tabIndex={activeTab === tab.id ? 0 : -1} onClick={() => setActiveTab(tab.id)} className={`shrink-0 ${workspaceTabClass(activeTab === tab.id)}`}>{tab.label}</button>)}
          </div>
          <div id="counseling-context-panel" role="tabpanel" aria-labelledby={`counseling-context-tab-${activeTab}`} tabIndex={0} className="min-w-0 pt-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            {activeQuery && canShowLastKnownData(activeQuery) ? <RefreshFailureNotice onRetry={() => void activeQuery.refetch()} retrying={activeQuery.isFetching} /> : null}
            {activeQuery?.isFetching && activeQuery.data && !activeQuery.isError ? <p role="status" className="text-sm text-muted">Refreshing…</p> : null}
            {activeTab === "OVERVIEW" ? <ContextOverview overview={overview} showInteractionFacts={showInteractionFacts} /> : null}
            {activeTab === "ROUTINE" ? <RoutineContext routine={routine} canManage={routineAccess.canManageAssigned} /> : null}
            {activeTab === "INVENTORY" ? <InventoryContext query={inventory} overview={overview} /> : null}
            {activeTab === "SUPPORT_INDICATORS" ? <SupportContext query={support} /> : null}
            {activeTab === "HISTORY" ? <HistoryContext query={history} /> : null}
          </div>
        </>
      )}
    </section>
  );
}

function ContextOverview({ overview, showInteractionFacts }: { overview: CounselingContextOverviewResponse; showInteractionFacts: boolean }) {
  return (
    <Panel as="div">
      <dl className="grid gap-x-8 px-4 py-2 sm:grid-cols-2 sm:px-5">
        <Metadata label="Student"><span className="inline-flex items-center gap-2"><PersonAvatar displayName={overview.student.display_name} photoUrl={overview.student.profile_photo_url} photoUpdatedAt={overview.student.profile_photo_updated_at} size="compact" />{overview.student.display_name}</span></Metadata>
        <Metadata label="Institutional ID">{overview.student.institutional_id ?? "Not provided"}</Metadata>
        <Metadata label="Campus">{overview.student.campus?.name ?? "Not provided"}</Metadata>
        <Metadata label="College">{overview.student.college?.name ?? "Not provided"}</Metadata>
        <Metadata label="Program">{overview.student.program?.name ?? "Not provided"}</Metadata>
        <Metadata label="Year level">{overview.student.year_level ?? "Not provided"}</Metadata>
        {showInteractionFacts ? <>
          <Metadata label="Origin">{counselingEntryModeLabel(overview.entry_mode)}</Metadata>
          <Metadata label="Delivery">{counselingDeliveryModeLabel(overview.delivery_mode)}</Metadata>
          <Metadata label="Available until">{formatCounselingDateTime(overview.valid_until)}</Metadata>
          <Metadata label="Routine Interview">{overview.routine_interview ? `${routineIntakeStatusLabel(overview.routine_interview.intake_status)} Intake · ${routineEvaluationStatusLabel(overview.routine_interview.evaluation_status)} Evaluation` : "No linked Routine Interview"}</Metadata>
          <Metadata label="Counseling Encounter">{contextEncounterStateLabels[contextEncounterState(overview)]}</Metadata>
        </> : null}
      </dl>
    </Panel>
  );
}

function RoutineContext({ routine, canManage }: { routine: QueryResultWithData<CounselorRoutineDetailResponse>; canManage: boolean }) {
  if (routine.isPending) return <div aria-busy="true"><span className="sr-only">Loading assigned Routine Interview…</span><Skeleton className="h-12 w-full" /><Skeleton className="mt-3 h-56 w-full" /></div>;
  if ((routine.isError && !canShowLastKnownData(routine)) || !routine.data?.data) return <CounselingQueryError message={counselingErrorMessage(routine.error, "Couldn't load the Routine Interview.")} onRetry={() => void routine.refetch()} />;
  const detail = routine.data.data;
  return (
    <div className="space-y-5">
      <Panel as="div">
        <PanelHeader
          title={<>Student Intake · {routineIntakeStatusLabel(detail.intake_status)}</>}
          level={3}
          description={detail.intake_status === "SUBMITTED" ? "Submitted responses are read-only for Counselors." : "Student responses remain private until submission."}
        />
        {detail.intake_status === "SUBMITTED" && detail.intake ? <div className="px-4 py-4 sm:px-5"><RoutineStudentIntakeReadOnly intake={detail.intake} /></div> : <PanelMessage role="status">Student Intake is still a draft. The Student’s answers become available after they submit their Intake.</PanelMessage>}
      </Panel>
      {detail.intake_status !== "SUBMITTED" ? <Panel as="div"><PanelHeader title="Counselor Evaluation" level={3} /><PanelMessage>Counselor evaluation becomes available after the Student submits the intake.</PanelMessage></Panel> : detail.evaluation_status === "FINALIZED" ? <Panel as="div"><PanelHeader title="Counselor Evaluation" level={3} description={`Finalized ${detail.evaluation_finalized_at ? formatCounselingDateTime(detail.evaluation_finalized_at) : ""} · Read-only`} /><div className="px-4 py-4 sm:px-5"><RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} /></div></Panel> : canManage ? <Panel as="div"><PanelHeader title="Counselor Evaluation" level={3} description="Draft evaluation · Edited on the Routine Interview." /><div className="px-4 py-4 sm:px-5"><p className="text-sm text-muted">The evaluation is written, saved and finalized on its Routine Interview. This workspace only shows it.</p><GuardedPortalLink href={`/portal/routine-interviews/${encodeURIComponent(detail.id)}`} className={buttonVariants({ variant: "secondary", className: "mt-3" })}>Open Routine Interview</GuardedPortalLink></div></Panel> : <Panel as="div"><PanelHeader title="Counselor Evaluation" level={3} description="Draft evaluation · Read-only for this account." /><div className="px-4 py-4 sm:px-5"><RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} /></div></Panel>}
    </div>
  );
}

function InventoryContext({ query, overview }: { query: QueryResultWithData<CounselingContextInventoryResponse>; overview: CounselingContextOverviewResponse }) {
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading contextual Individual Inventory…</span><Skeleton className="h-10 w-1/2" /><Skeleton className="mt-4 h-80 w-full" /></div>;
  if (query.isError && !canShowLastKnownData(query)) return <CounselingQueryError message={counselingErrorMessage(query.error, "Couldn't load the Individual Inventory. Try again.")} onRetry={() => void query.refetch()} />;
  const result = query.data?.data;
  if (!result?.available) {
    const unavailable: Record<string, string> = {
      [CounselingContextInventoryStatus.MISSING]: "No current submitted Individual Inventory is available for this Student.",
      [CounselingContextInventoryStatus.DRAFT]: "The current Individual Inventory is still a draft and is not available for Counselor review.",
      [CounselingContextInventoryStatus.SUBMITTED]: "A submitted Individual Inventory is not available here.",
    };
    return <Notice role="status">{unavailable[result?.inventory_source_status ?? CounselingContextInventoryStatus.MISSING]}</Notice>;
  }
  if (!result.inventory || result.inventory.status !== "SUBMITTED") return <Notice role="status">The current submitted Individual Inventory is not available here.</Notice>;
  return <InventoryReadOnly inventory={result.inventory} studentIdentity={{ display_name: overview.student.display_name, institutional_id: overview.student.institutional_id }} />;
}

function SupportContext({ query }: { query: QueryResultWithData<CounselingContextSupportResponse> }) {
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading support details…</span><Skeleton className="h-12 w-full" /><Skeleton className="mt-3 h-12 w-full" /></div>;
  if (query.isError && !canShowLastKnownData(query)) return <CounselingQueryError message={counselingErrorMessage(query.error, "Couldn't load support details. Try again.")} onRetry={() => void query.refetch()} />;
  const result = query.data?.data;
  if (!result?.available) {
    const message = result?.inventory_source_status === CounselingContextInventoryStatus.DRAFT
      ? "Support details appear after the Student submits this year's Individual Inventory."
      : result?.inventory_source_status === CounselingContextInventoryStatus.SUBMITTED
        ? "You don't have access to support details here."
        : "Support details appear after the Student submits this year's Individual Inventory.";
    return <Notice role="status">{message}</Notice>;
  }
  return <Panel as="div">{result.indicators.length ? <ul className="divide-y divide-border">{result.indicators.map((indicator) => <li key={indicator.code} className="px-4 py-3 text-sm text-ink sm:px-5">{indicator.label}</li>)}</ul> : <PanelMessage>No support indicators are recorded.</PanelMessage>}</Panel>;
}

function HistoryContext({ query }: { query: QueryResultWithData<CounselingContextHistoryResponse> }) {
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading Counseling history…</span><Skeleton className="h-14 w-full" /><Skeleton className="mt-2 h-14 w-full" /></div>;
  if (query.isError && !canShowLastKnownData(query)) return <CounselingQueryError message={counselingErrorMessage(query.error, "Couldn't load Counseling history. Try again.")} onRetry={() => void query.refetch()} />;
  const items = query.data?.data.items ?? [];
  if (!items.length) return <Panel as="div"><PanelMessage>No Counseling history is available here.</PanelMessage></Panel>;
  return <Panel as="div"><ol className="divide-y divide-border">{items.map((item) => <li key={`${item.kind}-${item.id}`} className="px-4 py-3.5 sm:px-5"><p className="font-semibold text-ink">{historyKindLabels[item.kind]} · {item.title}</p><p className="mt-1 text-sm text-muted">{formatCounselingDateTime(item.occurred_at)} · {historyStatusLabels[item.status]}{item.reference_code ? ` · ${item.reference_code}` : ""}{item.delivery_mode ? ` · ${counselingDeliveryModeLabel(item.delivery_mode)}` : ""}</p>{item.provider ? <p className="mt-1 text-sm text-muted">Counselor: {item.provider.display_name}</p> : null}</li>)}</ol></Panel>;
}
