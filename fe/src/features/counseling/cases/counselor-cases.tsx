"use client";

import { FolderPlus, NotebookText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { FloatingListTools, ListSearchField } from "@/components/ui/floating-list-tools";
import { PageActionLink } from "@/components/ui/page-action";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { SortField } from "@/components/ui/sort-field";
import { SortableColumnHeader } from "@/components/ui/sortable-column-header";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import {
  caseErrorMessage,
  caseHref,
  caseOrderingOptions,
  openCaseHref,
  SESSION_RECORDS_PATH,
} from "@/features/counseling/cases/case-presentation";
import { CaseStatusBadge } from "@/features/counseling/cases/case-status-badge";
import { withWorkflowReturn } from "@/features/portal/workflow-navigation";
import type { CounselingAccess } from "@/features/counseling/counseling-access";
import { CounselingHelp } from "@/features/counseling/counseling-help";
import {
  CounselingListSkeleton,
  CounselingPageHeading,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { useListOrdering } from "@/features/portal/components/list-ordering";
import { describeResultPage } from "@/features/portal/components/result-context";
import { useCounselingListMyCases } from "@/lib/api/generated/counseling/counseling";
import { CounselingCaseOrdering } from "@/lib/api/generated/model";

function positivePage(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

function pageHref(pathname: string, current: URLSearchParams, page: number): string {
  const next = new URLSearchParams(current);
  if (page > 1) next.set("page", String(page));
  else next.delete("page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

// The Counselor's own cases. A case appears here only for its primary Counselor; the backend
// decides that, and this list never widens it.
export function CounselorCases({ access }: { access: CounselingAccess }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const here = `${pathname}${searchParams.size ? `?${searchParams}` : ""}`;
  const page = positivePage(searchParams.get("page"));
  const search = searchParams.get("search") ?? "";
  const { requested: requestedOrdering, setOrdering } = useListOrdering(CounselingCaseOrdering);
  const cases = useCounselingListMyCases(
    {
      ...(search ? { search } : {}),
      ...(requestedOrdering ? { ordering: requestedOrdering } : {}),
      page,
      page_size: 20,
    },
    { query: { enabled: access.canViewAssigned, retry: false } },
  );
  const items = cases.data?.data.items ?? [];
  const ordering = requestedOrdering ?? cases.data?.data.ordering;
  const clearedHref = requestedOrdering ? `${pathname}?ordering=${requestedOrdering}` : pathname;

  return (
    <div>
      <CounselingPageHeading
        title="Counseling"
        help={<CounselingHelp />}
        action={
          <>
            {access.canManageAssigned ? (
              <PageActionLink href={openCaseHref()} icon={FolderPlus} label="Open case" />
            ) : null}
            <PageActionLink href={SESSION_RECORDS_PATH} icon={NotebookText} label="Session records" variant="secondary" />
            {access.canViewCoverage ? (
              <PageActionLink href="/portal/counseling/coverage" icon={ShieldCheck} label="Case coverage" variant="secondary" />
            ) : null}
          </>
        }
      />

      <section aria-labelledby="my-cases-heading">
        <form action={pathname} method="get" key={searchParams.toString()} role="search" aria-label="My cases">
          {requestedOrdering ? <input type="hidden" name="ordering" value={requestedOrdering} /> : null}
          <FloatingListTools
            submits
            label="Case search"
            clear={search ? <Button variant="quiet" onClick={() => router.replace(clearedHref, { scroll: false })}>Clear search</Button> : undefined}
          >
            <ListSearchField id="case-search" name="search" label="Search Student name, Institutional ID, or case reference" placeholder="Search Student name, Institutional ID, or case reference" defaultValue={search} maxLength={160} />
          </FloatingListTools>
        </form>

        <Panel as="div">
          <PanelHeader
            title="My cases"
            titleId="my-cases-heading"
            actions={<SortField id="case-sort" value={ordering} options={caseOrderingOptions} onChange={setOrdering} />}
            context={cases.data && !cases.isError ? describeResultPage({
              count: items.length,
              page: cases.data.data.page,
              hasNext: cases.data.data.has_next,
              noun: { one: "case", other: "cases" },
              filtered: Boolean(search),
            }) : null}
          />
          {cases.isPending ? (
            <CounselingListSkeleton label="Loading your cases…" framed={false} />
          ) : cases.isError ? (
            <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void cases.refetch()}>Retry</Button>}>
              {caseErrorMessage(cases.error, "Couldn't load your cases.")}
            </PanelMessage>
          ) : items.length === 0 ? (
            <PanelMessage>
              {search
                ? "No cases match this search. Clear or change it to broaden the results."
                : "You have no cases yet. Sessions you recorded earlier stay in Session records until you add them to a case."}
            </PanelMessage>
          ) : (
            <div className={dataTable.scroll}>
              <table className={`${dataTable.table} min-w-[820px]`}>
                <caption className="sr-only">Counseling cases you are responsible for</caption>
                <thead className={dataTable.head}>
                  <tr>
                    <SortableColumnHeader label="Student" ascending={CounselingCaseOrdering.STUDENT_ASC} descending={CounselingCaseOrdering.STUDENT_DESC} ascendingLabel="Student A–Z" descendingLabel="Student Z–A" current={ordering} onSort={setOrdering} className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`} />
                    <th scope="col" className={dataTable.headerCell}>Case</th>
                    <th scope="col" className={dataTable.headerCell}>Status</th>
                    <th scope="col" className={dataTable.headerCell}>Completed sessions</th>
                    <th scope="col" className={dataTable.headerCell}>Latest session</th>
                    <SortableColumnHeader label="Opened" ascending={CounselingCaseOrdering.OLDEST_OPENED} descending={CounselingCaseOrdering.LATEST_OPENED} ascendingLabel="Oldest case first" descendingLabel="Newest case first" firstDirection="descending" current={ordering} onSort={setOrdering} className={dataTable.headerCell} />
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {items.map((item) => (
                    <tr key={item.id} className={dataTable.row}>
                      <th scope="row" className={`${dataTable.cell} ${dataTable.stickyCell} min-w-48 font-normal`}>
                        <span className="flex items-center gap-2">
                          <PersonAvatar displayName={item.student.display_name} photoUrl={item.student.profile_photo_url} photoUpdatedAt={item.student.profile_photo_updated_at} size="compact" />
                          <Link href={withWorkflowReturn(caseHref(item.id), here)} className="font-semibold text-brand underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{item.student.display_name}</Link>
                        </span>
                        {item.student.institutional_id ? <span className="mt-1 block text-xs text-muted">{item.student.institutional_id}</span> : null}
                      </th>
                      <td className={`${dataTable.cell} whitespace-nowrap`}>{item.reference_code}</td>
                      <td className={dataTable.cell}><CaseStatusBadge status={item.status} /></td>
                      <td className={dataTable.cell}>{item.session_count}</td>
                      <td className={dataTable.cell}>{item.latest_session_at ? formatCounselingDateTime(item.latest_session_at) : "No session yet"}</td>
                      <td className={dataTable.cell}>{formatCounselingDateTime(item.opened_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!cases.isPending && !cases.isError ? (
            <CanonicalPagination
              className="border-brand-line px-4 py-3 sm:px-5"
              label="Case results pages"
              page={cases.data?.data.page ?? page}
              hasNext={cases.data?.data.has_next ?? false}
              onPageChange={(nextPage) => router.push(pageHref(pathname, new URLSearchParams(searchParams.toString()), nextPage), { scroll: false })}
            />
          ) : null}
        </Panel>
      </section>
    </div>
  );
}
