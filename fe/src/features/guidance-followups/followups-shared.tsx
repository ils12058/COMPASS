"use client";

import Link from "next/link";
import type { Category, SourceReference } from "@/lib/api/generated/model";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { Button } from "@/components/ui/button";
import { PanelMessage } from "@/components/ui/panel";

export { followupAccess } from "./followups-access";
export const categoryLabel = (category: Category) => ({ ADMINISTRATIVE: "Administrative coordination", STUDENT_CONTACT: "Student contact", COUNSELING: "Counseling follow-up", REFERRAL_ACTION: "Referral coordination" }[category]);
export const statusLabel = (status: string) => ({ PENDING: "Pending", COMPLETED: "Completed", CANCELLED: "Cancelled" }[status] ?? status);
export function sourceDestination(source: SourceReference) {
  const root = { COUNSELING_ENCOUNTER: "/portal/counseling/encounters/", REFERRAL: "/portal/referrals/", ROUTINE_INTERVIEW: "/portal/routine-interviews/" }[source.kind];
  return root + encodeURIComponent(source.id);
}
export function followupError(error: unknown) {
  if (error instanceof CompassApiError) {
    const code = readApiErrorCode(error.body);
    if (code === "followups_not_enabled") return "Follow-Ups are not available yet.";
    if (code === "followup_content_unavailable") return "Protected follow-up content is temporarily unavailable. Your saved information is preserved.";
    if (error.status === 404 || error.status === 403) return "This follow-up is not available to your account.";
    if (error.status === 409) return "This follow-up changed. Review the latest saved details before trying again.";
    if (error.status === 422) return "Check the Student, assignment, date and required text, then try again.";
  }
  return "We could not confirm the request. Your input has been kept.";
}
export function FollowupFailure({ error, retry }: { error: unknown; retry?: () => void }) {
  return <PanelMessage title="Follow-Ups unavailable"><p role="alert">{followupError(error)}</p>{retry ? <Button variant="secondary" onClick={retry}>Retry</Button> : null}</PanelMessage>;
}
export function FollowupRestricted() {
  return <PanelMessage title="Follow-Ups unavailable">Your account does not have access to Guidance Follow-Ups. <Link href="/portal">Return to Overview</Link></PanelMessage>;
}
