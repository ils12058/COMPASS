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
import { CsvPreviewTable } from "@/features/csv-import/csv-preview-table";
import { csvProblemMessage, readyRowNumbers, selectionSummary, problemRowsCsv } from "@/features/csv-import/csv-selection";
import {
  RosterImportFeedback,
  useRosterImportAction,
} from "@/features/student-academics/roster-import/roster-import-action";
import { AcademicImportTabs } from "@/features/student-academics/roster-import/batch-import-parts";
import { RosterCollegeReferences } from "@/features/student-academics/roster-import/roster-college-references";
import {
  rosterIssues,
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
  const [problemDownload, setProblemDownload] = useState<string | null>(null);
  const [selectedRows, setSelectedRows] = useState<number[]>([]);
  const [report, setReport] = useState<RosterImportResponse | null>(null);
  const [conflict, setConflict] = useState(false);
  const [issues, setIssues] = useState<ReturnType<typeof rosterIssues>>([]);
  const [commitReview, setCommitReview] = useState<{
    file: File;
    report: RosterImportResponse;
    selectedRows: number[];
  } | null>(null);
  const chosen = selectionSummary(report?.rows ?? [], selectedRows);
  const reviewCounts = commitReview ? selectionSummary(commitReview.report.rows, commitReview.selectedRows) : chosen;
  const readyToCommit = Boolean(file && reviewedFile === file && report && !report.committed && !conflict && chosen.write_count > 0);

  async function validate() {
    if (!file) return;
    setReport(null);
    setSelectedRows([]);
    setProblemDownload(null);
    setReviewedFile(null);
    setConflict(false);
    setIssues([]);
    const response = await action.run(
      () =>
        importCsv.mutateAsync({ data: { file }, params: { dry_run: true } }),
      "Couldn't validate the CSV. Try again.",
      undefined,
      (error) => setIssues(rosterIssues(error)),
    );
    if (!response) return;
    setReviewedFile(file);
    setReport(response.data);
    setSelectedRows(readyRowNumbers(response.data.rows));
    setProblemDownload(response.data.rows.some((row) => ["INVALID", "CONFLICT"].includes(row.action)) ? problemRowsCsv(response.data.headers, response.data.rows) : null);
  }

  function openCommitReview() {
    if (!file || !report || !readyToCommit) return;
    action.setError(null);
    action.setNotice(null);
    setCommitReview({ file, report, selectedRows: [...selectedRows] });
  }

  async function commit() {
    if (!commitReview) return;
    const reviewed = commitReview;
    const response = await action.run(
      () =>
        importCsv.mutateAsync({
          data: { file: reviewed.file, file_hash: reviewed.report.file_hash, selected_rows: JSON.stringify(reviewed.selectedRows) },
          params: { dry_run: false },
        }),
      "Couldn't complete the academic roster import. Try again.",
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
      `${response.data.set_count} placements imported, ${response.data.noop_count} already existed, ${response.data.not_selected_count} rows not selected.`,
    );
  }

  return (
    <section className="min-w-0 max-w-full" aria-labelledby="roster-import-heading">
      <AcademicImportTabs />
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
        description="This CSV updates current College placement only for existing Student accounts. It does not create or update accounts, identity, roles, status, Program, enrollment, periods, or graduation."
      />
      <Panel as="div">
        <PanelBody className="py-5">
          <div className="space-y-3 text-sm leading-6 text-muted">
            <p>
              A Student missing from the CSV keeps the current placement.
              Review and correct conflicting rows. Imported placements do
              not confirm enrollment.
            </p>
            <p>
              Required headers:{" "}
              <span className="break-all font-semibold text-ink">
                institutional_id,campus_code,college_code
              </span>
              . Both codes are required and must match an active Campus and an
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
            disabled={importCsv.isPending}
              accept=".csv,text/csv"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setReport(null);
              setSelectedRows([]);
              setProblemDownload(null);
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
                    <td className={dataTable.cell}>{csvProblemMessage(issue.message)}</td>
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
                  : "Choose the rows to import. COMPASS checks them again before saving."
                : "Select ready rows to import. Download rows with problems to fix and upload later."
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
          <CsvPreviewTable
            caption="CSV rows"
            rows={report.rows}
            headers={report.headers}
            problemDownload={problemDownload}
            total={report.total_rows}
            selected={selectedRows}
            onSelectionChange={setSelectedRows}
            committed={report.committed}
            disabled={importCsv.isPending || conflict}
            columns={[
              { header: "Row", cell: (row) => row.row_number },
              { header: "Institutional ID", cell: (row) => row.institutional_id || "—" },
              { header: "Student", cell: (row) => row.student_name || "—" },
              { header: "Current college", cell: (row) => row.current_college_code ?? "—" },
              { header: "Target campus/college", cell: (row) => `${row.campus_code || "—"} · ${row.college_code || "—"}` },
            ]}
          />
          {report.valid && report.set_count === 0 && !report.committed ? (
            <PanelBody className="border-t border-brand-line">
              <p className="text-sm text-muted">No placement changes are needed.</p>
            </PanelBody>
          ) : null}
          {!report.committed ? (
            <PanelFooter>
              <Button disabled={importCsv.isPending || !readyToCommit} onClick={openCommitReview}>
                Import selected
              </Button>
            </PanelFooter>
          ) : null}
        </Panel>
      ) : null}

      <ConsequentialActionDialog
        open={commitReview !== null}
        title={
          commitReview
            ? `Import ${reviewCounts.set_count} ${
                reviewCounts.set_count === 1 ? "placement" : "placements"
              }?`
            : "Import placements?"
        }
        confirmLabel="Import placements"
        pendingLabel="Importing placements…"
        pending={importCsv.isPending}
        confirmDisabled={conflict}
        error={action.error}
        onOpenChange={(open) => {
          if (!open) setCommitReview(null);
        }}
        onConfirm={() => void commit()}
      >
        {commitReview ? (
          <>
            <p>
              {reviewCounts.set_count} Student{" "}
              {reviewCounts.set_count === 1 ? "placement" : "placements"}{" "}
              will be set from this CSV.{" "}
              {reviewCounts.noop_count} matching{" "}
              {reviewCounts.noop_count === 1 ? "row" : "rows"} will not
              change.
            </p>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {[
                ["Set", reviewCounts.set_count],
                ["No change", reviewCounts.noop_count],
                ["Selected rows", reviewCounts.selected_count],
                ["Not selected", commitReview.report.total_rows - reviewCounts.selected_count],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-muted">{label}</dt>
                  <dd className="font-semibold text-ink">{value}</dd>
                </div>
              ))}
            </dl>
            <p>
              Imported placements don&apos;t confirm enrollment. COMPASS will check the CSV again before saving.
            </p>
          </>
        ) : null}
      </ConsequentialActionDialog>
    </section>
  );
}
