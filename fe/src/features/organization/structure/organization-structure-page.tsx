"use client";

import { Plus } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ContextHelp } from "@/components/ui/context-help";
import { FilterField } from "@/components/ui/filter-toolbar";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { PageAction } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { focusHeading } from "@/lib/focus-heading";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { canManageOrganization, canManageOrganizationCatalog } from "@/features/institution-configuration/institution-access";
import { QueryError, StatusBadge, TableSkeleton } from "@/features/organization/components/organization-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useOrganizationListCampuses, useOrganizationListColleges, useOrganizationListPrograms } from "@/lib/api/generated/organization/organization";
import { CatalogActions } from "./catalog/catalog-actions";
import { CatalogEditor } from "./catalog/catalog-editor";
import { CatalogHistory } from "./catalog/catalog-history";
import { academicProgramLabel, filterHierarchy, type BrowseFilters, type CatalogIntent, type CatalogTarget } from "./catalog/catalog-model";

const emptyFilters: BrowseFilters = { search: "", status: "", campus: "", college: "" };

export function OrganizationStructurePage() {
  const { user, session } = usePortalSession();
  return <StructureWorkspace key={`${user.id}:${session.id}`} />;
}
function StructureWorkspace() {
  const { user } = usePortalSession();
  const canEdit = canManageOrganizationCatalog(user);
  const campuses = useOrganizationListCampuses({}, { query: { retry: false } });
  const colleges = useOrganizationListColleges({}, { query: { retry: false } });
  const programs = useOrganizationListPrograms({}, { query: { retry: false } });
  const [filters, setFilters] = useState(emptyFilters);
  const [applied, setApplied] = useState(emptyFilters);
  const [editor, setEditor] = useState<{ id: number; intent: CatalogIntent } | null>(null);
  const [history, setHistory] = useState<CatalogTarget | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const editorSequence = useRef(0);
  const hasError = campuses.isError || colleges.isError || programs.isError;
  const campusData = safeQueryData(campuses);
  const collegeData = safeQueryData(colleges);
  const programData = safeQueryData(programs);
  const loaded = Boolean(campusData && collegeData && programData);
  const pending = !loaded && (campuses.isPending || colleges.isPending || programs.isPending);
  const campusItems = campusData?.data.items ?? [];
  const collegeItems = collegeData?.data.items ?? [];
  const programItems = programData?.data.items ?? [];
  const visible = filterHierarchy(campusItems, collegeItems, programItems, applied);
  const filtered = Object.values(applied).some(Boolean);
  const editing = canEdit && Boolean(editor);
  function returnFocus() {
    requestAnimationFrame(() => {
      if (opener.current?.isConnected) opener.current.focus();
      else focusHeading("organization-structure-heading");
    });
  }
  function openEditor(intent: CatalogIntent, element: HTMLElement) {
    opener.current = element;
    setEditor({ id: ++editorSequence.current, intent });
  }
  function actions(target: CatalogTarget) {
    return canEdit ? <CatalogActions target={target} disabled={hasError || editing} onEdit={openEditor} onHistory={(target, element) => { opener.current = element; setHistory(target); }} /> : null;
  }
  function showSaved(target: CatalogTarget) {
    const campusId = target.kind === "campus" ? target.record.id : target.kind === "college" ? target.record.campus.id : target.record.college.campus.id;
    const collegeId = target.kind === "program" ? target.record.college.id : target.kind === "college" ? target.record.id : "";
    const next = { ...emptyFilters, campus: campusId, college: collegeId };
    setFilters(next); setApplied(next);
  }
  return <section aria-labelledby="organization-structure-heading" className="max-w-4xl [overflow-wrap:anywhere]">
    <div className="@container/structure-heading"><PageHeader title="Organization structure" headingId="organization-structure-heading"
      className="[&>div]:flex-col [&>div>div:last-child]:max-w-full @[36rem]/structure-heading:[&>div]:flex-row"
      actions={canEdit ? <PageAction icon={Plus} label="Add campus" disabled={hasError || !loaded || editing} onClick={(event) => openEditor({ mode: "create", kind: "campus" }, event.currentTarget)} /> : undefined}
      help={<ContextHelp title="Organization structure" sections={[
        { heading: "Catalog and relationships", content: <p>Campus, College and Program definitions belong here. Counselor Responsibilities and Student affiliations have separate authority and workflows.</p> },
        { heading: "Academic policy and history", content: <p>Year Levels show the configured set. Pending policy is not approval to activate a Program. Current linked names can change; submitted records and issued certificates keep their saved facts.</p> },
        { heading: "Browse context", content: <p>Search matches official codes and names. Parents stay visible when a descendant matches; context labels identify parents outside the selected status or search. All returned records, including inactive records, are searched.</p> },
      ]} />}
    /></div>
    {editing && editor ? <CatalogEditor key={editor.id} intent={editor.intent} knownIds={[...campusItems, ...collegeItems, ...programItems].map((item) => item.id)} canManageRelationships={canManageOrganization(user)} onClose={() => { setEditor(null); returnFocus(); }} onSaved={showSaved} /> : null}
    {pending ? <TableSkeleton /> : hasError && !loaded ? <QueryError error={campuses.error ?? colleges.error ?? programs.error} fallback="Organization structure could not be loaded." onRetry={() => { void campuses.refetch(); void colleges.refetch(); void programs.refetch(); }} /> : <>
      {hasError ? <RefreshFailureNotice onRetry={() => { void campuses.refetch(); void colleges.refetch(); void programs.refetch(); }} /> : null}
      {loaded && !campusItems.length ? <Notice>No organization structure is available.</Notice> : !visible.length ? <Notice action={<Button variant="secondary" onClick={() => { setFilters(emptyFilters); setApplied(emptyFilters); }}>Clear filters</Button>}>No records match the current search and filters.</Notice> : <ol className="space-y-5">
        {visible.map(({ campus, colleges: children, contextOnly }) => <li key={campus.id}>
          <Panel aria-labelledby={`campus-${campus.id}`}>
            <PanelHeader title={campus.name} titleId={`campus-${campus.id}`} description={<><span className="font-mono">{campus.code}</span>{contextOnly ? " · Parent context" : ""}</>} actions={<StatusBadge active={campus.is_active} />} />
            {canEdit ? <div className="px-4 sm:px-5">{actions({ kind: "campus", record: campus })}</div> : null}
            {!children.length ? <PanelMessage>{filtered ? "No colleges match these filters in this campus." : "No colleges are recorded for this campus."}</PanelMessage> : <ul className="divide-y divide-border">
              {children.map(({ college, programs: items, contextOnly }) => <li key={college.id} className="px-4 py-3.5 sm:px-5" aria-labelledby={`college-${college.id}`}>
                <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><h3 id={`college-${college.id}`} className="font-heading text-base font-semibold text-ink">{college.name}</h3><p className="text-sm text-muted"><span className="font-mono">{college.code}</span>{contextOnly ? " · Parent context" : ""}</p></div><StatusBadge active={college.is_active} /></div>
                {actions({ kind: "college", record: college })}
                {!items.length ? <p className="mt-2 pl-3 text-sm text-muted">{filtered ? "No programs match these filters." : "No programs are recorded."}</p> : <ul aria-label={`Programs in ${college.name}`} className="mt-2 divide-y divide-border pl-3 sm:pl-6">
                  {items.map((program) => <li key={program.id} className="py-3" aria-label={program.name}>
                    <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0 flex-1"><p className="text-sm font-semibold text-ink">{program.name}</p><p className="font-mono text-xs text-muted">{program.code}</p><p className="mt-1 text-sm text-muted">{academicProgramLabel(program)}</p></div><StatusBadge active={program.is_active} /></div>
                    {actions({ kind: "program", record: program })}
                  </li>)}
                </ul>}
              </li>)}
            </ul>}
          </Panel>
        </li>)}
      </ol>}
      {!editing && loaded ? <form role="search" aria-label="Search organization structure" onSubmit={(event) => { event.preventDefault(); setApplied({ ...filters }); }}>
        <FloatingListTools submits filterCount={[applied.status, applied.campus, applied.college].filter(Boolean).length} clear={filtered ? <Button variant="quiet" onClick={() => { setFilters(emptyFilters); setApplied(emptyFilters); }}>Clear filters</Button> : null}
          filters={<>
            <FilterField label="Status" htmlFor="structure-status"><Select id="structure-status" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}><option value="">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></Select></FilterField>
            <FilterField label="Campus" htmlFor="structure-campus"><Select id="structure-campus" value={filters.campus} onChange={(event) => setFilters({ ...filters, campus: event.target.value, college: "" })}><option value="">All campuses</option>{campusItems.map((campus) => <option key={campus.id} value={campus.id}>{campus.name} ({campus.code})</option>)}</Select></FilterField>
            <FilterField label="College" htmlFor="structure-college"><Select id="structure-college" value={filters.college} onChange={(event) => setFilters({ ...filters, college: event.target.value })}><option value="">All colleges</option>{collegeItems.filter((college) => !filters.campus || college.campus.id === filters.campus).map((college) => <option key={college.id} value={college.id}>{college.name} ({college.campus.code} / {college.code})</option>)}</Select></FilterField>
          </>}>
          <ListSearchField id="structure-search" label="Search codes or names" value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value })} />
        </FloatingListTools>
      </form> : null}
    </>}
    {canEdit && history ? <CatalogHistory key={`${history.kind}:${history.record.id}`} target={history} onClose={() => setHistory(null)} onCloseAutoFocus={(event) => { event.preventDefault(); returnFocus(); }} /> : null}
  </section>;
}
