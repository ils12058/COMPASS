"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { dataTable } from "@/components/ui/data-table";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { pageSheetWidth } from "@/components/ui/page-width";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import { CounselingPageHeading, CounselingQueryError, CounselingUnavailable } from "@/features/counseling/counseling-shared";
import { useCounselingListContinuityOfficeCases } from "@/lib/api/generated/counseling/counseling";
import { continuityError, transferPrepareHref } from "./continuity-presentation";

export function OfficeContinuityPage() {
  const { user } = usePortalSession();
  const params = useSearchParams();
  const router = useRouter();
  const search = params.get("search") ?? "";
  const status = params.get("status") === "CLOSED" ? "CLOSED" : "ACTIVE";
  const [draftStatus, setDraftStatus] = useState<"ACTIVE" | "CLOSED">(status);
  const [draft, setDraft] = useState(search);
  const requested = Number(params.get("page") ?? 1);
  const page = Number.isInteger(requested) && requested >= 1 && requested <= 1000 ? requested : 1;
  const here = `/portal/counseling/continuity${params.size ? `?${params}` : ""}`;
  const allowed = user.capabilities.includes("counseling.continuity.request") && (user.role === "GUIDANCE_OFFICE_ASSISTANT" || (user.role === "COUNSELOR" && user.designations.includes("HEAD_GUIDANCE_COUNSELOR")));
  const query = useCounselingListContinuityOfficeCases({ status, search: search || undefined, page, page_size: 20 }, { query: { enabled: allowed, retry: false, staleTime: 0, gcTime: 0, refetchOnWindowFocus: "always", refetchOnReconnect: "always" } });
  function changePage(next: number, value = search, caseStatus = status) {
    const nextParams = new URLSearchParams();
    if (caseStatus !== "ACTIVE") nextParams.set("status", caseStatus);
    if (value) nextParams.set("search", value);
    if (next > 1) nextParams.set("page", String(next));
    router.replace(`/portal/counseling/continuity${nextParams.size ? `?${nextParams}` : ""}`);
  }
  function submit(event: FormEvent) { event.preventDefault(); changePage(1, draft.trim(), draftStatus); }
  if (!allowed) return <CounselingUnavailable title="Arrange case continuity" />;
  const data = query.isError ? undefined : query.data?.data;
  return <section className={pageSheetWidth}>
    <CounselingPageHeading title="Arrange case continuity" description="Prepare an arrangement when the primary Counselor is unavailable or there is a potential impartiality concern." back={<Link className={pageBackLinkClass} href="/portal/work">Back to My work</Link>} />
    <form onSubmit={submit} role="search" aria-label="Cases for continuity" className="mb-4 flex flex-wrap items-end gap-3"><div className="grid flex-1 gap-1"><Label htmlFor="continuity-case-search">Case reference or Student name</Label><Input id="continuity-case-search" type="search" maxLength={120} value={draft} onChange={event => setDraft(event.target.value)} /></div><div className="grid gap-1"><Label htmlFor="office-case-status">Case status</Label><Select id="office-case-status" value={draftStatus} onChange={event => setDraftStatus(event.target.value === "CLOSED" ? "CLOSED" : "ACTIVE")}><option value="ACTIVE">Active</option><option value="CLOSED">Closed</option></Select></div><Button type="submit">Search</Button>{search ? <Button type="button" variant="secondary" onClick={() => { setDraft(""); changePage(1, ""); }}>Clear search</Button> : null}</form>
    <Panel><PanelHeader title={status === "CLOSED" ? "Closed cases for reopening" : "Active cases"} titleId="office-continuity-cases-heading" />
      {query.isPending ? <PanelMessage role="status">Loading cases for continuity…</PanelMessage> : null}
      {query.isError ? <CounselingQueryError message={continuityError(query.error, "Couldn't load the cases available for continuity.")} onRetry={() => void query.refetch()} /> : null}
      {data?.items.length === 0 ? <PanelMessage>{search ? "No cases match this search." : `No ${status === "CLOSED" ? "Closed" : "Active"} cases are available for office preparation.`}</PanelMessage> : null}
      {data?.items.length ? <div className={dataTable.scroll}><table className={dataTable.table}><thead className={dataTable.head}><tr><th className={dataTable.headerCell}>Case and Student</th><th className={dataTable.headerCell}>Primary counselor</th><th className={dataTable.headerCell}>Status</th><th className={dataTable.headerCell}>Arrangement</th></tr></thead><tbody>{data.items.map(item => <tr key={item.id} className={dataTable.row}><td className={dataTable.cell}><p className="font-semibold">{item.reference_code}</p><p>{item.student.display_name}</p></td><td className={dataTable.cell}>{item.primary_counselor.display_name}</td><td className={dataTable.cell}>{item.status === "CLOSED" ? "Closed" : "Active"}</td><td className={dataTable.cell}>{item.status === "CLOSED" && item.primary_counselor.id === user.id ? <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`/portal/counseling/cases/${item.id}`, here)}>Open own case<span className="sr-only"> {item.reference_code}</span></Link> : <Link className="font-semibold text-brand underline" href={withWorkflowReturn(`${transferPrepareHref(item.id)}${item.status === "CLOSED" ? "?purpose=REOPEN" : ""}`, here)}>{item.status === "CLOSED" ? "Transfer to reopen" : "Transfer case"}<span className="sr-only"> {item.reference_code}</span></Link>}</td></tr>)}</tbody></table></div> : null}
    </Panel>
    {data ? <CanonicalPagination page={data.page} hasNext={data.has_next} disabled={query.isFetching} onPageChange={changePage} label="Continuity cases pages" /> : null}
  </section>;
}
