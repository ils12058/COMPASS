"use client";
import { useState } from "react";
import { useMutation, useQuery, type QueryKey } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { requestSessionRevalidation } from "@/lib/auth/session-revalidation";
import { isSessionEndedError, isAuthorityError } from "@/features/freshness/query-freshness";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import type { ContinuityGrantMetadata, ContinuityScopeMetadata, HandoffMetadata, HandoffBody } from "@/lib/api/generated/model";
import * as api from "@/lib/api/generated/counseling/counseling";
import { counselingDeliveryModeLabel, counselingEntryModeLabel, formatCounselingDateTime, counselingErrorCode } from "@/features/counseling/counseling-shared";
import { presentApprovedEvaluation } from "./coverage-safety";
import { CoverageError } from "./coverage-shared";
import type { useCoveragePrivacy } from "./use-coverage-privacy";
type Privacy = ReturnType<typeof useCoveragePrivacy>;
function useProtectedQuery<T>(privacy: Privacy, grant: ContinuityGrantMetadata, key: QueryKey, load: (signal: AbortSignal) => Promise<T>) {
    return useQuery({ queryKey: [...privacy.prefix, grant.version, privacy.generation, ...key], gcTime: 0, staleTime: 0, retry: false, refetchInterval: 15000, refetchOnWindowFocus: "always", refetchOnReconnect: "always", networkMode: "always", queryFn: async ({ signal }) => {
            const captured = privacy.barrier.current();
            try {
                if (!navigator.onLine || document.visibilityState !== "visible" || privacy.blocked)
                    throw new Error("Coverage access needs to be checked again.");
                const value = await load(signal);
                privacy.barrier.assertCurrent(captured, signal);
                if (!navigator.onLine || document.visibilityState !== "visible")
                    throw new Error("Coverage access needs to be checked again.");
                return value;
            }
            catch (error) {
                if (!signal.aborted && captured === privacy.barrier.current()) {
                    // Removing the failed query also cancels its global error callback.
                    // Request the existing portal session check before clearing it.
                    if (isSessionEndedError(error)) requestSessionRevalidation("session");
                    else if (isAuthorityError(error)) requestSessionRevalidation("authority");
                    privacy.clear();
                }
                throw error;
            }
        } });
}
export function ProtectedRecord({ grant, scope, privacy }: {
    grant: ContinuityGrantMetadata;
    scope: ContinuityScopeMetadata;
    privacy: Privacy;
}) {
    return scope.resource_kind === "ENCOUNTER" ? <EncounterRecord grant={grant} scope={scope} privacy={privacy}/> : <EvaluationRecord grant={grant} scope={scope} privacy={privacy}/>;
}
function EncounterRecord({ grant, scope, privacy }: {
    grant: ContinuityGrantMetadata;
    scope: ContinuityScopeMetadata;
    privacy: Privacy;
}) {
    const params = { expected_version: grant.version };
    const q = useProtectedQuery(privacy, grant, api.getCounselingContinuityGetSelectedEncounterMetadataQueryKey(grant.id, scope.source_id, params), signal => api.counselingContinuityGetSelectedEncounterMetadata(grant.id, scope.source_id, params, { signal }));
    if (q.isError)
        return <CoverageError error={q.error}/>;
    if (!q.data)
        return <p role="status">Checking selected Encounter…</p>;
    const e = q.data.data.encounter;
    return <Panel className="mt-5"><PanelHeader title="Selected Encounter metadata"/><dl className="grid gap-4 p-4 sm:grid-cols-2">{[["Encounter reference", e.id], ["Started", formatCounselingDateTime(e.started_at)], ["Ended", formatCounselingDateTime(e.ended_at)], ["Entry mode", counselingEntryModeLabel(e.entry_mode)], ["Delivery mode", counselingDeliveryModeLabel(e.delivery_mode)], ["Original Counselor", e.counselor_id]].map(([label, value]) => <div className="min-w-0" key={label}><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm">{value}</dd></div>)}</dl></Panel>;
}
function EvaluationRecord({ grant, scope, privacy }: {
    grant: ContinuityGrantMetadata;
    scope: ContinuityScopeMetadata;
    privacy: Privacy;
}) {
    const params = { expected_version: grant.version };
    const q = useProtectedQuery(privacy, grant, api.getCounselingContinuityGetSelectedRoutineEvaluationQueryKey(grant.id, scope.source_id, params), signal => api.counselingContinuityGetSelectedRoutineEvaluation(grant.id, scope.source_id, params, { signal }));
    if (q.isError)
        return <CoverageError error={q.error}/>;
    if (!q.data)
        return <p role="status">Checking selected Evaluation…</p>;
    return <Panel className="mt-5"><PanelHeader title="Selected Counselor Evaluation" description="Only the fields approved for this coverage are shown."/><dl className="space-y-5 p-4 sm:p-5">{presentApprovedEvaluation(q.data.data.evaluation).map(field => <div key={field.key}><dt className="text-sm font-semibold">{field.label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-sm">{field.value}</dd></div>)}</dl></Panel>;
}
export function HandoffWorkspace({ grant, privacy }: {
    grant: ContinuityGrantMetadata;
    privacy: Privacy;
}) {
    const { user } = usePortalSession();
    const [open, setOpen] = useState(false);
    const [dirty, setDirty] = useState(false);
    const [discard, setDiscard] = useState(false);
    const params = { expected_grant_version: grant.version };
    const meta = api.useCounselingHandoffGetMetadata(grant.id, params, { query: { retry: false, gcTime: 0, refetchInterval: 15000, queryKey: [...api.getCounselingHandoffGetMetadataQueryKey(grant.id, params), user.id, privacy.generation] } });
    const author = grant.original_counselor_id === user.id && user.capabilities.includes("counseling.handoff.manage_own");
    const receiver = grant.receiving_counselor_id === user.id && grant.effective_status === "ACTIVE" && user.capabilities.includes("counseling.handoff.read_received");
    const item = meta.data?.data.handoff;
    return <Panel className="mt-5"><PanelHeader title="Counselor handoff" description="Optional confidential communication, separate from Student Session Summaries."/>{meta.isPending ? <PanelMessage>Checking handoff status…</PanelMessage> : meta.isError ? <CoverageError error={meta.error}/> : <div className="space-y-4 p-4 sm:p-5"><p>{item?.state === "SUBMITTED" ? "Submitted · Read-only" : item ? "Draft · Author only" : "No handoff is available. Coverage does not require one."}</p>{author || receiver && item ? <Button variant="secondary" onClick={() => { if (open && dirty)
            setDiscard(true);
        else
            setOpen(!open); }}>{open ? "Close handoff" : author && !item ? "Prepare handoff" : "Open handoff"}</Button> : null}
 {open && (author || receiver) ? (item ? <ExistingHandoff key={item.id} grant={grant} privacy={privacy} item={item} author={author} onDirtyChange={setDirty} onSaved={() => { setDirty(false); setOpen(false); void meta.refetch(); }}/> : author ? <HandoffEditor grant={grant} privacy={privacy} onDirtyChange={setDirty} onSaved={() => { setDirty(false); setOpen(false); void meta.refetch(); }}/> : null) : null}
 <ConsequentialActionDialog open={discard} onOpenChange={setDiscard} title="Discard unsaved handoff changes?" confirmLabel="Discard changes" pendingLabel="Closing…" pending={false} variant="danger" error={null} onConfirm={() => { setDirty(false); setDiscard(false); setOpen(false); }}>Your unsaved text will be cleared. The last saved draft will remain.</ConsequentialActionDialog></div>}</Panel>;
}
function ExistingHandoff({ grant, privacy, item, author, onSaved, onDirtyChange }: {
    grant: ContinuityGrantMetadata;
    privacy: Privacy;
    item: HandoffMetadata;
    author: boolean;
    onSaved: () => void;
    onDirtyChange: (dirty: boolean) => void;
}) {
    const params = { expected_grant_version: grant.version };
    const key = author ? api.getCounselingHandoffGetAuthorDraftQueryKey(grant.id, params) : api.getCounselingHandoffReadSubmittedQueryKey(grant.id, params);
    const q = useProtectedQuery(privacy, grant, [item.id, ...key], signal => author ? api.counselingHandoffGetAuthorDraft(grant.id, params, { signal }) : api.counselingHandoffReadSubmitted(grant.id, params, { signal }));
    if (q.isError)
        return <CoverageError error={q.error}/>;
    if (!q.data)
        return <p role="status">Checking confidential handoff…</p>;
    return author && q.data.data.state === "DRAFT" ? <HandoffEditor grant={grant} privacy={privacy} existing={q.data.data} onSaved={onSaved} onDirtyChange={onDirtyChange} onConflict={() => void q.refetch()}/> : <p className="whitespace-pre-wrap break-words text-sm">{q.data.data.content}</p>;
}
function HandoffEditor({ grant, privacy, existing, onSaved, onDirtyChange, onConflict }: {
    grant: ContinuityGrantMetadata;
    privacy: Privacy;
    existing?: HandoffBody;
    onSaved: () => void;
    onDirtyChange: (dirty: boolean) => void;
    onConflict?: () => void;
}) {
    const [baseline, setBaseline] = useState(existing);
    const [reviewSaved, setReviewSaved] = useState(false);
    const [text, setText] = useState(existing?.content ?? "");
    const [confirmation, setConfirmation] = useState(false);
    const dirty = text !== (baseline?.content ?? "");
    const changed = Boolean(existing && baseline && existing.version !== baseline.version);
    const mutation = useMutation({ gcTime: 0, retry: false, mutationFn: (operation: "save" | "submit") => operation === "save" ? api.counselingHandoffSaveDraft(grant.id, { content: text, expected_grant_version: grant.version, expected_version: baseline?.version ?? 0 }) : api.counselingHandoffSubmit(grant.id, { expected_grant_version: grant.version, expected_version: baseline?.version ?? 0 }), onSuccess: () => { setConfirmation(false); onSaved(); }, onError: (error) => { setConfirmation(false); if(counselingErrorCode(error) === "continuity_stale_handoff_version" && onConflict) onConflict(); else privacy.clear(); } });
    useUnsavedChangesGuard({ dirty: dirty && !mutation.isSuccess, message: "Leave this unsaved confidential handoff?" });
    return <div className="space-y-4"><div><Label htmlFor="counselor-handoff-content">Confidential handoff</Label><Textarea id="counselor-handoff-content" rows={10} maxLength={12000} value={text} onChange={e => { setText(e.target.value); onDirtyChange(e.target.value !== (baseline?.content ?? "")); }} disabled={mutation.isPending}/></div><p role="status" className="text-sm text-muted">{dirty ? "Unsaved changes" : "Saved draft"}</p>{changed ? <p role="alert">The saved draft changed. Your unsaved text is retained. <Button variant="secondary" onClick={() => setReviewSaved(true)}>Review saved draft</Button></p> : null}{mutation.error ? <CoverageError error={mutation.error}/> : null}<div className="flex flex-wrap gap-3"><Button disabled={mutation.isPending || changed || Boolean(baseline) && !dirty} onClick={() => mutation.mutate("save")}>Save draft</Button><Button variant="secondary" disabled={mutation.isPending || changed || dirty || !baseline || !text.trim()} onClick={() => setConfirmation(true)}>Submit handoff</Button></div>
 <ConsequentialActionDialog open={reviewSaved} onOpenChange={setReviewSaved} title="Load the saved draft?" confirmLabel="Load saved draft" pendingLabel="Loading…" pending={false} error={null} onConfirm={() => { setBaseline(existing); setText(existing?.content ?? ""); onDirtyChange(false); mutation.reset(); setReviewSaved(false); }}>This replaces any unsaved text with the current saved draft. Review it before saving or submitting.</ConsequentialActionDialog><ConsequentialActionDialog open={confirmation} onOpenChange={setConfirmation} title="Submit confidential handoff?" confirmLabel="Submit handoff" pendingLabel="Submitting…" pending={mutation.isPending} error={null} onConfirm={() => mutation.mutate("submit")}><span className="block break-all">Receiving Counselor: {grant.receiving_counselor_id}.</span><span className="block">Submission locks this text. Coverage expires {formatCounselingDateTime(grant.expires_at)}. The receiver can read it only during effective coverage. It will not be published to the Student.</span></ConsequentialActionDialog></div>;
}
