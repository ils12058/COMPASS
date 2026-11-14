"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { dataTable } from "@/components/ui/data-table";
import { Label } from "@/components/ui/label";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";
import type { RosterIssue } from "@/features/student-academics/roster-import/roster-import-presentation";

export const importBasePath = "/portal/organization/student-academics/import";

const tabs = [
  { href: importBasePath, label: "College placement" },
  { href: `${importBasePath}/terms`, label: "Term records" },
  { href: `${importBasePath}/graduations`, label: "Graduations" },
];

/** The three academic imports share one place; each tab is its own page and its own CSV. */
export function AcademicImportTabs() {
  const pathname = usePathname();
  return (
    <WorkspaceTabs label="Academic import navigation">
      {tabs.map((tab) => {
        const current = pathname === tab.href;
        return (
          <Link key={tab.href} href={tab.href} aria-current={current ? "page" : undefined} className={workspaceTabClass(current)}>
            {tab.label}
          </Link>
        );
      })}
    </WorkspaceTabs>
  );
}

export function CsvTemplateLink({ fileName, template }: { fileName: string; template: string }) {
  return (
    <a
      download={fileName}
      href={`data:text/csv;charset=utf-8,${encodeURIComponent(template)}`}
      className="inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
    >
      Download CSV template
    </a>
  );
}

export function CsvFileField({ id, onChange }: { id: string; onChange: (file: File | null) => void }) {
  return (
    <div className="grid max-w-lg gap-1.5">
      <Label htmlFor={id}>CSV file</Label>
      <input
        id={id}
        className="block w-full text-sm text-ink file:mr-4 file:rounded-md file:border file:border-border file:bg-surface-raised file:px-3 file:py-2 file:text-sm file:font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        type="file"
        accept=".csv,text/csv"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
    </div>
  );
}

export function ImportCounts({ items }: { items: Array<[string, number]> }) {
  return (
    <dl className="grid grid-cols-2 gap-px border-b border-brand-line bg-border text-sm sm:grid-cols-5">
      {items.map(([label, value]) => (
        <div key={label} className="bg-surface-raised px-4 py-3 last:odd:col-span-2 sm:px-5 sm:last:odd:col-span-1">
          <dt className="text-muted">{label}</dt>
          <dd className="mt-1 font-heading text-xl font-semibold tabular-nums text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ImportIssuesTable({ issues, label }: { issues: RosterIssue[]; label: string }) {
  if (!issues.length) return null;
  return (
    <div className={`${dataTable.scroll} border-t border-brand-line`} role="region" aria-label={label}>
      <table className={`${dataTable.table} min-w-[36rem]`}>
        <thead className={dataTable.head}>
          <tr>
            <th scope="col" className={dataTable.headerCell}>Row</th>
            <th scope="col" className={dataTable.headerCell}>Institutional ID</th>
            <th scope="col" className={dataTable.headerCell}>Issue</th>
          </tr>
        </thead>
        <tbody className={dataTable.body}>
          {issues.map((issue, index) => (
            <tr key={`${issue.row ?? index}-${index}`} className={dataTable.row}>
              <td className={dataTable.cell}>{issue.row ?? "—"}</td>
              <td className={dataTable.cell}>{issue.institutionalId || "—"}</td>
              <td className={dataTable.cell}>{issue.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One preview row table; each import supplies its own columns. */
export function ImportRowsTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
}: {
  caption: string;
  columns: Array<{ header: string; cell: (row: Row) => ReactNode; strong?: boolean }>;
  rows: Row[];
  rowKey: (row: Row) => string;
}) {
  return (
    <div className={dataTable.scroll}>
      <table className={`${dataTable.table} min-w-[56rem]`}>
        <caption className="sr-only">{caption}</caption>
        <thead className={dataTable.head}>
          <tr>
            {columns.map((column) => (
              <th key={column.header} scope="col" className={dataTable.headerCell}>{column.header}</th>
            ))}
          </tr>
        </thead>
        <tbody className={dataTable.body}>
          {rows.map((row) => (
            <tr key={rowKey(row)} className={dataTable.row}>
              {columns.map((column) => (
                <td key={column.header} className={column.strong ? `${dataTable.cell} font-semibold` : dataTable.cell}>
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
