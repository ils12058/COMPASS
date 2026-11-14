"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter, PanelHeader } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  AcademicImportTabs,
  CsvFileField,
  CsvTemplateLink,
  ImportCounts,
  ImportIssuesTable,
  ImportRowsTable,
} from "@/features/student-academics/roster-import/batch-import-parts";
import {
  batchCommitReady,
  batchRowActionLabel,
  periodWriteCount,
  termFacts,
  termRecordsTemplate,
} from "@/features/student-academics/roster-import/batch-import-presentation";
import { RosterCollegeReferences } from "@/features/student-academics/roster-import/roster-college-references";
import {
  RosterImportFeedback,
  useRosterImportAction,
} from "@/features/student-academics/roster-import/roster-import-action";
import { rosterIssues } from "@/features/student-academics/roster-import/roster-import-presentation";
import { academicTermLabel } from "@/features/student-academics/student-academic-record/academic-record-presentation";
import { useAcademicYearsList } from "@/lib/api/generated/academic-years/academic-years";
import type { AcademicTerm, PeriodImportResponse } from "@/lib/api/generated/model";
import {
  getStudentAcademicsGetStudentRecordQueryKey,
  useStudentAcademicsImportPeriodsCsv,
} from "@/lib/api/generated/student-academics/student-academics";

const terms: AcademicTerm[] = ["FIRST_SEMESTER", "SECOND_SEMESTER"];

export function TermRecordsImportPage() {
  const { user } = usePortalSession();
  const canViewYears = user.capabilities.includes("academic_years.view");
  const years = useAcademicYearsList({ query: { enabled: canViewYears, retry: false } });
  const yearItems = years.data?.data.items ?? [];
  const importCsv = useStudentAcademicsImportPeriodsCsv();
  const queryClient = useQueryClient();
  const action = useRosterImportAction();
  const [chosenYearId, setChosenYearId] = useState("");
  const [term, setTerm] = useState<AcademicTerm>("FIRST_SEMESTER");
  const [file, setFile] = useState<File | null>(null);
  const [reviewed, setReviewed] = useState<{ file: File; scope: string } | null>(null);
  const [report, setReport] = useState<PeriodImportResponse | null>(null);
  const [conflict, setConflict] = useState(false);
  const [issues, setIssues] = useState<ReturnType<typeof rosterIssues>>([]);
  const [reviewOpen, setReviewOpen] = useState(false);

  // The current academic year is the usual choice; the operator can pick another before validating.
  const yearId = chosenYearId || yearItems.find((item) => item.is_current)?.id || "";
  const yearLabel = yearItems.find((item) => item.id === yearId)?.label ?? "";
  const scope = `${yearId}|${term}`;
  const writes = report ? periodWriteCount(report) : 0;
  const ready = batchCommitReady({ file, reviewed, scope, report, conflict, writes });

  function reset() {
    setReport(null);
    setReviewed(null);
    setConflict(false);
    setIssues([]);
    setReviewOpen(false);
    action.setError(null);
    action.setNotice(null);
  }

  async function validate() {
    if (!file || !yearId) return;
    reset();
    const checked = { file, scope };
    const response = await action.run(
      () => importCsv.mutateAsync({ data: { file, academic_year_id: yearId, term }, params: { dry_run: true } }),
      "Couldn't validate the CSV. Try again.",
      undefined,
      (error) => setIssues(rosterIssues(error)),
    );
    if (!response) return;
    setReviewed(checked);
    setReport(response.data);
  }

  async function commit() {
    if (!report || !file) return;
    const response = await action.run(
      () =>
        importCsv.mutateAsync({
          data: { file, academic_year_id: yearId, term, preview_fingerprint: report.preview_fingerprint },
          params: { dry_run: false },
        }),
      "Couldn't import the term records. Try again.",
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
      (row.action === "CREATE" || row.action === "UPDATE") && row.student_id ? [row.student_id] : [],
    );
    await Promise.all(
      studentIds.map((studentId) =>
        queryClient.invalidateQueries({ queryKey: getStudentAcademicsGetStudentRecordQueryKey(studentId) }),
      ),
    );
    action.setNotice("Term records imported.");
  }

  return (
    <section aria-labelledby="term-import-heading">
      <AcademicImportTabs />
      <PageHeader
        title="Import term records"
        headingId="term-import-heading"
        back={<Link href="/portal/organization/student-academics" className={pageBackLinkClass}>Back to Student Academic Records</Link>}
        description="Year level and enrollment for one academic year and term. Current College placement doesn't change."
      />
      <Panel as="div">
        <PanelBody className="space-y-4 py-5">
          <p className="text-sm leading-6 text-muted">
            Columns: <span className="font-semibold text-ink">institutional_id, campus_code, college_code, year_level, enrollment_status</span>.
            Year level is 1 to 8 or blank. Enrollment status is ENROLLED, NOT_ENROLLED, UNKNOWN, or blank for Unknown. Up to 1,000 rows.
          </p>
          <CsvTemplateLink fileName="compass-term-records-import.csv" template={termRecordsTemplate} />
          <RosterCollegeReferences />
          <div className="grid max-w-lg gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="term-import-year">Academic year</Label>
              <Select
                id="term-import-year"
                value={yearId}
                disabled={!canViewYears || years.isPending || years.isError}
                onChange={(event) => {
                  setChosenYearId(event.target.value);
                  reset();
                }}
              >
                {!yearId ? <option value="">Choose an academic year</option> : null}
                {yearItems.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}{item.is_current ? " (current)" : ""}</option>
                ))}
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="term-import-term">Term</Label>
              <Select
                id="term-import-term"
                value={term}
                onChange={(event) => {
                  setTerm(event.target.value as AcademicTerm);
                  reset();
                }}
              >
                {terms.map((value) => <option key={value} value={value}>{academicTermLabel(value)}</option>)}
              </Select>
            </div>
          </div>
          {!canViewYears ? (
            <p role="alert" className="text-sm text-danger">You don&apos;t have access to academic years, so term records can&apos;t be imported.</p>
          ) : years.isError ? (
            <p role="alert" className="text-sm text-danger">
              Couldn&apos;t load academic years.{" "}
              <Button variant="quiet" className="px-1" onClick={() => void years.refetch()}>Retry</Button>
            </p>
          ) : null}
          <CsvFileField
            id="term-import-file"
            onChange={(next) => {
              setFile(next);
              reset();
            }}
          />
          <RosterImportFeedback action={action} showMessages={!reviewOpen} />
          {conflict ? <p role="status" className="text-sm text-muted">Validate the CSV again before importing.</p> : null}
        </PanelBody>
        <ImportIssuesTable issues={issues} label="Term record row issues" />
        <PanelFooter>
          <Button disabled={!file || !yearId || importCsv.isPending} onClick={() => void validate()}>
            {importCsv.isPending && !report ? "Validating CSV…" : "Validate CSV"}
          </Button>
        </PanelFooter>
      </Panel>

      {report ? (
        <Panel className="mt-5 overflow-hidden" aria-labelledby="term-import-report-heading">
          <PanelHeader
            title={report.committed ? "Import result" : "Preview"}
            titleId="term-import-report-heading"
            description={
              report.committed
                ? `${yearLabel} · ${academicTermLabel(term)} term records were imported.`
                : report.valid
                  ? `${yearLabel} · ${academicTermLabel(term)}. Nothing is saved until you import.`
                  : "Fix the rows marked Problem, then validate again."
            }
          />
          <ImportCounts
            items={[
              ["New", report.create_count],
              ["Will change", report.update_count],
              ["No change", report.noop_count],
              ["Problem", report.conflict_count + report.invalid_count],
              ["Total", report.total_rows],
            ]}
          />
          <ImportRowsTable
            caption="Term record rows"
            rows={report.rows}
            rowKey={(row) => `${row.row_number}-${row.institutional_id}`}
            columns={[
              { header: "Row", cell: (row) => row.row_number },
              { header: "Institutional ID", cell: (row) => row.institutional_id || "—" },
              { header: "Student", cell: (row) => row.student_name || "—" },
              { header: "College", cell: (row) => (row.campus_code || row.college_code ? `${row.campus_code || "—"} · ${row.college_code || "—"}` : "—") },
              { header: "Now", cell: (row) => (row.action === "CREATE" ? "No record" : termFacts(row.current_year_level, row.current_enrollment_status)) },
              { header: "From CSV", cell: (row) => (row.action === "INVALID" ? "—" : termFacts(row.year_level, row.enrollment_status)) },
              { header: "Result", cell: (row) => batchRowActionLabel(row.action), strong: true },
              { header: "Note", cell: (row) => row.message || "—" },
            ]}
          />
          {report.valid && writes === 0 && !report.committed ? (
            <PanelBody className="border-t border-brand-line"><p className="text-sm text-muted">Every term record already matches.</p></PanelBody>
          ) : null}
          {ready ? (
            <PanelFooter>
              <Button disabled={importCsv.isPending} onClick={() => setReviewOpen(true)}>Import term records</Button>
            </PanelFooter>
          ) : null}
        </Panel>
      ) : null}

      <ConsequentialActionDialog
        open={reviewOpen}
        title={`Import ${writes} term ${writes === 1 ? "record" : "records"}?`}
        confirmLabel="Import term records"
        pendingLabel="Importing term records…"
        pending={importCsv.isPending}
        error={action.error}
        onOpenChange={setReviewOpen}
        onConfirm={() => void commit()}
      >
        {report ? (
          <p>
            {yearLabel} · {academicTermLabel(term)}: {report.create_count} new and {report.update_count} changed.{" "}
            If any record changed since the preview, nothing is saved.
          </p>
        ) : null}
      </ConsequentialActionDialog>
    </section>
  );
}
