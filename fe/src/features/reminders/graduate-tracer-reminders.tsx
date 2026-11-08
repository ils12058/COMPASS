"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { SortableColumnHeader } from "@/components/ui/sortable-column-header";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import { readOrdering } from "@/features/portal/components/list-ordering-params";
import { describeResultPage } from "@/features/portal/components/result-context";
import { reminderPageValue } from "@/features/reminders/reminders-shared";
import { useGraduateTracerListReminders } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import {
  GraduateTracerReminderOrdering,
  GraduateTracerReminderState,
  type GraduateTracerReminderSummary,
} from "@/lib/api/generated/model";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";

function ReminderSummary({ reminder }: { reminder: GraduateTracerReminderSummary }) {
  const label =
    reminder.state === GraduateTracerReminderState.ANSWERED
      ? "Answered"
      : reminder.state === GraduateTracerReminderState.SENT ? "Sent" : "Upcoming";
  return (
    <>
      <span className="text-muted">Due </span>
      <time dateTime={reminder.due_date}>{formatDateOnly(reminder.due_date)}</time>
      <p className="mt-1 font-medium">{label}</p>
      {reminder.issued_at ? (
        <p className="mt-1 text-xs text-muted">
          Issued <time dateTime={reminder.issued_at}>{formatInstitutionalDateTime(reminder.issued_at)}</time>
        </p>
      ) : null}
    </>
  );
}

export function GraduateTracerReminders() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const page = reminderPageValue(searchParams.get("tracer_page"));
  const ordering = readOrdering(searchParams.get("tracer_ordering"), GraduateTracerReminderOrdering);
  const result = useGraduateTracerListReminders({ page, page_size: 20, ...(ordering ? { ordering } : {}) });
  const data = result.data?.status === 200 ? result.data.data : undefined;

  function navigate(nextPage: number, nextOrdering = ordering) {
    const params = new URLSearchParams(searchParams.toString());
    if (nextPage === 1) params.delete("tracer_page");
    else params.set("tracer_page", String(nextPage));
    if (nextOrdering) params.set("tracer_ordering", nextOrdering);
    router.push(pathname + "?" + params.toString(), { scroll: false });
  }

  return (
    <Panel className="mt-6" aria-labelledby="tracer-reminders-heading">
      <PanelHeader
        title="Graduate Tracer"
        titleId="tracer-reminders-heading"
        description="One notice six months after graduation, then one follow-up 30 days after the first notice if the survey is still unsubmitted. Sent means the in-app notice was issued. Email follows the Graduate’s preference."
        context={data ? describeResultPage({
          count: data.items.length,
          page: data.page,
          hasNext: data.has_next,
          noun: { one: "Graduate", other: "Graduates" },
        }) : null}
      />
      {result.isPending ? <RowsSkeleton label="Loading Graduate Tracer reminders…" /> : null}
      {result.isError && !data ? (
        <PanelMessage
          tone="danger"
          title="Graduate Tracer reminders could not be loaded"
          action={<Button variant="secondary" onClick={() => void result.refetch()}>Retry</Button>}
        >
          Try loading the reminders again.
        </PanelMessage>
      ) : null}
      {result.isError && data ? (
        <RefreshFailureNotice retrying={result.isFetching} onRetry={() => void result.refetch()} />
      ) : null}
      {data ? (
        <>
          {data.items.length === 0 ? <PanelMessage>No Graduate Tracer reminders for active Graduate accounts.</PanelMessage> : (
            <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Graduate Tracer reminder dates and states">
              <table className={dataTable.table + " min-w-[42rem]"}>
                <thead className={dataTable.head}>
                  <tr>
                    <th scope="col" className={dataTable.headerCell + " " + dataTable.stickyHeaderCell}>Graduate</th>
                    <SortableColumnHeader
                      label="Graduation date"
                      className={dataTable.headerCell}
                      current={data.ordering}
                      ascending={GraduateTracerReminderOrdering.EARLIEST_GRADUATION}
                      ascendingLabel="Earliest graduation first"
                      descending={GraduateTracerReminderOrdering.LATEST_GRADUATION}
                      descendingLabel="Latest graduation first"
                      onSort={(next) => navigate(1, next)}
                      disabled={result.isFetching}
                    />
                    <th scope="col" className={dataTable.headerCell}>Six-month notice</th>
                    <th scope="col" className={dataTable.headerCell}>30-day follow-up</th>
                  </tr>
                </thead>
                <tbody className={dataTable.body}>
                  {data.items.map((entry) => (
                    <tr key={entry.graduation_record_id} className={dataTable.row}>
                      <th scope="row" className={dataTable.cell + " " + dataTable.stickyCell + " text-left font-medium"}>{entry.graduate_name}</th>
                      <td className={dataTable.cell}><time dateTime={entry.graduation_date}>{formatDateOnly(entry.graduation_date)}</time></td>
                      {entry.reminders.map((reminder) => (
                        <td key={reminder.kind} className={dataTable.cell}>
                          <ReminderSummary reminder={reminder} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <CanonicalPagination
            className="px-4 py-3 sm:px-5"
            page={data.page}
            hasNext={data.has_next}
            label="Graduate Tracer reminder pages"
            disabled={result.isFetching}
            onPageChange={(next) => navigate(next)}
          />
        </>
      ) : null}
    </Panel>
  );
}
