"use client";

import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils/cn";

export type SortOption<T extends string> = { value: T; label: string };

// A collection's one Sort control (ADR-090). It sits with the results it orders, on every screen
// size, and reads and writes the same URL ordering as the collection's sortable table headers.
// Sorting is a view preference, not a filter: it never counts toward the Filters badge and
// Clear filters leaves it alone.
//
// `value` is the ordering the results were returned in. Until the first page arrives it is
// unknown, so the control waits rather than guessing the backend's default.
export function SortField<T extends string>({
  id,
  value,
  options,
  onChange,
  disabled = false,
  className,
}: {
  id: string;
  value: T | undefined;
  options: readonly SortOption<T>[];
  onChange: (next: T) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 items-center gap-2", className)}>
      <Label htmlFor={id} className="shrink-0 text-muted">
        Sort
      </Label>
      <Select
        id={id}
        value={value ?? ""}
        disabled={disabled || value === undefined}
        onChange={(event) => {
          const next = options.find((option) => option.value === event.target.value);
          if (next && next.value !== value) onChange(next.value);
        }}
        className="w-auto min-w-0 max-w-full"
      >
        {value === undefined ? <option value="">Loading…</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
    </div>
  );
}
