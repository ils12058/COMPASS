"use client";

import Link from "next/link";
import { ChangeEvent, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, FileSpreadsheet, Upload } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { getApiErrorMessage } from "@/features/auth/utils/errors";
import {
  AccountActionMessage,
  AccountSection,
  accountAdminError,
} from "@/features/portal/admin/accounts/portal-it-admin-account-shared";
import { formatAdminLabel } from "@/features/portal/admin/portal-it-admin-shared";
import {
  getAccountsListQueryKey,
  useAccountsImportCsv,
} from "@/lib/api/generated/accounts/accounts";
import type {
  CsvImportResponse,
  CsvImportRowResponse,
} from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/client";

const MAX_CSV_BYTES = 1_048_576;
const CSV_HEADER = "institutional_id,email,first_name,last_name,role,middle_name,suffix";

function getImportErrorDetails(error: unknown) {
  if (!(error instanceof CompassApiError)) {
    return [];
  }

  const payload = error.data as {
    error?: { details?: unknown };
  } | null;
  const details = payload?.error?.details;

  if (!Array.isArray(details)) {
    return [];
  }

  return details.flatMap((item) => {
    if (!item || typeof item !== "object" || !("message" in item)) {
      return [];
    }

    const message = item.message;
    return typeof message === "string" ? [message] : [];
  });
}

function actionVariant(action: string) {
  switch (action) {
    case "CREATE":
      return "secondary" as const;
    case "SKIP":
      return "outline" as const;
    case "CONFLICT":
    case "INVALID":
      return "destructive" as const;
    default:
      return "outline" as const;
  }
}

function ImportSummary({ report }: { report: CsvImportResponse }) {
  const metrics = [
    ["Rows", report.total_rows],
    ["Create", report.create_count],
    ["Skip", report.skip_count],
    ["Conflict", report.conflict_count],
    ["Invalid", report.invalid_count],
  ] as const;

  return (
    <div className="grid gap-3 sm:grid-cols-5">
      {metrics.map(([label, value]) => (
        <div key={label} className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
          <p className="mt-2 font-heading text-2xl font-bold">{value}</p>
        </div>
      ))}
    </div>
  );
}

function ImportRows({ rows }: { rows: CsvImportRowResponse[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-[var(--compass-border)]">
      <table className="w-full min-w-[48rem] text-left text-sm">
        <caption className="sr-only">CSV account import results</caption>
        <thead className="bg-[var(--compass-surface-subtle)] text-xs uppercase tracking-[0.12em] text-muted-foreground">
          <tr>
            <th className="px-4 py-3 font-bold">Row</th>
            <th className="px-4 py-3 font-bold">Institutional ID</th>
            <th className="px-4 py-3 font-bold">Email</th>
            <th className="px-4 py-3 font-bold">Action</th>
            <th className="px-4 py-3 font-bold">Details</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.row_number}-${row.email}-${row.institutional_id}`} className="border-t border-[var(--compass-border)] align-top">
              <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{row.row_number}</td>
              <td className="px-4 py-3 font-medium">{row.institutional_id || "—"}</td>
              <td className="px-4 py-3">{row.email || "—"}</td>
              <td className="px-4 py-3">
                <Badge variant={actionVariant(row.action)}>{formatAdminLabel(row.action)}</Badge>
              </td>
              <td className="max-w-72 px-4 py-3 leading-6 text-muted-foreground">{row.message || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function downloadTemplate() {
  const blob = new Blob([`${CSV_HEADER}\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "compass-account-import-template.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

export function PortalItAdminAccountImportPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<CsvImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorDetails, setErrorDetails] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const importCsv = useAccountsImportCsv();

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] ?? null;
    event.target.value = "";
    setError(null);
    setErrorDetails([]);
    setMessage(null);
    setReport(null);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    if (selectedFile.size > MAX_CSV_BYTES) {
      setFile(null);
      setError("This CSV is larger than the 1 MiB import limit.");
      return;
    }

    setFile(selectedFile);
  }

  async function validateFile() {
    if (!file) {
      setError("Choose a CSV file first.");
      return;
    }

    setError(null);
    setErrorDetails([]);
    setMessage(null);

    try {
      const response = await importCsv.mutateAsync({
        data: { file },
        params: { dry_run: true },
      });
      setReport(response.data);
      setMessage(
        response.data.valid
          ? "Validation passed. Review the row results before committing the import."
          : "The file needs attention before it can be committed.",
      );
    } catch (caught) {
      setError(getApiErrorMessage(caught) ?? accountAdminError(caught, "We couldn’t validate this CSV. Please review the file and try again."));
      setErrorDetails(getImportErrorDetails(caught));
    }
  }

  async function commitFile() {
    if (!file || !report?.valid || report.committed) {
      return;
    }

    setError(null);
    setErrorDetails([]);
    setMessage(null);

    try {
      const response = await importCsv.mutateAsync({
        data: { file },
        params: { dry_run: false },
      });
      setReport(response.data);
      if (response.data.committed) {
        await queryClient.invalidateQueries({ queryKey: getAccountsListQueryKey() });
        setMessage("The account import was committed successfully.");
      } else {
        setMessage("The import was not committed. Review the row results before trying again.");
      }
    } catch (caught) {
      setError(getApiErrorMessage(caught) ?? accountAdminError(caught, "We couldn’t commit this CSV. The account directory was not changed by this request."));
      setErrorDetails(getImportErrorDetails(caught));
    }
  }

  const busy = importCsv.isPending;

  return (
    <div className="space-y-5">
      <Button asChild type="button" variant="ghost" className="-ml-2">
        <Link href="/portal/admin/accounts">
          <ArrowLeft aria-hidden="true" />
          Back to accounts
        </Link>
      </Button>

      <AccountSection
        icon={FileSpreadsheet}
        title="Import accounts"
        description="Validate a bounded CSV first, then commit it only after the row results are ready."
      >
        <div className="space-y-5">
          <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 text-sm leading-6 text-muted-foreground">
            <p className="font-semibold text-foreground">CSV columns</p>
            <p className="mt-1">Required: <code className="rounded bg-card px-1.5 py-0.5 text-xs text-foreground">institutional_id,email,first_name,last_name,role</code></p>
            <p className="mt-1">Optional: <code className="rounded bg-card px-1.5 py-0.5 text-xs text-foreground">middle_name,suffix</code></p>
            <p className="mt-2">The import does not set passwords, designations, MFA, verification state, or account status. Files are limited to 1 MiB and 1,000 nonblank rows.</p>
            <Button type="button" variant="link" className="mt-2 h-auto p-0" onClick={downloadTemplate}>
              Download a blank CSV template
            </Button>
          </div>

          <div className="rounded-2xl border border-dashed border-[var(--compass-border-strong)] p-5">
            <label htmlFor="account-csv-file" className="flex cursor-pointer flex-col items-center justify-center text-center">
              <span className="flex size-12 items-center justify-center rounded-2xl bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)]">
                <Upload aria-hidden="true" className="size-6" />
              </span>
              <span className="mt-3 font-semibold">Choose a CSV file</span>
              <span className="mt-1 text-sm text-muted-foreground">UTF-8 CSV up to 1 MiB</span>
              <input id="account-csv-file" type="file" accept=".csv,text/csv" className="sr-only" onChange={handleFileChange} />
            </label>
            {file ? (
              <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{file.name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{Math.ceil(file.size / 1024)} KiB</p>
                </div>
                <Button type="button" variant="outline" disabled={busy} onClick={() => void validateFile()}>
                  {busy ? "Validating…" : "Validate CSV"}
                </Button>
              </div>
            ) : null}
          </div>

          <Alert className="border-[var(--compass-brand-gold)]/40">
            <CheckCircle2 aria-hidden="true" />
            <AlertDescription>
              Both validation and commit require a recent MFA check. Commit revalidates the file on the server before any accounts are created.
            </AlertDescription>
          </Alert>

          <AccountActionMessage error={error} message={message} />
          {errorDetails.length ? (
            <ul className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm leading-6 text-destructive">
              {errorDetails.map((detail, index) => <li key={`${detail}-${index}`}>{detail}</li>)}
            </ul>
          ) : null}
        </div>
      </AccountSection>

      {report ? (
        <AccountSection
          icon={CheckCircle2}
          title={report.committed ? "Import complete" : "Validation results"}
          description={report.committed ? "The server committed the validated account batch." : "Review each row before committing this file."}
        >
          <ImportSummary report={report} />
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Badge variant={report.valid ? "secondary" : "destructive"}>
              {report.valid ? (report.committed ? "Committed" : "Ready to commit") : "Needs attention"}
            </Badge>
            {!report.committed ? (
              <Button type="button" disabled={!file || !report.valid || busy} onClick={() => void commitFile()}>
                {busy ? "Committing…" : "Commit import"}
              </Button>
            ) : null}
          </div>
          <div className="mt-5">
            <ImportRows rows={report.rows} />
          </div>
        </AccountSection>
      ) : null}
    </div>
  );
}
