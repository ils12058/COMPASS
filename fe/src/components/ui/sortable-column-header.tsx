"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { cn } from "@/lib/utils/cn";

type SortDirection = "ascending" | "descending";

type ColumnOrderings<T extends string> =
  | { ascending: T; ascendingLabel: string; descending?: T; descendingLabel?: string }
  | { ascending?: undefined; ascendingLabel?: undefined; descending: T; descendingLabel: string };

// A table column header whose button changes the collection's URL ordering (ADR-090). Only
// columns that are a real way to read the records are sortable; the rest keep a plain <th>.
//
// The column owns one or two values of the collection's closed ordering enum: `ascending` (A–Z,
// oldest or earliest first) and `descending` (Z–A, newest or latest first). The header reports
// the applied ordering through `aria-sort`, shows it with an arrow (never by color alone), and its
// button names the current order and the order a press applies. A first press uses
// `firstDirection`; another press reverses a two-way column.
export function SortableColumnHeader<T extends string>({
  label,
  firstDirection = "ascending",
  current,
  onSort,
  disabled = false,
  className,
  ...orderings
}: ColumnOrderings<T> & {
  label: string;
  firstDirection?: SortDirection;
  current: T | undefined;
  onSort: (next: T) => void;
  disabled?: boolean;
  className?: string;
}) {
  const { ascending, descending } = orderings;
  // The types guarantee at least one value; this narrows it for the fallbacks below.
  const either = ascending ?? descending;
  if (either === undefined) return <th scope="col" className={className}>{label}</th>;
  const direction: SortDirection | null =
    ascending !== undefined && current === ascending
      ? "ascending"
      : descending !== undefined && current === descending
        ? "descending"
        : null;
  const preferred = (wanted: SortDirection): T =>
    wanted === "ascending" ? ascending ?? either : descending ?? either;
  const next =
    direction === "ascending"
      ? preferred("descending")
      : direction === "descending"
        ? preferred("ascending")
        : preferred(firstDirection);
  const labelFor = (value: T) =>
    value === ascending ? orderings.ascendingLabel ?? "" : orderings.descendingLabel ?? "";
  const Icon = direction === "ascending" ? ArrowUp : direction === "descending" ? ArrowDown : ArrowUpDown;
  const pressable = !disabled && next !== current;

  return (
    <th scope="col" aria-sort={direction ?? undefined} className={className}>
      <button
        type="button"
        disabled={!pressable}
        onClick={() => onSort(next)}
        // The negative margins keep the label on the same line as plain headers while the padding
        // keeps a 24px target.
        className="relative -mx-1 -my-1 inline-flex items-center gap-1.5 rounded-sm px-1 py-1 text-left font-semibold uppercase tracking-wide text-inherit hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:cursor-default disabled:hover:text-inherit"
      >
        <span>{label}</span>
        <Icon
          aria-hidden="true"
          size={14}
          className={cn("shrink-0", direction === null && "opacity-60")}
        />
        <span className="sr-only">
          {direction ? `, sorted ${labelFor(preferred(direction)).toLowerCase()}` : ""}
          {pressable ? `. Sort ${labelFor(next).toLowerCase()}` : ""}
        </span>
      </button>
    </th>
  );
}
