"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter, PanelHeader } from "@/components/ui/panel";
import { CsvPreviewTable } from "@/features/csv-import/csv-preview-table";
import { readyRowNumbers, selectionSummary, problemRowsCsv } from "@/features/csv-import/csv-selection";
import {
  AcademicImportTabs,
  CsvFileField,
  CsvTemplateLink,
  ImportCounts,
  ImportIssuesTable,
} from "@/features/student-academics/roster-import/batch-import-parts";
import {
  batchCommitReady,
  graduationConsequence,
  graduationsTemplate,
  typedCountMatches,
} from "@/features/student-academics/roster-import/batch-import-presentation";
import { RosterCollegeReferences } from "@/features/student-academics/roster-import/roster-college-references";
import {
  RosterImportFeedback,
  useRosterImportAction,
} from "@/features/student-academics/roster-import/roster-import-action";
import { rosterIssues } from "@/features/student-academics/roster-import/roster-import-presentation";
import type { GraduationImportResponse } from "@/lib/api/generated/model";
import {
  getStudentAcademicsGetStudentRecordQueryKey,
  getStudentAcademicsListPlacementsQueryKey,
  useStudentAcademicsImportGraduationsCsv,
} from "@/lib/api/generated/student-academics/student-academics";

const MAX_SOURCE = 200;

export function GraduationImportPage() {
  const importCsv = useStudentAcademicsImportGraduationsCsv();
  const queryClient = useQueryClient();
  const action = useRosterImportAction();
  const [source, setSource] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [reviewed, setReviewed] = useState<{ file: File; scope: string } | null>(null);
  const [problemDownload, setProblemDownload] = useState<string | null>(null);
  const [selectedRows, setSelectedRows] = useState<number[]>([]);
  const [report, setReport] = useState<GraduationImportResponse | null>(null);
  const [conflict, setConflict] = useState(false);
  const [issues, setIssues] = useState<ReturnType<typeof rosterIssues>>([]);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [typed, setTyped] = useState("");

  const chosen = selectionSummary(report?.rows ?? [], selectedRows);
  const trimmedSource = source.trim();
  const writes = chosen.write_count;
  const ready = batchCommitReady({ file, reviewed, scope: trimmedSource, report, conflict, writes, selectedRows });

  function reset() {
    setReport(null);
    setSelectedRows([]);
    setProblemDownload(null);
    setReviewed(null);
    setConflict(false);
    setIssues([]);
    setReviewOpen(false);
    action.setError(null);
    action.setNotice(null);
  }

  async function validate() {
    if (!file || !trimmedSource) return;
    reset();
    const checked = { file, scope: trimmedSource };
    const response = await action.run(
      () => importCsv.mutateAsync({ data: { file, verification_source: trimmedSource }, params: { dry_run: true } }),
      "Couldn't validate the CSV. Try again.",
      undefined,
      (error) => setIssues(rosterIssues(error)),
    );
    if (!response) return;
    setReviewed(checked);
    setReport(response.data);
    setSelectedRows(readyRowNumbers(response.data.rows));
    setProblemDownload(response.data.rows.some((row) => ["INVALID", "CONFLICT"].includes(row.action)) ? problemRowsCsv(response.data.headers, response.data.rows) : null);
  }

  async function commit() {
    if (!report || !file) return;
    const response = await action.run(
      () =>
        importCsv.mutateAsync({
          data: {
            file,
            verification_source: trimmedSource,
            preview_fingerprint: report.preview_fingerprint,
            confirmed_count: Number(typed.trim()),
            file_hash: report.file_hash,
            selected_rows: JSON.stringify(selectedRows),
          },
          params: { dry_run: false },
        }),
      "Couldn't import the graduations. Try again.",
      () => setReviewOpen(false),
      (error) => {
        setConflict(true);
        setIssues(rosterIssues(error));
      },
    );
    if (!response) return;
    setReviewOpen(false);
    setReport(response.data);
    const studentIds = response.data.rows.flatMap((row) =>
      (row.action === "GRADUATE" || row.action === "UPDATE") && row.student_id ? [row.student_id] : [],
    );
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getStudentAcademicsListPlacementsQueryKey() }),
      ...studentIds.map((studentId) =>
        queryClient.invalidateQueries({ queryKey: getStudentAcademicsGetStudentRecordQueryKey(studentId) }),
      ),
    ]);
    action.setNotice(`${response.data.write_count} graduations imported, ${response.data.noop_count} already existed, ${response.data.not_selected_count} rows not selected.`);
  }

  return (
    <section className="min-w-0 max-w-full" aria-labelledby="graduation-import-heading">
      <AcademicImportTabs />
      <PageHeader
        title="Import graduations"
        headingId="graduation-import-heading"
        back={<Link href="/portal/organization/student-academics" className={pageBackLinkClass}>Back to Student Academic Records</Link>}
        description="Each Student becomes Graduated and leaves their current College placement. There is no batch undo."
      />
      <Panel as="div">
        <PanelBody className="space-y-4 py-5">
          <p className="text-sm leading-6 text-muted">
            Columns: <span className="font-semibold text-ink">institutional_id, campus_code, college_code, graduation_date</span>.
            Optional column: program_code, for an active Program under the row’s College. Graduation date is YYYY-MM-DD. Up to 1,000 rows. Correct a single mistake from the Student&apos;s academic record.
          </p>
          <CsvTemplateLink fileName="compass-graduations-import.csv" template={graduationsTemplate} />
          <RosterCollegeReferences />
          <div className="grid max-w-lg gap-1.5">
            <Label htmlFor="graduation-import-source">Verification source</Label>
            <Input
              id="graduation-import-source"
              disabled={importCsv.isPending}
              value={source}
              maxLength={MAX_SOURCE}
              aria-describedby="graduation-import-source-help"
              onChange={(event) => {
                setSource(event.target.value);
                reset();
              }}
            />
            <p id="graduation-import-source-help" className="text-xs text-muted">
              Applies to every row, for example &quot;Registrar&apos;s list of graduates, 2nd Semester 2025–2026&quot;.
            </p>
          </div>
          <CsvFileField
            disabled={importCsv.isPending}
            id="graduation-import-file"
            onChange={(next) => {
              setFile(next);
              reset();
            }}
          />
          <RosterImportFeedback action={action} showMessages={!reviewOpen} />
          {conflict ? <p role="status" className="text-sm text-muted">Validate the CSV again before importing.</p> : null}
        </PanelBody>
        <ImportIssuesTable issues={issues} label="Graduation row issues" />
        <PanelFooter>
          <Button disabled={!file || !trimmedSource || importCsv.isPending} onClick={() => void validate()}>
            {importCsv.isPending && !report ? "Validating CSV…" : "Validate CSV"}
          </Button>
        </PanelFooter>
      </Panel>

      {report ? (
        <Panel className="mt-5 overflow-hidden" aria-labelledby="graduation-import-report-heading">
          <PanelHeader
            title={report.committed ? "Import result" : "Preview"}
            titleId="graduation-import-report-heading"
            description={
              report.committed
                ? "Graduations were imported."
                : report.valid
                  ? writes > 0
                    ? graduationConsequence({ ...report, ...chosen })
                    : "Every graduation is already recorded."
                  : "Select ready rows to import. Download rows with problems to fix and upload later."
            }
          />
          <ImportCounts
            items={[
              ["Will graduate", report.graduate_count],
              ["Will change", report.update_count],
              ["No change", report.noop_count],
              ["Problem", report.conflict_count + report.invalid_count],
              ["Total", report.total_rows],
            ]}
          />
          <CsvPreviewTable
            caption="Graduation rows"
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
              { header: "College", cell: (row) => (row.campus_code || row.college_code ? `${row.campus_code || "—"} · ${row.college_code || "—"}` : "—") },
              { header: "Program", cell: (row) => row.previous_program_code && row.previous_program_code !== row.program_code ? `${row.previous_program_code} → ${row.program_code || "—"}` : row.program_code || "—" },
              { header: "Current placement", cell: (row) => row.current_placement_college_code ?? "—" },
              {
                header: "Graduation date",
                cell: (row) =>
                  row.previous_graduation_date && row.previous_graduation_date !== row.graduation_date
                    ? `${row.previous_graduation_date} → ${row.graduation_date}`
                    : row.graduation_date || "—",
              },
            ]}
          />
          {!report.committed ? (
            <PanelFooter>
              <Button
                variant="danger"
                disabled={importCsv.isPending || !ready}
                onClick={() => {
                  setTyped("");
                  setReviewOpen(true);
                }}
              >
                Import selected
              </Button>
            </PanelFooter>
          ) : null}
        </Panel>
      ) : null}

      <ConsequentialActionDialog
        open={reviewOpen}
        variant="danger"
        title={`Record ${writes} ${writes === 1 ? "graduation" : "graduations"}?`}
        confirmLabel="Import graduations"
        pendingLabel="Importing graduations…"
        pending={importCsv.isPending}
        confirmDisabled={conflict || !typedCountMatches(typed, writes)}
        error={action.error}
        onOpenChange={setReviewOpen}
        onConfirm={() => void commit()}
        choices={
          <div className="grid gap-1.5">
            <Label htmlFor="graduation-import-confirm">Type {writes} to confirm</Label>
            <Input
              id="graduation-import-confirm"
              inputMode="numeric"
              autoComplete="off"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
            />
          </div>
        }
      >
        {report ? <p>{graduationConsequence({ ...report, ...chosen })} There is no batch undo.</p> : null}
      </ConsequentialActionDialog>
    </section>
  );
}
