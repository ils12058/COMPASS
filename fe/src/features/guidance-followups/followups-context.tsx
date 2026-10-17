"use client";
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
  const context = useGuidanceFollowupsGetContext({ source_kind: kind, source_id: id }, { query: { enabled: access.view, retry: false } });
  const query = useGuidanceFollowupsList({ source_kind: kind, source_id: id, page, page_size: 10 }, { query: { enabled: access.view && context.isSuccess, retry: false } });
  if (!access.view) return null;
  if (context.isError || context.isPending) return null;
  return <Panel className="mt-5"><PanelHeader title="Linked follow-ups" /><div className="space-y-3 p-5">
    {context.data.data.can_create ? <Link className="font-semibold text-brand underline" href={`/portal/follow-ups/new?source_kind=${kind}&source_id=${encodeURIComponent(id)}`}>Create follow-up</Link> : null}
    {query.isPending ? <p role="status">Loading linked follow-ups…</p> : query.isError ? <p role="alert">Linked follow-ups could not be loaded. <Button variant="secondary" onClick={() => void query.refetch()}>Retry</Button></p> : query.data?.data.items.length ? <ul className="divide-y divide-border">{query.data.data.items.map(row => <li className="py-2" key={row.id}><Link className="font-semibold text-brand underline" href={`/portal/follow-ups/${row.id}`}>{statusLabel(row.status)} · {formatInstitutionalDateTime(row.due_at)}</Link></li>)}</ul> : <p>No linked follow-ups are available to your account.</p>}
    {query.data ? <CanonicalPagination page={query.data.data.page} hasNext={query.data.data.has_next} onPageChange={setPage} /> : null}
  </div></Panel>;
}
