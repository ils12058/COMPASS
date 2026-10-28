"use client";
import Link from "next/link";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { Button } from "@/components/ui/button";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { CoverageHeading, CoverageError, statusLabels, referenceClass } from "./coverage-shared";
import { CoverageRequest } from "./coverage-request";
import * as api from "@/lib/api/generated/counseling/counseling";
import { formatCounselingDateTime } from "@/features/counseling/counseling-shared";
export function CoveragePage() {
    const { user } = usePortalSession();
    const params = useSearchParams();
    const [page, setPage] = useState(1);
    const [requestOpen, setRequestOpen] = useState(Boolean(params.get("student")));
    const allowed = user.role === "COUNSELOR" && user.capabilities.includes("counseling.continuity.view");
    const config = api.useCounselingCoverageGetConfiguration({ query: { enabled: allowed, retry: false, refetchOnWindowFocus: "always", gcTime: 0, queryKey: [...api.getCounselingCoverageGetConfigurationQueryKey(), user.id] } });
    const list = api.useCounselingContinuityListGrants({ page, page_size: 20 }, { query: { enabled: allowed && config.isSuccess, retry: false, refetchInterval: 15000, refetchOnWindowFocus: "always", queryKey: [...api.getCounselingContinuityListGrantsQueryKey({ page, page_size: 20 }), user.id], gcTime: 0 } });
    const groups = [
        { title: "My case coverage", items: list.data?.data.items.filter(g => g.receiving_counselor_id === user.id) ?? [] },
        { title: "Coverage requests", items: list.data?.data.items.filter(g => (g.requested_by_id === user.id || g.original_counselor_id === user.id)) ?? [] },
        ...(config.data?.data.can_approve ? [{ title: "Pending approvals", items: list.data?.data.items.filter(g => g.decision === "REQUESTED" && g.requested_by_id !== user.id && g.receiving_counselor_id !== user.id) ?? [] }, { title: "Coverage history", items: list.data?.data.items.filter(g => g.decision !== "REQUESTED" && g.requested_by_id !== user.id && g.receiving_counselor_id !== user.id) ?? [] }] : []),
    ];
    return <article><CoverageHeading />{!allowed ? <CoverageError error={null}/> : config.isPending ? <p role="status">Loading case coverage…</p> : config.isError ? <CoverageError error={config.error} retry={() => void config.refetch()}/> : <>
    {config.data.data.can_request ? <div className="mb-5"><Button variant={requestOpen ? "secondary" : "primary"} onClick={() => setRequestOpen(!requestOpen)}>{requestOpen ? "Close request" : "Request coverage"}</Button></div> : null}
    {requestOpen && config.data.data.can_request ? <CoverageRequest key={user.id} configuration={config.data.data} initialStudent={params.get("student") ?? ""} initialOriginal={params.get("original") ?? user.id} onCreated={() => { setRequestOpen(false); void list.refetch(); }}/> : null}
    {list.isPending ? <p role="status">Loading coverage requests…</p> : list.isError ? <CoverageError error={list.error} retry={() => void list.refetch()}/> : <>{groups.map(group => <Panel key={group.title} className="mb-5"><PanelHeader title={group.title}/>{group.items.length ? <ul className="divide-y divide-line">{group.items.map(g => <li key={g.id} className="flex flex-wrap items-center justify-between gap-3 p-4"><div className="min-w-0"><p className="font-semibold">{statusLabels[g.effective_status]}</p><p className={referenceClass}>Student {g.student_id}</p><p className="text-sm text-muted">{formatCounselingDateTime(g.starts_at)} – {formatCounselingDateTime(g.expires_at)}</p></div><Link className="font-semibold text-brand underline" href={`/portal/counseling/coverage/${g.id}`}>Review coverage<span className="sr-only"> for Student {g.student_id}</span></Link></li>)}</ul> : <PanelMessage>No coverage in this section on this page.</PanelMessage>}</Panel>)}<div className="flex items-center gap-3"><Button variant="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {page}</span><Button variant="secondary" disabled={!list.data?.data.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></>}
  </>}</article>;
}
