"use client";

import Link from "next/link";
import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";
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
import { RoutineCounselorEvaluationReadOnly, RoutineCounselorEvaluationWorkspace } from "@/features/routine-interviews/routine-counselor-evaluation";
import { RoutineStudentIntakeReadOnly } from "@/features/routine-interviews/routine-student-intake";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { routineEvaluationStatusLabel, routineIntakeStatusLabel } from "@/features/routine-interviews/routine-interviews-shared";
import type { EncounterOriginPreset } from "@/features/counseling/record-encounter-form";
import { RecordEncounterDialog } from "@/features/counseling/record-encounter-dialog";
import { SharedSummarySection } from "@/features/counseling/shared-summary-section";
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
import type {
  ContextHistoryKind,
  ContextHistoryStatus,
  CounselingContextHistoryResponse,
  CounselingContextInventoryResponse,
  CounselingContextOverviewResponse,
  CounselingContextSharedSummariesResponse,
  CounselingContextSupportResponse,
  CounselorRoutineDetailResponse,
} from "@/lib/api/generated/model";
import { CounselingContextAnchorType, CounselingContextInventoryStatus, CounselingEntryMode, DeliveryMode } from "@/lib/api/generated/model";
import {
  getCounselingContextGetOverviewQueryKey,
  getCounselingContextGetInventoryQueryKey,
  getCounselingContextGetSupportIndicatorsQueryKey,
  getCounselingContextListHistoryQueryKey,
  getCounselingContextListSharedSummariesQueryKey,
  useCounselingContextGetInventory,
  useCounselingContextGetOverview,
  useCounselingContextGetSupportIndicators,
  useCounselingContextListHistory,
  useCounselingContextListSharedSummaries,
} from "@/lib/api/generated/counseling/counseling";
import {
  getRoutineInterviewsGetAssignedQueryKey,
  getRoutineInterviewsListAssignedQueryKey,
  getRoutineInterviewsListEncounterCandidatesQueryKey,
  useRoutineInterviewsGetAssigned,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

type ContextTabId = "OVERVIEW" | "ROUTINE" | "INVENTORY" | "SUPPORT_INDICATORS" | "HISTORY" | "SHARED_SUMMARIES";
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

function isDeliveryMode(value: string): value is DeliveryMode {
  return Object.values(DeliveryMode).includes(value as DeliveryMode);
}

function isDirectEntryMode(value: string): value is "WALK_IN" | "CALLED_IN" | "REFERRED" {
  return value === CounselingEntryMode.WALK_IN || value === CounselingEntryMode.CALLED_IN || value === CounselingEntryMode.REFERRED;
}

function directEntryMode(value: string): CounselingEntryMode | undefined {
  return isDirectEntryMode(value) ? value : undefined;
}

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
      getCounselingContextListSharedSummariesQueryKey(anchorType, anchorId, { limit: 20 }),
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

  if (!allowed) return <CounselingUnavailable title="Counseling context unavailable" />;

  let content: ReactNode;
  if (contextUnavailable || invalidBoundary || boundaryReached || shouldHideProtectedData(overview.error) || counselingErrorCode(overview.error) === "counseling_context_not_found") {
    content = <Notice role="alert" className="max-w-3xl px-5 py-6 sm:px-6" title={<h1 className="font-heading text-2xl font-semibold text-ink">Counseling information unavailable</h1>} action={<Button variant="secondary" onClick={() => void reauthorize()}>Check again</Button>}>We cannot show this information until your access is checked again.</Notice>;
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
            <Link href="/portal/counseling" className={buttonVariants({ variant: "secondary" })}>My Counseling Encounters</Link>
          </>
        }
      >
        <p>{expired ? "This counseling view is no longer available." : counselingErrorMessage(overview.error, "Counseling information is not currently available.")}</p>
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
  const [recordOpen, setRecordOpen] = useState(false);
  const [recordUncertain, setRecordUncertain] = useState(false);
  const [recordNotice, setRecordNotice] = useState<string | null>(null);
  const [contextExpired, setContextExpired] = useState(false);
  const [contextPanelRevision, setContextPanelRevision] = useState(0);

  const directMode = anchorType === CounselingContextAnchorType.ROUTINE_INTERVIEW ? directEntryMode(overview.entry_mode) : undefined;
  const directDelivery = isDeliveryMode(overview.delivery_mode) ? overview.delivery_mode : null;
  const preset: EncounterOriginPreset | undefined = anchorType === CounselingContextAnchorType.APPOINTMENT && isDeliveryMode(overview.delivery_mode)
    ? {
        entryMode: CounselingEntryMode.APPOINTMENT,
        appointmentId: anchorId,
        studentName: overview.student.display_name,
        institutionalId: overview.student.institutional_id,
        deliveryMode: overview.delivery_mode,
      }
    : directMode && directDelivery
      ? {
          entryMode: directMode,
          studentId: overview.student.id,
          studentName: overview.student.display_name,
          institutionalId: overview.student.institutional_id,
          deliveryMode: directDelivery,
          // Recorded from this Routine Interview's workspace, so COMPASS links it on creation.
          routineInterviewId: anchorId,
        }
      : undefined;
  const encounterState = contextEncounterState(overview);
  // Linking changes the Routine Interview, so recording here also needs Routine management.
  const canRecord = access.canManageAssigned && (
    anchorType !== CounselingContextAnchorType.ROUTINE_INTERVIEW || getRoutineInterviewAccess(user).canManageAssigned
  );

  async function handleCreated() {
    const routineId = overview.routine_interview?.id;
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(anchorType, anchorId) }),
      // Recording links the Encounter to this context's Routine Interview.
      ...(routineId
        ? [
            queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineId) }),
            queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(routineId) }),
            queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() }),
          ]
        : []),
    ]);
    setRecordOpen(false);
    setContextPanelRevision((revision) => revision + 1);
    await onRefreshOverview();
  }

  async function handleAlreadyRecorded() {
    await handleCreated();
    setRecordNotice("This Routine Interview's encounter was already recorded. The latest details are now shown.");
  }

  async function handlePublished() {
    await queryClient.invalidateQueries({ queryKey: getCounselingContextListSharedSummariesQueryKey(anchorType, anchorId, { limit: 20 }) });
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
            {overview.matching_encounter && encounterState === "RECORDED" ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5">{recordNotice ? <p role="status" className="mb-2 text-sm text-ink">{recordNotice}</p> : null}<p className="text-sm text-muted">Completed interaction recorded {formatCounselingDateTime(overview.matching_encounter.started_at)} – {formatCounselingDateTime(overview.matching_encounter.ended_at)}.</p><Link href={`/portal/counseling/encounters/${overview.matching_encounter.id}`} className={buttonVariants({ variant: "secondary", className: "mt-3" })}>View encounter</Link></div>
            ) : overview.matching_encounter ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><p className="text-sm text-muted">A matching interaction recorded {formatCounselingDateTime(overview.matching_encounter.started_at)} – {formatCounselingDateTime(overview.matching_encounter.ended_at)} is not linked to this Routine Interview. If it is this interaction, choose it when finalizing the Counselor Evaluation.</p><Link href={`/portal/counseling/encounters/${overview.matching_encounter.id}`} className={buttonVariants({ variant: "secondary", className: "mt-3" })}>View encounter</Link></div>
            ) : canRecord ? (
              <div className="border-t border-brand-line px-4 py-4 sm:px-5"><p className="text-sm font-medium text-ink">Encounter not recorded</p><Button className="mt-3" disabled={recordUncertain} onClick={() => setRecordOpen(true)}>{recordUncertain ? "Recording result unconfirmed" : "Record encounter"}</Button>{preset ? <RecordEncounterDialog open={recordOpen} onOpenChange={setRecordOpen} preset={preset} onUncertain={() => setRecordUncertain(true)} onCreated={handleCreated} onAlreadyRecorded={handleAlreadyRecorded} /> : recordOpen ? <p role="alert" className="mt-3 text-sm text-danger">This interaction cannot be recorded from this page. Review its visit type and delivery mode.</p> : null}</div>
            ) : null}
          </Panel>

          <CounselingContextPanel
            key={`${anchorType}-${anchorId}-${contextPanelRevision}`}
            anchorType={anchorType}
            anchorId={anchorId}
            overview={overview}
            showInteractionFacts={false}
            access={access}
            onPublished={handlePublished}
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
  access,
  onPublished,
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
  access: ReturnType<typeof getCounselingAccess>;
  onPublished?: () => unknown;
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
    ...(available.has("SHARED_SUMMARIES") ? [{ id: "SHARED_SUMMARIES" as const, label: "Shared Summaries" }] : []),
  ];
  const tabIs = (tab: ContextTabId) => activeTab === tab;
  const inventory = useCounselingContextGetInventory(anchorType, anchorId, { query: { enabled: tabIs("INVENTORY") && available.has("INVENTORY"), retry: false } });
  const support = useCounselingContextGetSupportIndicators(anchorType, anchorId, { query: { enabled: tabIs("SUPPORT_INDICATORS") && available.has("SUPPORT_INDICATORS"), retry: false } });
  const history = useCounselingContextListHistory(anchorType, anchorId, { limit: 20 }, { query: { enabled: tabIs("HISTORY") && available.has("HISTORY"), retry: false } });
  const previousSummaries = useCounselingContextListSharedSummaries(anchorType, anchorId, { limit: 20 }, { query: { enabled: tabIs("SHARED_SUMMARIES") && available.has("SHARED_SUMMARIES") && access.canViewAssignedSummaries, retry: false } });
  const routine = useRoutineInterviewsGetAssigned(overview.routine_interview?.id ?? "", { query: { enabled: tabIs("ROUTINE") && Boolean(overview.routine_interview), retry: false } });
  const contextExpired = [inventory.error, support.error, history.error, previousSummaries.error].some((error) => counselingErrorCode(error) === "counseling_context_not_found" || shouldHideProtectedData(error));
  const activeQuery = activeTab === "INVENTORY" ? inventory : activeTab === "SUPPORT_INDICATORS" ? support : activeTab === "HISTORY" ? history : activeTab === "SHARED_SUMMARIES" ? previousSummaries : activeTab === "ROUTINE" ? routine : null;

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
            {activeTab === "SHARED_SUMMARIES" ? <SharedSummariesContext query={previousSummaries} overview={overview} access={access} onPublished={() => void onPublished?.()} /> : null}
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
        <Metadata label="Student">{overview.student.display_name}</Metadata>
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
  if ((routine.isError && !canShowLastKnownData(routine)) || !routine.data?.data) return <CounselingQueryError message={counselingErrorMessage(routine.error, "The Routine Interview could not be loaded for this account.")} onRetry={() => void routine.refetch()} />;
  const detail = routine.data.data;
  return (
    <div className="space-y-5">
      <Panel as="div">
        <PanelHeader
          title={<>Student Intake · {routineIntakeStatusLabel(detail.intake_status)}</>}
          level={3}
          description={detail.intake_status === "SUBMITTED" ? "Submitted responses are read-only for counselors." : "Student responses remain private until submission."}
        />
        {detail.intake_status === "SUBMITTED" && detail.intake ? <div className="px-4 py-4 sm:px-5"><RoutineStudentIntakeReadOnly intake={detail.intake} /></div> : <PanelMessage role="status">Student Intake is still a draft. The Student’s answers become available after they submit their Intake.</PanelMessage>}
      </Panel>
      {detail.intake_status !== "SUBMITTED" ? <Panel as="div"><PanelHeader title="Counselor Evaluation" level={3} /><PanelMessage>Counselor evaluation becomes available after the student submits the intake.</PanelMessage></Panel> : detail.evaluation_status === "FINALIZED" ? <Panel as="div"><PanelHeader title="Counselor Evaluation" level={3} description={`Finalized ${detail.evaluation_finalized_at ? formatCounselingDateTime(detail.evaluation_finalized_at) : ""} · Read-only`} /><div className="px-4 py-4 sm:px-5"><RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} /></div></Panel> : canManage ? <RoutineCounselorEvaluationWorkspace key={detail.id} routineInterviewId={detail.id} entryMode={detail.entry_mode} linkedEncounter={detail.counseling_encounter} initialEvaluation={detail.evaluation} evaluationFinalized={false} /> : <Panel as="div"><PanelHeader title="Counselor Evaluation" level={3} description="Draft evaluation · Read-only for this account." /><div className="px-4 py-4 sm:px-5"><RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} /></div></Panel>}
    </div>
  );
}

function InventoryContext({ query, overview }: { query: QueryResultWithData<CounselingContextInventoryResponse>; overview: CounselingContextOverviewResponse }) {
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading contextual Individual Inventory…</span><Skeleton className="h-10 w-1/2" /><Skeleton className="mt-4 h-80 w-full" /></div>;
  if (query.isError && !canShowLastKnownData(query)) return <CounselingQueryError message={counselingErrorMessage(query.error, "Contextual Individual Inventory could not be loaded.")} onRetry={() => void query.refetch()} />;
  const result = query.data?.data;
  if (!result?.available) {
    const unavailable: Record<string, string> = {
      [CounselingContextInventoryStatus.MISSING]: "No current submitted Individual Inventory is available for this student.",
      [CounselingContextInventoryStatus.DRAFT]: "The current Individual Inventory is still a draft and is not available for counselor review.",
      [CounselingContextInventoryStatus.SUBMITTED]: "A submitted Individual Inventory is not available here.",
    };
    return <Notice role="status">{unavailable[result?.inventory_source_status ?? CounselingContextInventoryStatus.MISSING]}</Notice>;
  }
  if (!result.inventory || result.inventory.status !== "SUBMITTED") return <Notice role="status">The current submitted Individual Inventory is not available here.</Notice>;
  return <InventoryReadOnly inventory={result.inventory} studentIdentity={{ display_name: overview.student.display_name, institutional_id: overview.student.institutional_id }} />;
}

function SupportContext({ query }: { query: QueryResultWithData<CounselingContextSupportResponse> }) {
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading contextual support indicators…</span><Skeleton className="h-12 w-full" /><Skeleton className="mt-3 h-12 w-full" /></div>;
  if (query.isError && !canShowLastKnownData(query)) return <CounselingQueryError message={counselingErrorMessage(query.error, "Contextual support indicators could not be loaded.")} onRetry={() => void query.refetch()} />;
  const result = query.data?.data;
  if (!result?.available) {
    const message = result?.inventory_source_status === CounselingContextInventoryStatus.DRAFT
      ? "Support indicators are unavailable because the current Individual Inventory is still a draft."
      : result?.inventory_source_status === CounselingContextInventoryStatus.SUBMITTED
        ? "Support indicators are unavailable here."
        : "Support indicators are unavailable because no current submitted Individual Inventory is available.";
    return <Notice role="status">{message}</Notice>;
  }
  return <Panel as="div">{result.indicators.length ? <ul className="divide-y divide-border">{result.indicators.map((indicator) => <li key={indicator.code} className="px-4 py-3 text-sm text-ink sm:px-5">{indicator.label}</li>)}</ul> : <PanelMessage>No support indicators are recorded.</PanelMessage>}</Panel>;
}

function HistoryContext({ query }: { query: QueryResultWithData<CounselingContextHistoryResponse> }) {
  if (query.isPending) return <div aria-busy="true"><span className="sr-only">Loading minimized Counseling history…</span><Skeleton className="h-14 w-full" /><Skeleton className="mt-2 h-14 w-full" /></div>;
  if (query.isError && !canShowLastKnownData(query)) return <CounselingQueryError message={counselingErrorMessage(query.error, "Counseling context history could not be loaded.")} onRetry={() => void query.refetch()} />;
  const items = query.data?.data.items ?? [];
  if (!items.length) return <Panel as="div"><PanelMessage>No contextual history is available.</PanelMessage></Panel>;
  return <Panel as="div"><ol className="divide-y divide-border">{items.map((item) => <li key={`${item.kind}-${item.id}`} className="px-4 py-3.5 sm:px-5"><p className="font-semibold text-ink">{historyKindLabels[item.kind]} · {item.title}</p><p className="mt-1 text-sm text-muted">{formatCounselingDateTime(item.occurred_at)} · {historyStatusLabels[item.status]}{item.reference_code ? ` · ${item.reference_code}` : ""}{item.delivery_mode ? ` · ${counselingDeliveryModeLabel(item.delivery_mode)}` : ""}</p>{item.provider ? <p className="mt-1 text-sm text-muted">Provider: {item.provider.display_name}</p> : null}</li>)}</ol></Panel>;
}

function SharedSummariesContext({
  query,
  overview,
  access,
  onPublished,
}: {
  query: QueryResultWithData<CounselingContextSharedSummariesResponse>;
  overview: CounselingContextOverviewResponse;
  access: ReturnType<typeof getCounselingAccess>;
  onPublished: () => void;
}) {
  if (query.isPending && access.canViewAssignedSummaries) return <div aria-busy="true"><span className="sr-only">Loading published Shared Summaries…</span><Skeleton className="h-20 w-full" /><Skeleton className="mt-2 h-20 w-full" /></div>;
  if (query.isError && !canShowLastKnownData(query) && access.canViewAssignedSummaries) return <CounselingQueryError message={counselingErrorMessage(query.error, "Previously published Shared Summaries could not be loaded.")} onRetry={() => void query.refetch()} />;
  const items = query.data?.data.items ?? [];
  const encounterId = overview.matching_encounter?.id;
  return (
    <div className="space-y-5">
      <Panel aria-labelledby="previous-shared-summaries-heading">
        <PanelHeader title="Previous published summaries" titleId="previous-shared-summaries-heading" level={3} />
        {!access.canViewAssignedSummaries ? <PanelMessage>Published shared summaries are unavailable to this account.</PanelMessage> : items.length ? <ul className="divide-y divide-border">{items.map((item) => <li key={item.id} className="px-4 py-3.5 sm:px-5"><p className="font-semibold text-ink">Counselor: {item.counselor.display_name}</p><p className="mt-1 text-sm text-muted">Counseling ended {formatCounselingDateTime(item.counseling_ended_at)} · Published {formatCounselingDateTime(item.published_at)}</p><p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{item.content}</p></li>)}</ul> : <PanelMessage>No previous published Shared Summaries are available.</PanelMessage>}
      </Panel>
      {encounterId && access.canViewAssignedSummaries ? <section aria-labelledby="current-shared-summary-heading"><h3 id="current-shared-summary-heading" className="sr-only">This encounter’s Shared Summary</h3><SharedSummarySection encounterId={encounterId} access={access} onPublished={onPublished} /></section> : null}
    </div>
  );
}
