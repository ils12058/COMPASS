import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CsvPreviewTable } from "../src/features/csv-import/csv-preview-table.tsx";
import {
  csvProblemMessage, problemRowsCsv, readyRowNumbers, rowStatus,
  selectionCountLabel, selectionSummary, toggleRow,
} from "../src/features/csv-import/csv-selection.ts";
import { batchCommitReady } from "../src/features/student-academics/roster-import/batch-import-presentation.ts";

const row = (row_number, action, values = [String(row_number)], message = "") => ({
  row_number, action, institutional_id: `UCN-${row_number}`, email: "fixture@example.test", values, message,
});
const rows = [row(2, "CREATE"), row(3, "SKIP"), row(4, "INVALID", ["bad"], "email is invalid"), row(5, "CONFLICT", ["taken"], "existing account is disabled")];
const table = (items = rows, selected = readyRowNumbers(items)) => renderToStaticMarkup(createElement(CsvPreviewTable, {
  caption: "CSV rows", rows: items, headers: ["institutional_id"], total: items.length,
  selected, onSelectionChange: () => {}, committed: false,
  columns: [{ header: "Row", cell: (item) => item.row_number }],
}));

test("ready rows start checked, existing rows unchecked, and problem rows disabled with reasons", () => {
  assert.deepEqual(readyRowNumbers(rows), [2]);
  const html = table();
  const inputs = [...html.matchAll(/<input[^>]+>/g)].map(([input]) => input);
  assert.equal(inputs.length, 4);
  assert.match(inputs[0], /checked=""/);
  assert.doesNotMatch(inputs[1], /checked=""|disabled=""/);
  assert.match(inputs[2], /disabled=""/);
  assert.match(inputs[3], /disabled=""/);
  assert.match(html, /Select row 4/);
  assert.match(html, /email is invalid/);
  assert.match(html, /Already exists/);
  assert.match(html, /Select all ready/);
  assert.match(html, /Clear selection/);
  assert.match(html, /Import 1 of 4 rows/);
  for (const label of ["All", "Ready", "Already exists", "Has problems"]) assert.ok(html.includes(label));
});

test("selection changes the live count, cannot add invalid rows, and survives paging and filtering", () => {
  assert.deepEqual(toggleRow(rows, [2], 2), []);
  assert.deepEqual(toggleRow(rows, [], 2), [2]);
  assert.deepEqual(toggleRow(rows, [2], 4), [2]);
  assert.deepEqual(toggleRow(rows, [2], 5), [2]);
  assert.deepEqual(toggleRow(rows, [2], 999), [2]);
  assert.equal(selectionCountLabel(0, 300), "Import 0 of 300 rows");
  assert.equal(selectionSummary(rows, [2, 3]).write_count, 1);
  assert.equal(selectionSummary(rows, [2, 3]).skip_count, 1);
  assert.match(table(rows, []), /Import 0 of 4 rows/);
  const many = Array.from({ length: 300 }, (_, index) => row(index + 2, "CREATE"));
  const html = table(many);
  assert.equal([...html.matchAll(/<input[^>]+>/g)].length, 50, "only one page is rendered");
  assert.match(html, /CSV rows pages/);
  assert.match(html, /Import 300 of 300 rows/);
  assert.equal(many.filter((item) => rowStatus(item) === "ready").length, 300);
});

test("problem CSV preserves original optional columns, quotes, commas, newlines, empty fields and row order", () => {
  const columns = ["email", "first_name", "suffix", "role"];
  const items = [
    row(2, "CREATE", ["ok@example.test", "Good", "", "STUDENT"]),
    row(4, "INVALID", ["bad", 'Ann, "B"\nC', "", "STUDENT"], 'first_name is invalid, "check"'),
    row(5, "CONFLICT", ["taken@example.test", "Name", "Jr.", "STUDENT"], "existing account is disabled"),
  ];
  assert.equal(problemRowsCsv(columns, items),
    '"email","first_name","suffix","role","problem"\r\n' +
    '"bad","Ann, ""B""\nC","","STUDENT","First name is invalid, ""check"""\r\n' +
    '"taken@example.test","Name","Jr.","STUDENT","existing account is disabled"\r\n');
  assert.equal(problemRowsCsv(columns, [items[0]]), '"email","first_name","suffix","role","problem"\r\n');
});

test("all academic write actions are ready and graduation consequences count selected rows only", () => {
  const academic = [row(2, "SET"), row(3, "UPDATE"), row(4, "GRADUATE"), row(5, "NOOP"), row(6, "CONFLICT")];
  academic[2].current_placement_college_code = "CCMS";
  assert.deepEqual(readyRowNumbers(academic), [2, 3, 4]);
  assert.equal(selectionSummary(academic, [3]).placement_cleared_count, 0);
  assert.equal(selectionSummary(academic, [4]).placement_cleared_count, 1);
  const file = { name: "a.csv" };
  const options = { file, reviewed: { file, scope: "year" }, scope: "year", report: { valid: false, committed: false }, conflict: false, writes: 1, selectedRows: [2] };
  assert.equal(batchCommitReady(options), true, "unselected problems don't block ready rows");
  assert.equal(batchCommitReady({ ...options, writes: 0, selectedRows: [] }), false);
  assert.equal(batchCommitReady({ ...options, conflict: true }), false);
  assert.equal(batchCommitReady({ ...options, scope: "another-year" }), false);
  assert.equal(csvProblemMessage("the account does not have the STUDENT role"), "the account does not have the Student account role");
});

test("retry downloads replace the old problem column instead of duplicating it", () => {
  const retry = row(2, "INVALID", ["UCN-2", "old note", "bad"], "email is invalid");
  assert.equal(problemRowsCsv(["institutional_id", "problem", "email"], [retry]),
    '"institutional_id","email","problem"\r\n"UCN-2","bad","email is invalid"\r\n');
});

test("problem downloads remain available after selected rows were committed", () => {
  const download = problemRowsCsv(["institutional_id"], rows);
  const html = renderToStaticMarkup(createElement(CsvPreviewTable, {
    caption: "CSV rows", rows: [rows[0]], headers: ["institutional_id"], total: 4,
    selected: [2], onSelectionChange: () => {}, committed: true, problemDownload: download,
    columns: [{ header: "Row", cell: (item) => item.row_number }],
  }));
  assert.match(html, /Download rows with problems/);
  assert.match(html, /Created/);
  assert.doesNotMatch(html, /Select all ready/);
  assert.match(html, /disabled=""/);
});
