"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Notice } from "@/components/ui/notice";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useServerBoundary, boundaryDelay } from "@/features/freshness/use-server-boundary";
import * as api from "@/lib/api/generated/counseling/counseling";
import { CoverageHeading, CoverageFacts, CoverageError, referenceClass, reasonLabels } from "./coverage-shared";
import { useCoveragePrivacy, broadcastCoverageChange } from "./use-coverage-privacy";
import { ProtectedRecord, HandoffWorkspace } from "./protected-record";
import type { ContinuityGrantMetadata } from "@/lib/api/generated/model";
export function CoverageDetail({ grantId }: {
    grantId: string;
}) { const { user, session } = usePortalSession(); return <CoverageDetailForAccount key={`${user.id}:${session.id}:${user.role}:${[...user.capabilities].sort().join(",")}:${grantId}`} grantId={grantId}/>; }
function CoverageDetailForAccount({ grantId }: {
    grantId: string;
}) {
    const { user } = usePortalSession();
    const privacy = useCoveragePrivacy(user.id, grantId);
    const allowed = user.role === "COUNSELOR" && user.capabilities.includes("counseling.continuity.view");
    const grantQuery = api.useCounselingContinuityGetGrant(grantId, { query: { enabled: allowed, retry: false, gcTime: 0, refetchInterval: 15000, refetchOnWindowFocus: "always", refetchOnReconnect: "always", queryKey: [...api.getCounselingContinuityGetGrantQueryKey(grantId), user.id] } });
    const config = api.useCounselingCoverageGetConfiguration({ query: { enabled: allowed, retry: false, gcTime: 0, queryKey: [...api.getCounselingCoverageGetConfigurationQueryKey(), user.id] } });
    const grant = grantQuery.data?.data;
    const [selected, setSelected] = useState<string | null>(null);
    const validUntil = grant && config.data ? new Date(Math.min(Date.parse(grant.expires_at), Date.parse(config.data.data.valid_until))).toISOString() : grant?.expires_at;
    useServerBoundary({ boundary: validUntil, serverDate: grantQuery.data?.headers.date, receivedAt: grantQuery.dataUpdatedAt, onBoundary: privacy.clear });
    const remaining = grant ? boundaryDelay(validUntil, grantQuery.data?.headers.date, grantQuery.dataUpdatedAt) : null;
    const confirmed = Boolean(grant && !grantQuery.isError && config.isSuccess && !privacy.blocked && (remaining ?? 0) > 0 && ["ACTIVE", "SCHEDULED", "PENDING"].includes(grant.effective_status));
    async function recheck() { privacy.clear(); const [g, c] = await Promise.all([grantQuery.refetch(), config.refetch()]); if (g.isSuccess && c.isSuccess)
        privacy.resume(); setSelected(null); }
    return <article><CoverageHeading title="Coverage details"/>{!allowed ? <CoverageError error={null}/> : grantQuery.isPending ? <p role="status">Loading coverage…</p> : grantQuery.isError || !grant ? <CoverageError error={grantQuery.error} retry={() => void recheck()}/> : <>
  <Panel><PanelHeader title="Case coverage"/><CoverageFacts grant={grant}/></Panel>
  <CoverageDecisions grant={grant} canApprove={Boolean(config.data?.data.can_approve) && !config.isError && !grantQuery.isFetching} onChanged={() => { privacy.clear(); broadcastCoverageChange(grant.id); void recheck(); }}/>
  {!confirmed ? <div className="mt-5">{config.isError ? <CoverageError error={config.error} retry={() => void recheck()}/> : <Notice title="Protected content is closed" action={<Button variant="secondary" onClick={() => void recheck()}>Check access again</Button>}>Coverage may be inactive, expired or unconfirmed. Protected content has been cleared.</Notice>}</div> : null}
  <Panel className="mt-5"><PanelHeader title="Selected records" description="Read-only records retain their original Counselor."/><ul className="divide-y divide-line">{grant.scopes.map(s => <li className="flex flex-wrap items-center justify-between gap-3 p-4" key={s.id}><div className="min-w-0"><p>{s.resource_kind === "ENCOUNTER" ? "Encounter metadata" : "Finalized Counselor Evaluation"}</p><p className={referenceClass}>{s.source_id}</p></div>{confirmed && grant.effective_status === "ACTIVE" && grant.receiving_counselor_id === user.id && user.capabilities.includes("counseling.continuity.read_selected") ? <Button variant="secondary" onClick={() => setSelected(selected === s.id ? null : s.id)}>{selected === s.id ? "Close record" : "Review record"}<span className="sr-only"> {s.source_id}</span></Button> : null}</li>)}</ul></Panel>
  {confirmed && selected && grant.effective_status === "ACTIVE" && grant.receiving_counselor_id === user.id ? grant.scopes.filter(s => s.id === selected).map(scope => <ProtectedRecord key={`${user.id}:${grant.id}:${grant.version}:${privacy.generation}:${scope.id}`} grant={grant} scope={scope} privacy={privacy}/>) : null}
  {confirmed ? <HandoffWorkspace key={`${user.id}:${grant.id}:${grant.version}:${privacy.generation}`} grant={grant} privacy={privacy}/> : null}
 </>}</article>;
}
function CoverageDecisions({ grant, canApprove, onChanged }: {
    grant: ContinuityGrantMetadata;
    canApprove: boolean;
    onChanged: () => void;
}) {
    const { user } = usePortalSession();
    const [action, setAction] = useState<"approve" | "decline" | "cancel" | "revoke" | null>(null);
    const [reviewedVersion, setReviewedVersion] = useState<number | null>(null);
    function choose(next: "approve" | "decline" | "cancel" | "revoke") {
        setReviewedVersion(grant.version);
        setAction(next);
    }
    const mutate = useMutation({ retry: false, gcTime: 0, mutationFn: async () => {
            if (reviewedVersion === null || reviewedVersion !== grant.version) throw new Error("Coverage changed before confirmation.");
            const data = { expected_version: reviewedVersion };
            if (action === "approve")
                return api.counselingContinuityApproveGrant(grant.id, data);
            if (action === "decline")
                return api.counselingContinuityDeclineGrant(grant.id, data);
            if (action === "cancel")
                return api.counselingContinuityCancelGrant(grant.id, data);
            return api.counselingContinuityRevokeGrant(grant.id, { ...data, reason_code: "COVERAGE_ENDED" });
        }, onSuccess: () => { setAction(null); onChanged(); }, onError: () => { setAction(null); onChanged(); } });
    const independent = canApprove && grant.requested_by_id !== user.id && grant.receiving_counselor_id !== user.id;
    const labels = { approve: "Approve coverage", decline: "Decline request", cancel: "Cancel request", revoke: "Revoke coverage" };
    return <div className="my-5 flex flex-wrap gap-3">
 {grant.decision === "REQUESTED" && independent ? <><Button onClick={() => choose("approve")}>Approve coverage</Button><Button variant="secondary" onClick={() => choose("decline")}>Decline request</Button></> : null}
 {grant.decision === "REQUESTED" && grant.requested_by_id === user.id ? <Button variant="secondary" onClick={() => choose("cancel")}>Cancel request</Button> : null}
 {grant.decision === "APPROVED" && independent && user.capabilities.includes("counseling.continuity.revoke") ? <Button variant="danger" onClick={() => choose("revoke")}>Revoke coverage</Button> : null}
 {action !== null && reviewedVersion !== grant.version ? <Notice role="status" title="Coverage changed">Review the latest details before choosing an action again.</Notice> : null}
 {mutate.error ? <CoverageError error={mutate.error}/> : null}
 <ConsequentialActionDialog open={action !== null && reviewedVersion === grant.version} onOpenChange={open => { if (!open)
        setAction(null); }} title={action ? `${labels[action]}?` : "Review coverage"} confirmLabel={action ? labels[action] : "Confirm"} pendingLabel="Saving…" pending={mutate.isPending} error={null} onConfirm={() => mutate.mutate()} variant={action === "revoke" ? "danger" : "primary"}><span className="block break-all">Receiving Counselor: {grant.receiving_counselor_id}.</span><span className="block break-all">Student: {grant.student_id}. Purpose: {reasonLabels[grant.reason_category]}.</span><span className="block">{grant.scopes.length} selected records. Expires {new Date(grant.expires_at).toLocaleString("en-PH", { timeZone: "Asia/Manila" })} Philippine time.</span><ul className="mt-3 space-y-2">{grant.scopes.map(scope => <li key={scope.id} className="break-all text-xs">{scope.resource_kind === "ENCOUNTER" ? "Encounter metadata" : "Finalized Evaluation"}: {scope.source_id}</li>)}</ul>{action === "revoke" ? <span className="block">New coverage reads will stop. Already viewed information cannot be recalled.</span> : null}</ConsequentialActionDialog>
 </div>;
}
