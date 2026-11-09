"use client";

import Link from "next/link";
import type { Category, FollowUpDetail, SourceReference } from "@/lib/api/generated/model";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";
import { PanelMessage } from "@/components/ui/panel";

export { followupAccess } from "./followups-access";
export const categoryLabel = (category: Category) => ({ ADMINISTRATIVE: "Administrative coordination", STUDENT_CONTACT: "Student contact", COUNSELING: "Counseling Follow-Up", REFERRAL_ACTION: "Referral coordination" }[category]);
export const statusLabel = (status: string) => ({ PENDING: "Pending", COMPLETED: "Completed", CANCELLED: "Cancelled" }[status] ?? status);
export function sourceDestination(source: SourceReference) {
  const root = { COUNSELING_ENCOUNTER: "/portal/counseling/encounters/", REFERRAL: "/portal/referrals/", ROUTINE_INTERVIEW: "/portal/routine-interviews/" }[source.kind];
  return root + encodeURIComponent(source.id);
}
export function nextFollowupHref(item: Pick<FollowUpDetail, "source" | "student_id" | "student_name">) {
  const reference = item.source
    ? `source_kind=${encodeURIComponent(item.source.kind)}&source_id=${encodeURIComponent(item.source.id)}`
    : `student_id=${encodeURIComponent(item.student_id)}&student_name=${encodeURIComponent(item.student_name)}`;
  return `/portal/follow-ups/new?${reference}`;
}
export function followupError(error: unknown) {
  if (error instanceof CompassApiError) {
    const code = readApiErrorCode(error.body);
    if (code === "followup_content_unavailable") return "Couldn't show confidential Follow-Up details right now. Your saved information is kept.";
    if (error.status === 404 || error.status === 403) return "This Follow-Up is not available to your account.";
    if (error.status === 409) return "This Follow-Up changed. Review the latest saved details before trying again.";
    if (error.status === 422) return "Check the Student, assignment, date and required text, then try again.";
  }
  return "Couldn't confirm the request. Your input is kept.";
}
export function FollowupFailure({ error, retry }: { error: unknown; retry?: () => void }) {
  return <PanelMessage title="Follow-Ups"><p role="alert">{followupError(error)}</p>{retry ? <Button variant="secondary" onClick={retry}>Retry</Button> : null}</PanelMessage>;
}
export function FollowupRestricted() {
  return <PanelMessage title="Follow-Ups">You don&apos;t have access to Guidance Follow-Ups. <Link href="/portal">Return to Overview</Link></PanelMessage>;
}
