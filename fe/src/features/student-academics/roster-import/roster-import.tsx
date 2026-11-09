"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { dataTable } from "@/components/ui/data-table";
import { Label } from "@/components/ui/label";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter, PanelHeader } from "@/components/ui/panel";
import {
  RosterImportFeedback,
  useRosterImportAction,
} from "@/features/student-academics/roster-import/roster-import-action";
import { RosterCollegeReferences } from "@/features/student-academics/roster-import/roster-college-references";
import {
  rosterCommitReady,
  rosterIssues,
  rosterRowActionLabel,
  rosterTemplate,
} from "@/features/student-academics/roster-import/roster-import-presentation";
import {
  getStudentAcademicsGetStudentRecordQueryKey,
  getStudentAcademicsListPlacementsQueryKey,
  useStudentAcademicsImportRosterCsv,
} from "@/lib/api/generated/student-academics/student-academics";
import type { RosterImportResponse } from "@/lib/api/generated/model";

export function RosterImportPage() {
  const importCsv = useStudentAcademicsImportRosterCsv();
  const queryClient = useQueryClient();
  const action = useRosterImportAction();
  const [file, setFile] = useState<File | null>(null);
  const [reviewedFile, setReviewedFile] = useState<File | null>(null);
  const [report, setReport] = useState<RosterImportResponse | null>(null);
  const [conflict, setConflict] = useState(false);
  const [issues, setIssues] = useState<ReturnType<typeof rosterIssues>>([]);
  const [commitReview, setCommitReview] = useState<{
    file: File;
    report: RosterImportResponse;
  } | null>(null);
  const readyToCommit = rosterCommitReady({ file, reviewedFile, report, conflict });

  async function validate() {
    if (!file) return;
    setReport(null);
    setReviewedFile(null);
    setConflict(false);
    setIssues([]);
    const response = await action.run(
      () =>
        importCsv.mutateAsync({ data: { file }, params: { dry_run: true } }),
      "The CSV could not be validated.",
      undefined,
      (error) => setIssues(rosterIssues(error)),
    );
    if (!response) return;
    setReviewedFile(file);
    setReport(response.data);
  }

  function openCommitReview() {
    if (!file || !report || !readyToCommit) return;
    action.setError(null);
    action.setNotice(null);
    setCommitReview({ file, report });
  }

  async function commit() {
    if (!commitReview) return;
    const reviewed = commitReview;
    const response = await action.run(
      () =>
        importCsv.mutateAsync({
          data: { file: reviewed.file },
          params: { dry_run: false },
        }),
      "The academic roster import could not be completed.",
      () => setCommitReview(null),
      (error) => {
        setConflict(true);
        setIssues(rosterIssues(error));
      },
    );
    if (!response) return;
    setCommitReview(null);
    setReport(response.data);
    const studentIds = response.data.rows.flatMap((row) =>
      row.action === "SET" && row.student_id ? [row.student_id] : [],
    );
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getStudentAcademicsListPlacementsQueryKey(),
      }),
      ...studentIds.map((studentId) =>
        queryClient.invalidateQueries({
          queryKey: getStudentAcademicsGetStudentRecordQueryKey(studentId),
        }),
      ),
    ]);
    action.setNotice(
      "Academic roster import completed. Review the committed result below.",
    );
  }

  return (
    <section aria-labelledby="roster-import-heading">
      <PageHeader
        title="Import academic roster"
        headingId="roster-import-heading"
        back={
          <Link
            href="/portal/organization/student-academics"
            className={pageBackLinkClass}
          >
            Back to Student Academic Records
          </Link>
        }
        description="This CSV reconciles current College placement only for existing Student accounts. It does not create or update accounts, identity, roles, status, Program, enrollment, periods, or graduation."
      />
      <Panel as="div">
        <PanelBody className="py-5">
          <div className="space-y-3 text-sm leading-6 text-muted">
            <p>
              A Student missing from the CSV keeps the current placement.
              Conflicting rows must be resolved manually. Imported placements do
              not confirm enrollment.
            </p>
            <p>
              Required headers:{" "}
              <span className="font-semibold text-ink">
                institutional_id,campus_code,college_code
              </span>
              . Both codes are required and must resolve to an active Campus and an
              active College beneath it.{" "}
              <span className="font-semibold">program_code</span> and{" "}
              <span className="font-semibold">email</span> are not supported. Limit:
              about 1 MiB and 1,000 non-empty rows.
            </p>
          </div>
          <a
            download="compass-academic-roster-import.csv"
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(rosterTemplate)}`}
            className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Download headers-only template
          </a>
          <RosterCollegeReferences />
          <div className="mt-5 grid max-w-lg gap-1.5">
            <Label htmlFor="roster-csv-file">CSV file</Label>
            <input
              id="roster-csv-file"
              className="block w-full text-sm text-ink file:mr-4 file:rounded-md file:border file:border-border file:bg-surface-raised file:px-3 file:py-2 file:text-sm file:font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setReport(null);
                setReviewedFile(null);
                setConflict(false);
                setIssues([]);
                setCommitReview(null);
                action.setError(null);
                action.setNotice(null);
              }}
            />
          </div>
          <RosterImportFeedback action={action} showMessages={!commitReview} />
          {conflict ? (
            <p role="status" className="mt-3 text-sm text-muted">
              Review the current CSV again before attempting another import.
            </p>
          ) : null}
        </PanelBody>
        {issues.length ? (
          <div
            className={`${dataTable.scroll} border-t border-brand-line`}
            role="region"
            aria-label="Roster row issues"
          >
            <table className={`${dataTable.table} min-w-[36rem]`}>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>
                    Row
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Institutional ID
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Issue
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {issues.map((issue, index) => (
                  <tr key={`${issue.row ?? index}-${index}`} className={dataTable.row}>
                    <td className={dataTable.cell}>{issue.row ?? "—"}</td>
                    <td className={dataTable.cell}>
                      {issue.institutionalId || "—"}
                    </td>
                    <td className={dataTable.cell}>{issue.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        <PanelFooter>
          <Button
            disabled={!file || importCsv.isPending}
            onClick={() => void validate()}
          >
            {importCsv.isPending && !report ? "Validating CSV…" : "Validate CSV"}
          </Button>
        </PanelFooter>
      </Panel>

      {report ? (
        <Panel className="mt-5 overflow-hidden" aria-labelledby="roster-report-heading">
          <PanelHeader
            title={report.committed ? "Import result" : "Validation report"}
            titleId="roster-report-heading"
            description={
              report.valid
                ? report.committed
                  ? "The academic roster import was completed."
                  : "The CSV is valid for import. Records may change before commit."
                : "Resolve the conflicts or invalid rows, then validate the CSV again."
            }
          />
          <dl className="grid grid-cols-2 gap-px border-b border-brand-line bg-border text-sm sm:grid-cols-5">
            {[
              ["Total", report.total_rows],
              ["Set", report.set_count],
              ["No change", report.noop_count],
              ["Conflict", report.conflict_count],
              ["Invalid", report.invalid_count],
            ].map(([label, value]) => (
              <div
                key={label}
                className="bg-surface-raised px-4 py-3 last:odd:col-span-2 sm:px-5 sm:last:odd:col-span-1"
              >
                <dt className="text-muted">{label}</dt>
                <dd className="mt-1 font-heading text-xl font-semibold tabular-nums text-ink">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[64rem]`}>
              <caption className="sr-only">Academic roster rows</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>
                    Row
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Institutional ID
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Student
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Current College
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Target Campus/College
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Action
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Message
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {report.rows.map((row) => (
                  <tr
                    key={`${row.row_number}-${row.institutional_id}`}
                    className={dataTable.row}
                  >
                    <td className={dataTable.cell}>{row.row_number}</td>
                    <td className={dataTable.cell}>
                      {row.institutional_id || "—"}
                    </td>
                    <td className={dataTable.cell}>
                      {row.student_name || "—"}
                    </td>
                    <td className={dataTable.cell}>
                      {row.current_college_code ?? "—"}
                    </td>
                    <td className={dataTable.cell}>
                      {row.campus_code || row.college_code
                        ? `${row.campus_code || "—"} · ${row.college_code || "—"}`
                        : "—"}
                    </td>
                    <td className={`${dataTable.cell} font-semibold`}>
                      {rosterRowActionLabel(row.action)}
                    </td>
                    <td className={dataTable.cell}>{row.message || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {report.valid && report.set_count === 0 && !report.committed ? (
            <PanelBody className="border-t border-brand-line">
              <p className="text-sm text-muted">No placement changes are needed.</p>
            </PanelBody>
          ) : null}
          {readyToCommit ? (
            <PanelFooter>
              <Button disabled={importCsv.isPending} onClick={openCommitReview}>
                Import placements
              </Button>
            </PanelFooter>
          ) : null}
        </Panel>
      ) : null}

      <ConsequentialActionDialog
        open={commitReview !== null}
        title={
          commitReview
            ? `Import ${commitReview.report.set_count} ${
                commitReview.report.set_count === 1 ? "placement" : "placements"
              }?`
            : "Import placements?"
        }
        confirmLabel="Import placements"
        pendingLabel="Importing placements…"
        pending={importCsv.isPending}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setCommitReview(null);
        }}
        onConfirm={() => void commit()}
      >
        {commitReview ? (
          <>
            <p>
              {commitReview.report.set_count} Student{" "}
              {commitReview.report.set_count === 1 ? "placement" : "placements"}{" "}
              will be set from this CSV.{" "}
              {commitReview.report.noop_count} matching{" "}
              {commitReview.report.noop_count === 1 ? "row" : "rows"} will not
              change.
            </p>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {[
                ["Set", commitReview.report.set_count],
                ["No change", commitReview.report.noop_count],
                ["Conflict", commitReview.report.conflict_count],
                ["Invalid", commitReview.report.invalid_count],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-muted">{label}</dt>
                  <dd className="font-semibold text-ink">{value}</dd>
                </div>
              ))}
            </dl>
            <p>
              Imported placements do not confirm enrollment. Server checks remain
              authoritative at commit time.
            </p>
          </>
        ) : null}
      </ConsequentialActionDialog>
    </section>
  );
}
