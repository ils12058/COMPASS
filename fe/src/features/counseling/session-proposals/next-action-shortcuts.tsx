"use client";

import { CalendarPlus, MessageSquare, TicketCheck } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { caseCallSlipHref, messageThreadHref, proposeSessionHref } from "./session-proposal-presentation";

/** NS-1: ways to reach the Student from a pending next action. None completes the task. */
export function NextActionShortcuts({ label, studentId, threadId, callSlip, proposeCaseId, followUpId, returnTo }: {
  label: string;
  studentId: string;
  threadId: string | null;
  callSlip: { caseId: string | null } | null;
  proposeCaseId: string | null;
  followUpId: string;
  returnTo: string;
}) {
  if (!threadId && !callSlip && !proposeCaseId) return null;
  const link = buttonVariants({ variant: "quiet", className: "min-h-9 gap-1.5 px-2 text-sm" });
  return <div role="group" aria-label={`Reach the Student for ${label}`} className="mt-2 flex flex-wrap gap-x-2 gap-y-1">
    {threadId ? <Link className={link} href={messageThreadHref(threadId, returnTo)}><MessageSquare size={16} aria-hidden="true" />Message student</Link> : null}
    {callSlip ? <Link className={link} href={caseCallSlipHref({ studentId, caseId: callSlip.caseId, followUpId, returnTo })}><TicketCheck size={16} aria-hidden="true" />Issue Call Slip</Link> : null}
    {proposeCaseId ? <Link className={link} href={proposeSessionHref(proposeCaseId, returnTo, followUpId)}><CalendarPlus size={16} aria-hidden="true" />Propose session</Link> : null}
  </div>;
}
