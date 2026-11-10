"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { ContextHelp } from "@/components/ui/context-help";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { CounselingPageHeading, counselingErrorCode, formatCounselingDateTime } from "@/features/counseling/counseling-shared";
import type { ContinuityCommunicationPurpose, ContinuityStatus, ContinuityReason, ContinuityGrantMetadata } from "@/lib/api/generated/model";
export const statusLabels: Record<ContinuityStatus, string> = { PENDING: "Pending approval", SCHEDULED: "Scheduled", ACTIVE: "Active", EXPIRED: "Expired", DECLINED: "Declined", CANCELLED: "Cancelled", REVOKED: "Revoked", UNAVAILABLE: "Not available" };
export const reasonLabels: Record<ContinuityReason, string> = { PLANNED_ABSENCE: "Planned absence", UNEXPECTED_ABSENCE: "Unexpected absence", TEMPORARY_SUPPORT: "Temporary support" };
export const communicationPurposeLabels: Record<ContinuityCommunicationPurpose, string> = { CASE_COORDINATION: "Case coordination" };
export const referenceClass = "break-all font-mono text-xs text-muted";
// Names come from the coverage response; staff show a name, the Student also their ID.
export function personLabel(grant: ContinuityGrantMetadata, id: string | null | undefined, { withId = false, missing = "Not recorded" }: { withId?: boolean; missing?: string } = {}): string {
    if (!id) return missing;
    const person = grant.people?.find((item) => item.id === id);
    if (!person) return "Name not available";
    return withId && person.institutional_id ? `${person.name} (${person.institutional_id})` : person.name;
}
export function CoverageHeading({ title = "Case coverage", messagesTrigger }: {
    title?: string;
    messagesTrigger?: ReactNode;
}) {
    return <CounselingPageHeading title={title} back={<Link href="/portal/counseling" className={pageBackLinkClass}>Back to Counseling</Link>} action={<>{messagesTrigger}<ContextHelp title="Case coverage" sections={[
                { heading: "Temporary access", content: <p>A separate approver must approve coverage. Access is checked whenever a shared record is opened; its author and current Appointment responsibilities stay the same.</p> },
                { heading: "Counselor handoff", content: <p>A confidential handoff is optional. Drafts belong to the original Counselor; submitted handoffs are read-only. They are separate from Student Session Summaries.</p> },
                { heading: "Confidentiality", content: <p>Confidential information is hidden when access can&apos;t be confirmed; information already viewed can&apos;t be recalled. Contact the Guidance Office for help with coverage or approval.</p> },
            ]}/></>}/>;
}
export function CoverageError({ error, retry }: {
    error: unknown;
    retry?: () => void;
}) {
    const code = counselingErrorCode(error) ?? "";
    const conflict = code.includes("version") || code.includes("changed") || code.includes("busy");
    return <Notice role="alert" title={conflict ? "Coverage needs review" : "Couldn't confirm access"} action={retry ? <Button variant="secondary" onClick={retry}>Check again</Button> : undefined}>
    {conflict ? "The request, record or access conditions changed. Review the latest information before trying again." : code.includes("handoff_unavailable") ? "Couldn't open the confidential handoff. Contact the Guidance Office." : "Confidential information has been hidden. Contact the Guidance Office for help with coverage access."}
  </Notice>;
}
export function CoverageFacts({ grant }: {
    grant: ContinuityGrantMetadata;
}) {
    const facts = [["Student", personLabel(grant, grant.student_id, { withId: true })], ["Original Counselor", personLabel(grant, grant.original_counselor_id)], ["Receiving Counselor", personLabel(grant, grant.receiving_counselor_id)], ["Requester", personLabel(grant, grant.requested_by_id)], ["Approver", personLabel(grant, grant.decision_by_id, { missing: "Pending" })], ["Purpose", reasonLabels[grant.reason_category]], ...(grant.communication_purpose ? [["Communication purpose", communicationPurposeLabels[grant.communication_purpose]]] : []), ["Starts", formatCounselingDateTime(grant.starts_at)], ["Expires", formatCounselingDateTime(grant.expires_at)], ["Status", statusLabels[grant.effective_status]]];
    return <dl className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5">{facts.map(([label, value]) => <div key={label} className="min-w-0"><dt className="text-xs font-semibold text-muted">{label}</dt><dd className="mt-1 break-words text-sm">{value}</dd></div>)}</dl>;
}
