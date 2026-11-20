"use client";

import { useId, useState } from "react";
import type { ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { dataTable } from "@/components/ui/data-table";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  csvProblemMessage,
  csvRowLabel,
  problemRowsCsv,
  readyRowNumbers,
  rowStatus,
  selectionCountLabel,
  toggleRow,
} from "@/features/csv-import/csv-selection";
import type { CsvPreviewRow, CsvStatusFilter } from "@/features/csv-import/csv-selection";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";

const PAGE_SIZE = 50;

export function CsvPreviewTable<Row extends CsvPreviewRow>({
  caption,
  columns,
  rows,
  headers,
  selected,
  onSelectionChange,
  committed,
  total,
  disabled = false,
  problemDownload,
}: {
  caption: string;
  columns: Array<{ header: string; cell: (row: Row) => ReactNode; strong?: boolean }>;
  rows: Row[];
  headers: string[];
  selected: number[];
  onSelectionChange: (rows: number[]) => void;
  committed: boolean;
  total: number;
  disabled?: boolean;
  problemDownload?: string | null;
}) {
  const id = useId();
  const [filter, setFilter] = useState<CsvStatusFilter>("all");
  const [page, setPage] = useState(1);
  const filtered = rows.filter((row) => filter === "all" || rowStatus(row) === filter);
  const currentPage = Math.min(page, Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
  const visible = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const download = problemDownload ?? (
    rows.some((row) => rowStatus(row) === "problems") ? problemRowsCsv(headers, rows) : null
  );

  return (
    <>
      <div className="flex min-w-0 flex-wrap items-end gap-3 border-b border-brand-line px-4 py-3 sm:px-5">
        {!committed ? (
          <>
            <Button
              variant="secondary"
              disabled={disabled}
              onClick={() => onSelectionChange(readyRowNumbers(rows))}
            >
              Select all ready
            </Button>
            <Button
              variant="quiet"
              disabled={disabled || !selected.length}
              onClick={() => onSelectionChange([])}
            >
              Clear selection
            </Button>
          </>
        ) : null}
        <div className="grid min-w-0 gap-1.5">
          <Label htmlFor={`${id}-status`}>Status</Label>
          <Select
            id={`${id}-status`}
            value={filter}
            onChange={(event) => {
              const next = event.target.value;
              if (next === "all" || next === "ready" || next === "exists" || next === "problems") {
                setFilter(next);
                setPage(1);
              }
            }}
          >
            <option value="all">All</option>
            <option value="ready">Ready</option>
            <option value="exists">Already exists</option>
            <option value="problems">Has problems</option>
          </Select>
        </div>
        {download ? (
          <a
            download="compass-rows-with-problems.csv"
            href={`data:text/csv;charset=utf-8,${encodeURIComponent(download)}`}
            className={`${buttonVariants({ variant: "secondary" })} whitespace-normal text-center`}
          >
            Download rows with problems
          </a>
        ) : null}
        {!committed ? (
          <p role="status" className="basis-full text-sm font-semibold text-ink">
            {selectionCountLabel(selected.length, total)}
          </p>
        ) : null}
      </div>
      <div
        className={`${dataTable.scroll} max-w-full`}
        role="region"
        aria-label={caption}
        tabIndex={0}
      >
        <table className={`${dataTable.table} min-w-[48rem]`}>
          <caption className="sr-only">{caption}</caption>
          <thead className={dataTable.head}>
            <tr>
              <th scope="col" className={dataTable.headerCell}>Select</th>
              {columns.map((column) => (
                <th key={column.header} scope="col" className={dataTable.headerCell}>
                  {column.header}
                </th>
              ))}
              <th scope="col" className={dataTable.headerCell}>Status</th>
              <th scope="col" className={dataTable.headerCell}>Note</th>
            </tr>
          </thead>
          <tbody className={dataTable.body}>
            {visible.map((row) => {
              const status = rowStatus(row);
              const noteId = `${id}-row-${row.row_number}-note`;
              return (
                <tr key={row.row_number} className={dataTable.row}>
                  <td className={dataTable.cell}>
                    <label className="flex min-h-11 min-w-11 items-center justify-center">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                        checked={selected.includes(row.row_number)}
                        disabled={disabled || committed || status === "problems"}
                        aria-describedby={noteId}
                        onChange={() => onSelectionChange(toggleRow(rows, selected, row.row_number))}
                      />
                      <span className="sr-only">Select row {row.row_number}</span>
                    </label>
                  </td>
                  {columns.map((column) => (
                    <td
                      key={column.header}
                      className={column.strong ? `${dataTable.cell} font-semibold` : dataTable.cell}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                  <td className={`${dataTable.cell} font-semibold`}>
                    {csvRowLabel(row, committed)}
                  </td>
                  <td id={noteId} className={dataTable.cell}>
                    {csvProblemMessage(row.message) || "—"}
                  </td>
                </tr>
              );
            })}
            {!visible.length ? (
              <tr>
                <td colSpan={columns.length + 3} className={dataTable.cell}>
                  No rows match this status.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <CanonicalPagination
        page={currentPage}
        hasNext={currentPage * PAGE_SIZE < filtered.length}
        onPageChange={setPage}
        label={`${caption} pages`}
        className="px-4 sm:px-5"
      />
    </>
  );
}
