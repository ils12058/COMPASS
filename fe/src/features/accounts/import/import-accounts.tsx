"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
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
  const readyToCommit = Boolean(
    file &&
      reviewedFile === file &&
      report?.valid &&
      !report.committed &&
      !conflict,
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

  async function commit() {
    if (!file || !readyToCommit) return;
    const response = await action.run(
      () =>
        importCsv.mutateAsync({ data: { file }, params: { dry_run: false } }),
      "The CSV import could not be completed.",
      undefined,
      (error) => {
        setConflict(true);
        setIssues(csvIssues(error));
      },
    );
    if (!response) return;
    setReport(response.data);
    await invalidate();
    action.setNotice(
      "CSV import completed. Review the committed result below.",
    );
  }

  return (
    <section aria-labelledby="import-accounts-heading">
      <Link
        href="/portal/accounts"
        className="text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        ← Accounts
      </Link>
      <h1
        id="import-accounts-heading"
        className="mt-5 font-heading text-3xl font-bold text-ink"
      >
        Import accounts
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
        CSV import provisions new accounts. It does not update existing account
        identity, roles, or status. Exact matching active accounts are skipped;
        conflicting records are reported.
      </p>
      <div className="mt-7 border-y border-border py-6">
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
        <div className="mt-5 max-w-lg">
          <Label htmlFor="account-csv-file">CSV file</Label>
          <input
            id="account-csv-file"
            className="mt-2 block w-full text-sm text-ink file:mr-4 file:rounded-md file:border file:border-border file:bg-surface-raised file:px-3 file:py-2 file:text-sm file:font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setReport(null);
              setReviewedFile(null);
              setConflict(false);
              setIssues([]);
              action.setError(null);
              action.setNotice(null);
            }}
          />
        </div>
        <Button
          className="mt-5"
          disabled={!file || importCsv.isPending}
          onClick={() => void validate()}
        >
          {importCsv.isPending && !report ? "Validating CSV…" : "Validate CSV"}
        </Button>
        <ManagedActionFeedback action={action} />
        {conflict ? (
          <p role="status" className="mt-3 text-sm text-muted">
            Review the current CSV again before attempting another import.
          </p>
        ) : null}
        {issues.length ? (
          <div
            className="mt-5 overflow-x-auto border-y border-border"
            role="region"
            aria-label="CSV row issues"
          >
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-3 py-3">
                    Row
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Institutional ID
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Email
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Issue
                  </th>
                </tr>
              </thead>
              <tbody>
                {issues.map((issue, index) => (
                  <tr
                    key={`${issue.row ?? index}-${index}`}
                    className="border-t border-border"
                  >
                    <td className="px-3 py-3">{issue.row ?? "—"}</td>
                    <td className="px-3 py-3">
                      {issue.institutionalId || "—"}
                    </td>
                    <td className="px-3 py-3">{issue.email || "—"}</td>
                    <td className="px-3 py-3">{issue.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>

      {report ? (
        <section aria-labelledby="csv-report-heading" className="mt-8">
          <h2
            id="csv-report-heading"
            className="font-heading text-2xl font-semibold text-ink"
          >
            {report.committed ? "Import result" : "Validation report"}
          </h2>
          <p className="mt-2 text-sm text-muted">
            {report.valid
              ? report.committed
                ? "The import was completed."
                : "The CSV is valid for import. Records may change before commit."
              : "Resolve the conflicts or invalid rows, then validate the CSV again."}
          </p>
          <dl className="mt-6 grid grid-cols-2 gap-4 border-y border-border py-5 text-sm sm:grid-cols-5">
            {[
              ["Total rows", report.total_rows],
              ["Create", report.create_count],
              ["Skip", report.skip_count],
              ["Conflict", report.conflict_count],
              ["Invalid", report.invalid_count],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-muted">{label}</dt>
                <dd className="mt-1 font-heading text-xl font-semibold text-ink">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-5 overflow-x-auto border-y border-border">
            <table className="w-full min-w-[42rem] text-left text-sm">
              <thead className="bg-surface-subtle text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th scope="col" className="px-3 py-3">
                    Row
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Institutional ID
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Email
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Action
                  </th>
                  <th scope="col" className="px-3 py-3">
                    Message
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.rows.map((row) => (
                  <tr
                    key={`${row.row_number}-${row.institutional_id}`}
                    className="border-t border-border"
                  >
                    <td className="px-3 py-3">{row.row_number}</td>
                    <td className="px-3 py-3">{row.institutional_id || "—"}</td>
                    <td className="px-3 py-3">{row.email || "—"}</td>
                    <td className="px-3 py-3 font-semibold">
                      {rowActionLabel(row.action, report.committed)}
                    </td>
                    <td className="px-3 py-3">{row.message || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {readyToCommit ? (
            <div className="mt-6">
              <Button
                disabled={importCsv.isPending}
                onClick={() => void commit()}
              >
                {importCsv.isPending
                  ? "Importing accounts…"
                  : "Import accounts"}
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
