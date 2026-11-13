"use client";
import { useFollowupsFreshness, followupQueryFreshness } from "./followups-data";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useGuidanceFollowupsGetContext, useGuidanceFollowupsList } from "@/lib/api/generated/guidance-followups/guidance-followups";
import type { SourceKind } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { followupAccess, statusLabel } from "./followups-shared";
import { followupActionLabel } from "./followups-presentation";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
export function FollowupsContext({ kind, id }: { kind: SourceKind; id: string }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const params = useSearchParams();
  const here = `${pathname}${params.size ? `?${params}` : ""}`;
  const [page, setPage] = useState(1);
  const access = followupAccess(user);
  useFollowupsFreshness(access.view);
  const context = useGuidanceFollowupsGetContext({ source_kind: kind, source_id: id }, { query: { ...followupQueryFreshness, enabled: access.view, retry: false } });
  const query = useGuidanceFollowupsList({ source_kind: kind, source_id: id, page, page_size: 10 }, { query: { ...followupQueryFreshness, enabled: access.view && context.isSuccess, retry: false } });
  if (!access.view) return null;
  if (context.isPending) return null;
  if (context.isError) return <Panel className="mt-5"><PanelMessage role="status">Couldn&apos;t load linked Follow-Ups for this record. Try again.</PanelMessage></Panel>;
  const counseling = kind === "COUNSELING_ENCOUNTER" || kind === "ROUTINE_INTERVIEW";
  const sourceLabel = kind === "COUNSELING_ENCOUNTER" ? "this Counseling Encounter" : kind === "ROUTINE_INTERVIEW" ? "this Routine Interview" : "this Referral";
  const actionLabel = kind === "REFERRAL" ? "Create Referral Follow-Up" : "Create counseling Follow-Up";
  return <Panel className="mt-5"><PanelHeader title="Linked Follow-Ups" description={kind === "REFERRAL" ? "Track Referral coordination as a separate next action." : "Track the next action after this counseling session."} /><div className="space-y-3 p-5">
    {counseling ? <p className="text-sm text-muted">Counseling Follow-Ups stay Counselor-confidential and require access to {sourceLabel}.</p> : <p className="text-sm text-muted">Referral Follow-Ups go to the staff who currently handle this Student.</p>}
    {context.data.data.can_create ? <Link className="font-semibold text-brand underline underline-offset-4" href={withWorkflowReturn(`/portal/follow-ups/new?source_kind=${kind}&source_id=${encodeURIComponent(id)}`, here)}>{actionLabel}</Link> : null}
    {query.isPending ? <p role="status">Loading linked Follow-Ups…</p> : query.isError ? <p role="alert">Couldn&apos;t load linked Follow-Ups. Try again. <Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button></p> : query.data?.data.items.length ? <ul className="divide-y divide-border">{query.data.data.items.map(row => <li className="py-2" key={row.id}><Link className="font-semibold text-brand underline" href={withWorkflowReturn(`/portal/follow-ups/${row.id}`, here)}>{followupActionLabel(row)}</Link><p className="mt-1 text-sm">Due {formatInstitutionalDateTime(row.due_at)} · {statusLabel(row.status)}</p></li>)}</ul> : <p>{context.data.data.can_create ? "No Follow-Ups are linked to this record yet." : "No linked Follow-Ups are available to your account."}</p>}
    {query.data ? <CanonicalPagination page={query.data.data.page} hasNext={query.data.data.has_next} onPageChange={setPage} /> : null}
  </div></Panel>;
}
