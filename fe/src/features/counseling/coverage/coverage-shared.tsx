"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { ContextHelp } from "@/components/ui/context-help";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { CounselingPageHeading, counselingErrorCode, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import type { ContinuityStatus, ContinuityReason, ContinuityGrantMetadata } from "@/lib/api/generated/model";
export const statusLabels: Record<ContinuityStatus, string> = { PENDING: "Pending approval", SCHEDULED: "Scheduled", ACTIVE: "Active", EXPIRED: "Expired", DECLINED: "Declined", CANCELLED: "Cancelled", REVOKED: "Revoked", UNAVAILABLE: "Unavailable" };
export const reasonLabels: Record<ContinuityReason, string> = { PLANNED_ABSENCE: "Planned absence", UNEXPECTED_ABSENCE: "Unexpected absence", TEMPORARY_SUPPORT: "Temporary support" };
export const referenceClass = "break-all font-mono text-xs text-muted";
export function CoverageHeading({ title = "Case coverage" }: {
    title?: string;
}) {
    return <CounselingPageHeading title={title} back={<Link href="/portal/counseling" className={pageBackLinkClass}>Back to Counseling</Link>} action={<ContextHelp title="Case coverage" sections={[
                { heading: "Temporary access", content: <p>Coverage requires independent approval. Each selected record is checked again when opened. Original authorship and Appointment responsibilities stay with their existing workflows.</p> },
                { heading: "Counselor handoff", content: <p>A confidential handoff is optional. Drafts belong to the original Counselor; submitted handoffs are read-only. They are separate from Student Session Summaries.</p> },
                { heading: "Confidentiality", content: <p>Protected content is cleared when access cannot be confirmed. Already viewed information cannot be recalled. Contact your guidance office when approved coverage or an independent approver is unavailable.</p> },
            ]}/>}/>;
}
export function CoverageError({ error, retry }: {
    error: unknown;
    retry?: () => void;
}) {
    const code = counselingErrorCode(error) ?? "";
    const policy = code.includes("policy");
    const conflict = code.includes("version") || code.includes("changed") || code.includes("busy");
    return <Notice role="alert" title={policy ? "Case coverage is unavailable" : conflict ? "Coverage needs review" : "Access could not be confirmed"} action={retry ? <Button variant="secondary" onClick={retry}>Check again</Button> : undefined}>
    {policy ? "An approved institutional procedure is required before this workflow can be used." : conflict ? "The request, record or access conditions changed. Review the latest information before trying again." : code.includes("handoff_unavailable") ? "The encrypted handoff is unavailable. Contact the guidance office." : "Protected content has been cleared. Your guidance office can help with coverage access."}
  </Notice>;
}
export function CoverageFacts({ grant }: {
    grant: ContinuityGrantMetadata;
}) {
    const facts = [["Student reference", grant.student_id], ["Original Counselor", grant.original_counselor_id ?? "Not recorded"], ["Receiving Counselor", grant.receiving_counselor_id], ["Requester", grant.requested_by_id], ["Approver", grant.decision_by_id ?? "Pending"], ["Purpose", reasonLabels[grant.reason_category]], ["Starts", formatCounselingDateTime(grant.starts_at)], ["Expires", formatCounselingDateTime(grant.expires_at)], ["Status", statusLabels[grant.effective_status]], ["Policy reference", grant.policy_evidence]];
    return <dl className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">{facts.map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm">{value}</dd></div>)}</dl>;
}
