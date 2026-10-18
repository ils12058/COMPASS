"use client";
import { useFollowupsFreshness, followupQueryFreshness } from "./followups-data";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useGuidanceFollowupsGetContext, useGuidanceFollowupsList } from "@/lib/api/generated/guidance-followups/guidance-followups";
import type { SourceKind } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import { followupAccess, statusLabel } from "./followups-shared";
export function FollowupsContext({ kind, id }: { kind: SourceKind; id: string }) {
  const { user } = usePortalSession();
  const [page, setPage] = useState(1);
  const access = followupAccess(user);
  useFollowupsFreshness(access.view);
  const context = useGuidanceFollowupsGetContext({ source_kind: kind, source_id: id }, { query: { ...followupQueryFreshness, enabled: access.view, retry: false } });
  const query = useGuidanceFollowupsList({ source_kind: kind, source_id: id, page, page_size: 10 }, { query: { ...followupQueryFreshness, enabled: access.view && context.isSuccess, retry: false } });
  if (!access.view) return null;
  if (context.isError || context.isPending) return null;
  const counseling = kind === "COUNSELING_ENCOUNTER" || kind === "ROUTINE_INTERVIEW";
  const sourceLabel = kind === "COUNSELING_ENCOUNTER" ? "this Counseling Encounter" : kind === "ROUTINE_INTERVIEW" ? "this Routine Interview" : "this Referral";
  const actionLabel = kind === "REFERRAL" ? "Create referral follow-up" : "Create counseling follow-up";
  return <Panel className="mt-5"><PanelHeader title="Linked follow-ups" description={kind === "REFERRAL" ? "Track referral coordination as a separate next action." : "Track the next action after this counseling session."} /><div className="space-y-3 p-5">
    {counseling ? <p className="text-sm text-muted">Counseling follow-ups stay Counselor-confidential and require access to {sourceLabel}.</p> : <p className="text-sm text-muted">Referral follow-ups remain operational and use the Student’s current staff responsibility scope.</p>}
    {context.data.data.can_create ? <Link className="font-semibold text-brand underline underline-offset-4" href={`/portal/follow-ups/new?source_kind=${kind}&source_id=${encodeURIComponent(id)}`}>{actionLabel}</Link> : null}
    {query.isPending ? <p role="status">Loading linked follow-ups…</p> : query.isError ? <p role="alert">Linked follow-ups could not be loaded. <Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button></p> : query.data?.data.items.length ? <ul className="divide-y divide-border">{query.data.data.items.map(row => <li className="py-2" key={row.id}><Link className="font-semibold text-brand underline" href={`/portal/follow-ups/${row.id}`}>{statusLabel(row.status)} · {formatInstitutionalDateTime(row.due_at)}</Link></li>)}</ul> : <p>{context.data.data.can_create ? "No follow-ups are linked to this record yet." : "No linked follow-ups are available to your account."}</p>}
    {query.data ? <CanonicalPagination page={query.data.data.page} hasNext={query.data.data.has_next} onPageChange={setPage} /> : null}
  </div></Panel>;
}
