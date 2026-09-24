"use client";

import Link from "next/link";
import { useEffect, useState, type KeyboardEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { InventoryReadOnly } from "@/features/inventory/read-only/inventory-read-only";
import { RoutineCounselorEvaluationReadOnly, RoutineCounselorEvaluationWorkspace } from "@/features/routine-interviews/routine-counselor-evaluation";
import { RoutineStudentIntakeReadOnly } from "@/features/routine-interviews/routine-student-intake";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { routineIntakeStatusLabel } from "@/features/routine-interviews/routine-interviews-shared";
import type { EncounterOriginPreset } from "@/features/counseling/record-encounter-form";
import { RecordEncounterForm } from "@/features/counseling/record-encounter-form";
import { SharedSummarySection } from "@/features/counseling/shared-summary-section";
import {
  counselingDeliveryModeLabel,
  counselingEntryModeLabel,
  counselingErrorCode,
  counselingErrorMessage,
  CounselingPageHeading,
  CounselingQueryError,
  CounselingUnavailable,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import type {
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
  getCounselingContextListSharedSummariesQueryKey,
  useCounselingContextGetInventory,
  useCounselingContextGetOverview,
  useCounselingContextGetSupportIndicators,
  useCounselingContextListHistory,
  useCounselingContextListSharedSummaries,
} from "@/lib/api/generated/counseling/counseling";
import { useRoutineInterviewsGetAssigned } from "@/lib/api/generated/routine-interviews/routine-interviews";
import { getRoutineInterviewsListEncounterCandidatesQueryKey } from "@/lib/api/generated/routine-interviews/routine-interviews";

type ContextTabId = "OVERVIEW" | "ROUTINE" | "INVENTORY" | "SUPPORT_INDICATORS" | "HISTORY" | "SHARED_SUMMARIES";
type ContextTab = { id: ContextTabId; label: string };
type QueryResultWithData<T> = {
  data?: { data: T };
  error: unknown;
  isPending: boolean;
  isError: boolean;
  refetch: () => Promise<unknown>;
};

function simpleLabel(value: string): string {
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

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
  return <div className="border-b border-border/70 py-3"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm text-ink">{children}</dd></div>;
}

export function CounselingWorkspace({
  anchorType,
  anchorId,
}: {
  anchorType: CounselingContextAnchorType;
  anchorId: string;
}) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const allowed = access.isCounselor && (access.canViewAssigned || access.canManageAssigned);
  const overview = useCounselingContextGetOverview(anchorType, anchorId, {
    query: { enabled: allowed, retry: false },
  });

  if (!allowed) return <CounselingUnavailable title="Counseling context unavailable" />;
  if (overview.isPending) return <div aria-busy="true" aria-label="Loading Counseling context"><Skeleton className="h-10 w-2/3" /><Skeleton className="mt-5 h-32 w-full" /><Skeleton className="mt-5 h-72 w-full" /></div>;
  if (overview.isError || !overview.data?.data) {
    const expired = counselingErrorCode(overview.error) === "counseling_context_not_found";
    return (
      <section role="alert" className="max-w-3xl border-y border-border py-7">
        <h1 className="font-heading text-2xl font-semibold text-ink">Counseling context</h1>
        <p className="mt-3 text-sm leading-6 text-muted">{expired ? "This temporary Counseling Context is no longer available." : counselingErrorMessage(overview.error, "Counseling Context is not currently available.")}</p>
        {expired ? <p className="mt-2 text-sm leading-6 text-muted">Context access is limited to the active Counseling relationship and its configured review window.</p> : <Button className="mt-3" variant="secondary" onClick={() => void overview.refetch()}>Retry</Button>}
        <Link href="/portal/counseling" className="mt-4 inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">My Counseling Encounters</Link>
      </section>
    );
  }

  return <CounselingWorkspaceContent anchorType={anchorType} anchorId={anchorId} overview={overview.data.data} access={access} onRefreshOverview={() => overview.refetch()} />;
}

function CounselingWorkspaceContent({
  anchorType,
  anchorId,
  overview,
  access,
  onRefreshOverview,
}: {
  anchorType: CounselingContextAnchorType;
  anchorId: string;
  overview: CounselingContextOverviewResponse;
  access: ReturnType<typeof getCounselingAccess>;
  onRefreshOverview: () => unknown;
}) {
  const queryClient = useQueryClient();
  const [recordOpen, setRecordOpen] = useState(false);
  const [recordUncertain, setRecordUncertain] = useState(false);
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
        }
      : undefined;

  async function handleCreated() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getCounselingContextGetOverviewQueryKey(anchorType, anchorId) }),
      ...(anchorType === CounselingContextAnchorType.ROUTINE_INTERVIEW
        ? [queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(anchorId) })]
        : []),
    ]);
    setRecordOpen(false);
    setContextPanelRevision((revision) => revision + 1);
    await onRefreshOverview();
  }

  async function handlePublished() {
    await queryClient.invalidateQueries({ queryKey: getCounselingContextListSharedSummariesQueryKey(anchorType, anchorId, { limit: 20 }) });
  }

  return (
    <div>
      <CounselingPageHeading title="Counseling workspace" description="Temporary Counseling context is available only around the active interaction and configured review window." action={<Link href="/portal/counseling" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">My Counseling Encounters</Link>} />
      {contextExpired ? (
        <section role="alert" className="border-y border-warning/40 py-5"><h2 className="font-heading text-xl font-semibold text-ink">Counseling context is no longer available</h2><p className="mt-2 text-sm leading-6 text-muted">This temporary Counseling Context is no longer available. Context access is limited to the active Counseling relationship and its configured review window.</p><p className="mt-2 text-sm text-muted">Your assigned Encounter remains available from My Counseling Encounters.</p></section>
      ) : (
        <div className="grid gap-8 xl:grid-cols-[minmax(15rem,0.8fr)_minmax(0,2fr)]">
          <section aria-labelledby="counseling-interaction-heading" className="min-w-0 border-y border-border py-5">
            <h2 id="counseling-interaction-heading" className="font-heading text-xl font-semibold text-ink">Interaction</h2>
            <dl className="mt-3 divide-y divide-border">
              <Metadata label="Origin">{counselingEntryModeLabel(overview.entry_mode)}</Metadata>
              <Metadata label="Delivery">{counselingDeliveryModeLabel(overview.delivery_mode)}</Metadata>
              <Metadata label="Context available until">{formatCounselingDateTime(overview.valid_until)}</Metadata>
              <Metadata label="Routine Interview">{overview.routine_interview ? `${simpleLabel(overview.routine_interview.intake_status)} Intake · ${simpleLabel(overview.routine_interview.evaluation_status)} Evaluation` : "No linked Routine Interview"}</Metadata>
              <Metadata label="Counseling Encounter">{overview.matching_encounter ? "Recorded" : "Not yet recorded"}</Metadata>
            </dl>
            {overview.matching_encounter ? (
              <div className="mt-4 border-t border-border pt-4"><p className="text-sm text-muted">Completed interaction recorded {formatCounselingDateTime(overview.matching_encounter.started_at)} – {formatCounselingDateTime(overview.matching_encounter.ended_at)}.</p><Link href={`/portal/counseling/encounters/${overview.matching_encounter.id}`} className="mt-3 inline-flex min-h-10 items-center rounded-md border border-border px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">View encounter</Link></div>
            ) : access.canManageAssigned ? (
              <div className="mt-4 border-t border-border pt-4"><p className="text-sm font-medium text-ink">Counseling Encounter not yet recorded</p><Button className="mt-3" disabled={recordUncertain} onClick={() => setRecordOpen((open) => !open)}>{recordUncertain ? "Recording result unconfirmed" : recordOpen ? "Close recording" : "Record completed encounter"}</Button>{recordOpen ? preset ? <div className="mt-4"><RecordEncounterForm preset={preset} onCancel={() => setRecordOpen(false)} onUncertain={() => setRecordUncertain(true)} onCreated={() => void handleCreated()} /></div> : <p role="alert" className="mt-3 text-sm text-danger">This context does not provide a supported direct origin and delivery mode for recording.</p> : null}</div>
            ) : null}
          </section>

          <CounselingContextPanel
            key={`${anchorType}-${anchorId}-${contextPanelRevision}`}
            anchorType={anchorType}
            anchorId={anchorId}
            overview={overview}
            access={access}
            onPublished={handlePublished}
            onContextExpiredChange={setContextExpired}
          />
        </div>
      )}
    </div>
  );
}

export function CounselingContextPanel({
  anchorType,
  anchorId,
  overview,
  access,
  onPublished,
  onContextExpiredChange,
}: {
  anchorType: CounselingContextAnchorType;
  anchorId: string;
  overview: CounselingContextOverviewResponse;
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
  const contextExpired = [inventory.error, support.error, history.error, previousSummaries.error].some((error) => counselingErrorCode(error) === "counseling_context_not_found");

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
      <h2 className="font-heading text-xl font-semibold text-ink">Student context</h2>
      {contextExpired ? (
        <div role="status" className="mt-4 border-y border-border py-5"><p className="text-sm text-muted">Counseling context is not currently available.</p></div>
      ) : (
        <>
          <div role="tablist" aria-label="Counseling context sections" onKeyDown={handleTabKeyDown} className="mt-4 flex max-w-full gap-1 overflow-x-auto border-b border-border">
            {tabs.map((tab) => <button key={tab.id} id={`counseling-context-tab-${tab.id}`} type="button" role="tab" aria-selected={activeTab === tab.id} aria-controls="counseling-context-panel" tabIndex={activeTab === tab.id ? 0 : -1} onClick={() => setActiveTab(tab.id)} className={`min-h-10 shrink-0 border-b-2 px-3 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${activeTab === tab.id ? "border-brand text-brand" : "border-transparent text-muted hover:text-ink"}`}>{tab.label}</button>)}
          </div>
          <div id="counseling-context-panel" role="tabpanel" aria-labelledby={`counseling-context-tab-${activeTab}`} tabIndex={0} className="min-w-0 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
            {activeTab === "OVERVIEW" ? <ContextOverview overview={overview} /> : null}
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

function ContextOverview({ overview }: { overview: CounselingContextOverviewResponse }) {
  return (
    <div>
      <dl className="grid gap-x-8 sm:grid-cols-2">
        <Metadata label="Student">{overview.student.display_name}</Metadata>
        <Metadata label="Institutional ID">{overview.student.institutional_id ?? "Not provided"}</Metadata>
        <Metadata label="Campus">{overview.student.campus?.name ?? "Not provided"}</Metadata>
        <Metadata label="College">{overview.student.college?.name ?? "Not provided"}</Metadata>
        <Metadata label="Program">{overview.student.program?.name ?? "Not provided"}</Metadata>
        <Metadata label="Year level">{overview.student.year_level ?? "Not provided"}</Metadata>
        <Metadata label="Counseling origin">{counselingEntryModeLabel(overview.entry_mode)}</Metadata>
        <Metadata label="Delivery mode">{counselingDeliveryModeLabel(overview.delivery_mode)}</Metadata>
        <Metadata label="Available until">{formatCounselingDateTime(overview.valid_until)}</Metadata>
        <Metadata label="Routine Interview">{overview.routine_interview ? `${simpleLabel(overview.routine_interview.intake_status)} Intake · ${simpleLabel(overview.routine_interview.evaluation_status)} Evaluation` : "No Routine Interview is linked to this Counseling context."}</Metadata>
        <Metadata label="Matching Encounter">{overview.matching_encounter ? "Counseling Encounter recorded" : "Counseling Encounter not yet recorded"}</Metadata>
      </dl>
    </div>
  );
}

function RoutineContext({ routine, canManage }: { routine: QueryResultWithData<CounselorRoutineDetailResponse>; canManage: boolean }) {
  if (routine.isPending) return <div aria-busy="true" aria-label="Loading assigned Routine Interview"><Skeleton className="h-12 w-full" /><Skeleton className="mt-3 h-56 w-full" /></div>;
  if (routine.isError || !routine.data?.data) return <CounselingQueryError message={counselingErrorMessage(routine.error, "The Routine Interview could not be loaded within your current access.")} onRetry={() => void routine.refetch()} />;
  const detail = routine.data.data;
  return (
    <div>
      <div className="mb-5 border-y border-border py-4"><p className="text-sm font-semibold text-ink">Student Intake · {routineIntakeStatusLabel(detail.intake_status)}</p><p className="mt-1 text-sm text-muted">{detail.intake_status === "SUBMITTED" ? "Submitted responses are read-only for Counselors." : "Student-authored responses are protected until submission."}</p></div>
      {detail.intake_status === "SUBMITTED" && detail.intake ? <RoutineStudentIntakeReadOnly intake={detail.intake} /> : <p role="status" className="border-b border-border py-5 text-sm text-muted">Student Intake is still a draft. The Student’s answers become available after they submit their Intake.</p>}
      {detail.intake_status !== "SUBMITTED" ? <section className="mt-8 border-t border-border pt-5"><h3 className="font-heading text-lg font-semibold text-ink">Counselor Evaluation</h3><p className="mt-2 text-sm text-muted">Counselor Evaluation becomes available after the Student submits the Intake.</p></section> : detail.evaluation_status === "FINALIZED" ? <section className="mt-8 border-t border-border pt-5"><h3 className="font-heading text-lg font-semibold text-ink">Counselor Evaluation</h3><p className="mt-1 text-sm text-muted">Finalized {detail.evaluation_finalized_at ? formatCounselingDateTime(detail.evaluation_finalized_at) : ""} · Read-only</p><RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} /></section> : canManage ? <RoutineCounselorEvaluationWorkspace key={detail.id} routineInterviewId={detail.id} entryMode={detail.entry_mode} initialEvaluation={detail.evaluation} evaluationFinalized={false} /> : <section className="mt-8 border-t border-border pt-5"><h3 className="font-heading text-lg font-semibold text-ink">Counselor Evaluation</h3><p className="mt-1 text-sm text-muted">Draft evaluation · Read-only in your current access.</p><RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} /></section>}
    </div>
  );
}

function InventoryContext({ query, overview }: { query: QueryResultWithData<CounselingContextInventoryResponse>; overview: CounselingContextOverviewResponse }) {
  if (query.isPending) return <div aria-busy="true" aria-label="Loading contextual Individual Inventory"><Skeleton className="h-10 w-1/2" /><Skeleton className="mt-4 h-80 w-full" /></div>;
  if (query.isError) return <CounselingQueryError message={counselingErrorMessage(query.error, "Contextual Individual Inventory could not be loaded.")} onRetry={() => void query.refetch()} />;
  const result = query.data?.data;
  if (!result?.available) {
    const unavailable: Record<string, string> = {
      [CounselingContextInventoryStatus.MISSING]: "No current submitted Individual Inventory is available for this Counseling context.",
      [CounselingContextInventoryStatus.DRAFT]: "The current Individual Inventory is still a draft and is not available for Counselor review.",
      [CounselingContextInventoryStatus.SUBMITTED]: "A submitted Individual Inventory is not available for this Counseling context.",
    };
    return <p role="status" className="border-y border-border py-5 text-sm text-muted">{unavailable[result?.inventory_source_status ?? CounselingContextInventoryStatus.MISSING]}</p>;
  }
  if (!result.inventory || result.inventory.status !== "SUBMITTED") return <p role="status" className="border-y border-border py-5 text-sm text-muted">The current submitted Individual Inventory is not available for this Counseling context.</p>;
  return <InventoryReadOnly inventory={result.inventory} studentIdentity={{ display_name: overview.student.display_name, institutional_id: overview.student.institutional_id }} />;
}

function SupportContext({ query }: { query: QueryResultWithData<CounselingContextSupportResponse> }) {
  if (query.isPending) return <div aria-busy="true" aria-label="Loading contextual support indicators"><Skeleton className="h-12 w-full" /><Skeleton className="mt-3 h-12 w-full" /></div>;
  if (query.isError) return <CounselingQueryError message={counselingErrorMessage(query.error, "Contextual support indicators could not be loaded.")} onRetry={() => void query.refetch()} />;
  const result = query.data?.data;
  if (!result?.available) {
    const message = result?.inventory_source_status === CounselingContextInventoryStatus.DRAFT
      ? "Support indicators are unavailable because the current Individual Inventory is still a draft."
      : result?.inventory_source_status === CounselingContextInventoryStatus.SUBMITTED
        ? "Support indicators are unavailable for this Counseling context."
        : "Support indicators are unavailable because no current submitted Individual Inventory is available.";
    return <p role="status" className="border-y border-border py-5 text-sm text-muted">{message}</p>;
  }
  return result.indicators.length ? <ul className="divide-y divide-border border-y border-border">{result.indicators.map((indicator) => <li key={indicator.code} className="py-3 text-sm text-ink">{indicator.label}</li>)}</ul> : <p className="border-y border-border py-5 text-sm text-muted">No support indicators were returned for this Counseling context.</p>;
}

function HistoryContext({ query }: { query: QueryResultWithData<CounselingContextHistoryResponse> }) {
  if (query.isPending) return <div aria-busy="true" aria-label="Loading minimized Counseling history"><Skeleton className="h-14 w-full" /><Skeleton className="mt-2 h-14 w-full" /></div>;
  if (query.isError) return <CounselingQueryError message={counselingErrorMessage(query.error, "Counseling context history could not be loaded.")} onRetry={() => void query.refetch()} />;
  const items = query.data?.data.items ?? [];
  if (!items.length) return <p className="border-y border-border py-5 text-sm text-muted">No contextual history is available.</p>;
  const kinds: Record<string, string> = { APPOINTMENT: "Appointment", REFERRAL: "Referral", CALL_SLIP: "Call Slip", ROUTINE_INTERVIEW: "Routine Interview" };
  return <ol className="divide-y divide-border border-y border-border">{items.map((item) => <li key={`${item.kind}-${item.id}`} className="py-4"><p className="font-semibold text-ink">{kinds[item.kind] ?? simpleLabel(item.kind)} · {item.title}</p><p className="mt-1 text-sm text-muted">{formatCounselingDateTime(item.occurred_at)} · {simpleLabel(item.status)}{item.reference_code ? ` · ${item.reference_code}` : ""}{item.delivery_mode ? ` · ${counselingDeliveryModeLabel(item.delivery_mode)}` : ""}</p>{item.provider ? <p className="mt-1 text-sm text-muted">Provider: {item.provider.display_name}</p> : null}</li>)}</ol>;
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
  if (query.isPending && access.canViewAssignedSummaries) return <div aria-busy="true" aria-label="Loading published Shared Summaries"><Skeleton className="h-20 w-full" /><Skeleton className="mt-2 h-20 w-full" /></div>;
  if (query.isError && access.canViewAssignedSummaries) return <CounselingQueryError message={counselingErrorMessage(query.error, "Previously published Shared Summaries could not be loaded.")} onRetry={() => void query.refetch()} />;
  const items = query.data?.data.items ?? [];
  const encounterId = overview.matching_encounter?.id;
  return (
    <div className="space-y-8">
      <section aria-labelledby="previous-shared-summaries-heading">
        <h3 id="previous-shared-summaries-heading" className="font-heading text-lg font-semibold text-ink">Previous published summaries</h3>
        {!access.canViewAssignedSummaries ? <p className="mt-3 text-sm text-muted">Published Shared Summaries are not available in your current access.</p> : items.length ? <ul className="mt-3 divide-y divide-border border-y border-border">{items.map((item) => <li key={item.id} className="py-4"><p className="font-semibold text-ink">Counselor: {item.counselor.display_name}</p><p className="mt-1 text-sm text-muted">Counseling ended {formatCounselingDateTime(item.counseling_ended_at)} · Published {formatCounselingDateTime(item.published_at)}</p><p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{item.content}</p></li>)}</ul> : <p className="mt-3 border-y border-border py-5 text-sm text-muted">No previous published Shared Summaries are available.</p>}
      </section>
      {encounterId && access.canViewAssignedSummaries ? <section aria-labelledby="current-shared-summary-heading" className="border-t border-border pt-6"><h3 id="current-shared-summary-heading" className="sr-only">This encounter’s Shared Summary</h3><SharedSummarySection encounterId={encounterId} access={access} onPublished={onPublished} /></section> : null}
    </div>
  );
}
