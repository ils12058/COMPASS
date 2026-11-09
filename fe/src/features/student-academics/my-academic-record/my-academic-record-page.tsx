"use client";

import { dataTable } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import {
  QueryError,
  StatusBadge,
  TableSkeleton,
} from "@/features/organization/components/organization-shared";
import { useStudentAcademicsGetMyRecord } from "@/lib/api/generated/student-academics/student-academics";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  academicTermLabel,
  enrollmentStatusLabel,
  lifecycleStatusLabel,
  yearLevelLabel,
} from "../student-academic-record/academic-record-presentation";

function RecordFact({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-ink">{children}</dd>
    </div>
  );
}

export function MyAcademicRecordPage() {
  const record = useStudentAcademicsGetMyRecord({ query: { retry: false } });

  if (record.isPending) {
    return <TableSkeleton label="Loading your academic record…" />;
  }

  if (record.isError && !record.data) {
    return (
      <QueryError
        error={record.error}
        fallback="Your academic record could not be loaded."
        onRetry={() => void record.refetch()}
      />
    );
  }

  const data = record.data.data;

  return (
    <section aria-labelledby="my-academic-record-heading">
      <PageHeader
        title="Academic record"
        headingId="my-academic-record-heading"
        meta={
          <span className="flex flex-wrap items-center gap-2">
            <span className="inline-flex rounded-full border border-border bg-surface-muted px-2 py-0.5 text-xs font-semibold text-muted">
              {lifecycleStatusLabel(data.lifecycle_status)}
            </span>
            <StatusBadge active={data.student.is_active} />
          </span>
        }
      />

      <Panel aria-labelledby="my-academic-placement-heading" className="mb-5">
        <PanelHeader
          title="Academic placement"
          titleId="my-academic-placement-heading"
        />
        {data.placement ? (
          <div className="px-4 py-4 sm:px-5">
            <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
              <span>
                {data.placement.college.campus.name} ·{" "}
                {data.placement.college.name}
              </span>
            </p>
            <p className="mt-2 text-sm leading-6 text-muted">
              This placement is recorded by the institution. It does not by
              itself confirm enrollment.
            </p>
          </div>
        ) : (
          <PanelMessage>No academic placement recorded.</PanelMessage>
        )}
      </Panel>

      <Panel aria-labelledby="my-academic-periods-heading" className="mb-5">
        <PanelHeader
          title="Academic periods"
          titleId="my-academic-periods-heading"
          context={
            data.periods.length === 1
              ? "1 recorded"
              : `${data.periods.length} recorded`
          }
        />
        {data.periods.length === 0 ? (
          <PanelMessage>No academic periods recorded.</PanelMessage>
        ) : (
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[36rem]`}>
              <caption className="sr-only">Academic periods</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th
                    scope="col"
                    className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell}`}
                  >
                    Academic year
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Term
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    College
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Year level
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Enrollment status
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {data.periods.map((item) => (
                  <tr key={item.id} className={dataTable.row}>
                    <th
                      scope="row"
                      className={`${dataTable.cell} ${dataTable.stickyCell} font-normal text-ink`}
                    >
                      {item.academic_year.label}
                    </th>
                    <td className={dataTable.cell}>
                      {academicTermLabel(item.term)}
                    </td>
                    <td className={dataTable.cell}>{item.college.name}</td>
                    <td className={dataTable.cell}>
                      {yearLevelLabel(item.year_level)}
                    </td>
                    <td className={dataTable.cell}>
                      {enrollmentStatusLabel(item.enrollment_status)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <Panel aria-labelledby="my-graduation-heading" className="mb-5">
        <PanelHeader title="Graduation" titleId="my-graduation-heading" />
        {data.graduation ? (
          <div className="px-4 py-4 sm:px-5">
            <dl className="grid gap-4 sm:grid-cols-2">
              <RecordFact label="Graduated college">
                {data.graduation.graduated_college.name}
              </RecordFact>
              <RecordFact label="Graduation date">
                {formatDateOnly(data.graduation.graduation_date)}
              </RecordFact>
              <RecordFact label="Verification source">
                {data.graduation.verification_source}
              </RecordFact>
              <RecordFact label="Verified by">
                {data.graduation.verified_by?.full_name ?? "Not recorded"}
              </RecordFact>
              <RecordFact label="Verified at">
                {formatInstitutionalDateTime(data.graduation.verified_at)}
              </RecordFact>
            </dl>
          </div>
        ) : (
          <PanelMessage>No graduation recorded.</PanelMessage>
        )}
      </Panel>

      <p className="text-sm leading-6 text-muted">
        If this information is incorrect, contact the Registrar or Guidance
        office.
      </p>
    </section>
  );
}
