"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { dataTable } from "@/components/ui/data-table";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter, PanelHeader } from "@/components/ui/panel";
import {
  ManagedActionFeedback,
  useInvalidateManagedAccount,
  useManagedAction,
} from "@/features/accounts/components/account-action";
import { useAccountsImportCsv } from "@/lib/api/generated/accounts/accounts";
import type { CsvImportResponse } from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/errors";

const template =
  "institutional_id,email,first_name,middle_name,last_name,suffix,role\n";

const rowActionLabels: Record<string, [review: string, committed: string]> = {
  CREATE: ["Create", "Created"],
  SKIP: ["Skip", "Skipped"],
  CONFLICT: ["Conflict", "Conflict"],
  INVALID: ["Invalid", "Invalid"],
};

function rowActionLabel(action: string, committed: boolean): string {
  const labels = rowActionLabels[action];
  return labels ? labels[committed ? 1 : 0] : action;
}

type CsvIssue = {
  row: number | null;
  institutionalId: string;
  email: string;
  message: string;
};

function csvIssues(error: unknown): CsvIssue[] {
  if (!(error instanceof CompassApiError)) return [];
  const body = error.body;
  if (!body || typeof body !== "object" || !("error" in body)) return [];
  const detail = body.error;
  if (
    !detail ||
    typeof detail !== "object" ||
    !("details" in detail) ||
    !Array.isArray(detail.details)
  )
    return [];
  const rawIssues: unknown[] = detail.details;
  return rawIssues.flatMap((issue): CsvIssue[] => {
    if (
      !issue ||
      typeof issue !== "object" ||
      !("message" in issue) ||
      typeof issue.message !== "string"
    )
      return [];
    return [
      {
        row:
          "row_number" in issue && typeof issue.row_number === "number"
            ? issue.row_number
            : null,
        institutionalId:
          "institutional_id" in issue &&
          typeof issue.institutional_id === "string"
            ? issue.institutional_id
            : "",
        email:
          "email" in issue && typeof issue.email === "string"
            ? issue.email
            : "",
        message: issue.message,
      },
    ];
  });
}

export function ImportAccounts() {
  const importCsv = useAccountsImportCsv();
  const invalidate = useInvalidateManagedAccount();
  const action = useManagedAction();
  const [file, setFile] = useState<File | null>(null);
  const [reviewedFile, setReviewedFile] = useState<File | null>(null);
  const [report, setReport] = useState<CsvImportResponse | null>(null);
  const [conflict, setConflict] = useState(false);
  const [issues, setIssues] = useState<CsvIssue[]>([]);
  const [commitReview, setCommitReview] = useState<{
    file: File;
    report: CsvImportResponse;
  } | null>(null);
  const readyToCommit = Boolean(
    file &&
      reviewedFile === file &&
      report?.valid &&
      !report.committed &&
      !conflict &&
      report.create_count > 0,
  );

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
      (error) => setIssues(csvIssues(error)),
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
      "The CSV import could not be completed.",
      () => setCommitReview(null),
      (error) => {
        setConflict(true);
        setIssues(csvIssues(error));
      },
      () => setCommitReview(reviewed),
    );
    if (!response) return;
    setCommitReview(null);
    setReport(response.data);
    await invalidate();
    action.setNotice(
      "CSV import completed. Review the committed result below.",
    );
  }

  return (
    <section aria-labelledby="import-accounts-heading">
      <PageHeader
        title="Import accounts"
        headingId="import-accounts-heading"
        back={
          <Link href="/portal/accounts" className={pageBackLinkClass}>
            Back to Accounts
          </Link>
        }
        description="CSV import provisions new accounts. It does not update existing account identity, roles, or status. Exact matching active accounts are skipped; conflicting records are reported."
      />
      <Panel as="div">
        <PanelBody className="py-5">
        <p className="text-sm text-muted">
          Required columns: institutional_id, email, first_name, last_name,
          role. Optional: middle_name, suffix. Limit: about 1 MiB and 1,000
          non-empty rows.
        </p>
        <a
          download="compass-account-import.csv"
          href={`data:text/csv;charset=utf-8,${encodeURIComponent(template)}`}
          className="mt-3 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          Download headers-only template
        </a>
        <div className="mt-5 grid max-w-lg gap-1.5">
          <Label htmlFor="account-csv-file">CSV file</Label>
          <input
            id="account-csv-file"
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
        <ManagedActionFeedback action={action} showMessages={!commitReview} />
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
            aria-label="CSV row issues"
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
                    Email
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Issue
                  </th>
                </tr>
              </thead>
              <tbody className={dataTable.body}>
                {issues.map((issue, index) => (
                  <tr
                    key={`${issue.row ?? index}-${index}`}
                    className={dataTable.row}
                  >
                    <td className={dataTable.cell}>{issue.row ?? "—"}</td>
                    <td className={dataTable.cell}>
                      {issue.institutionalId || "—"}
                    </td>
                    <td className={dataTable.cell}>{issue.email || "—"}</td>
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
        <Panel className="mt-5 overflow-hidden" aria-labelledby="csv-report-heading">
          <PanelHeader
            title={report.committed ? "Import result" : "Validation report"}
            titleId="csv-report-heading"
            description={
              report.valid
                ? report.committed
                  ? "The import was completed."
                  : "The CSV is valid for import. Records may change before commit."
                : "Resolve the conflicts or invalid rows, then validate the CSV again."
            }
          />
          <dl className="grid grid-cols-2 gap-px border-b border-brand-line bg-border text-sm sm:grid-cols-5">
            {[
              ["Total rows", report.total_rows],
              ["Create", report.create_count],
              ["Skip", report.skip_count],
              ["Conflict", report.conflict_count],
              ["Invalid", report.invalid_count],
            ].map(([label, value]) => (
              <div key={label} className="bg-surface-raised px-4 py-3 last:odd:col-span-2 sm:px-5 sm:last:odd:col-span-1">
                <dt className="text-muted">{label}</dt>
                <dd className="mt-1 font-heading text-xl font-semibold tabular-nums text-ink">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          <div className={dataTable.scroll}>
            <table className={`${dataTable.table} min-w-[42rem]`}>
              <caption className="sr-only">CSV rows</caption>
              <thead className={dataTable.head}>
                <tr>
                  <th scope="col" className={dataTable.headerCell}>
                    Row
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Institutional ID
                  </th>
                  <th scope="col" className={dataTable.headerCell}>
                    Email
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
                    <td className={dataTable.cell}>{row.institutional_id || "—"}</td>
                    <td className={dataTable.cell}>{row.email || "—"}</td>
                    <td className={`${dataTable.cell} font-semibold`}>
                      {rowActionLabel(row.action, report.committed)}
                    </td>
                    <td className={dataTable.cell}>{row.message || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {readyToCommit ? (
            <PanelFooter>
              <Button
                disabled={importCsv.isPending}
                onClick={openCommitReview}
              >
                Import accounts
              </Button>
            </PanelFooter>
          ) : null}
        </Panel>
      ) : null}
      <ConsequentialActionDialog
        open={commitReview !== null}
        title={
          commitReview
            ? `Import ${commitReview.report.create_count} ${commitReview.report.create_count === 1 ? "account" : "accounts"}?`
            : "Import accounts?"
        }
        confirmLabel={
          commitReview
            ? `Import ${commitReview.report.create_count} ${commitReview.report.create_count === 1 ? "account" : "accounts"}`
            : "Import accounts"
        }
        pendingLabel="Importing accounts…"
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
              {commitReview.report.create_count} new active {commitReview.report.create_count === 1 ? "account" : "accounts"} will be created.
              {" "}
              {commitReview.report.skip_count} exact existing {commitReview.report.skip_count === 1 ? "account" : "accounts"} will be skipped.
            </p>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {[
                ["Create", commitReview.report.create_count],
                ["Skip", commitReview.report.skip_count],
                ["Conflict", commitReview.report.conflict_count],
                ["Invalid", commitReview.report.invalid_count],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt className="text-muted">{label}</dt>
                  <dd className="font-semibold text-ink">{value}</dd>
                </div>
              ))}
            </dl>
            <p>The import will use the CSV that produced this validation report. Server checks remain authoritative at commit time.</p>
          </>
        ) : null}
      </ConsequentialActionDialog>
    </section>
  );
}
