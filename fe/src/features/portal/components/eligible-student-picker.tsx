"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  CallSlipStudentOptionResponse,
  ReferralStudentOptionResponse,
} from "@/lib/api/generated/model";

export type EligibleStudentOption =
  | CallSlipStudentOptionResponse
  | ReferralStudentOptionResponse;

export function EligibleStudentPicker({
  search,
  onSearchChange,
  onSearch,
  items,
  selectedStudent,
  selectedId,
  onSelect,
  page,
  hasNext,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  onPageChange,
  label = "Student",
}: {
  search: string;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  items: EligibleStudentOption[];
  selectedStudent: EligibleStudentOption | null;
  selectedId: string | null;
  onSelect: (student: EligibleStudentOption) => void;
  page: number;
  hasNext: boolean;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string;
  onRetry: () => void;
  onPageChange: (page: number) => void;
  label?: string;
}) {
  return (
    <fieldset className="min-w-0" aria-busy={isLoading}>
      <legend className="text-sm font-semibold text-ink">{label}</legend>
      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          onSearch();
        }}
      >
        <div className="min-w-0 flex-1">
          <Label htmlFor="eligible-student-search">Search eligible Students</Label>
          <Input
            id="eligible-student-search"
            type="search"
            autoComplete="off"
            maxLength={160}
            placeholder="Search name or Institutional ID"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
        <Button className="self-end" variant="secondary" type="submit">
          Search
        </Button>
      </form>
      {selectedStudent ? (
        <p className="mt-3 border-l-2 border-brand pl-3 text-sm text-ink">
          Selected: <span className="font-semibold">{selectedStudent.display_name}</span>
          {selectedStudent.institutional_id ? ` · ${selectedStudent.institutional_id}` : ""}
        </p>
      ) : null}
      {isError ? (
        <div role="alert" className="mt-4 border-y border-danger/30 py-4">
          <p className="text-sm text-danger">{errorMessage}</p>
          <Button className="mt-3" variant="secondary" onClick={onRetry}>
            Retry Student search
          </Button>
        </div>
      ) : isLoading ? (
        <p role="status" className="mt-4 text-sm text-muted">Loading eligible Students…</p>
      ) : items.length === 0 ? (
        <p className="mt-4 border-y border-border py-4 text-sm text-muted">
          No eligible Students match this search.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border border-y border-border">
          {items.map((student) => (
            <li key={student.id} className="py-3">
              <label className="flex min-h-11 cursor-pointer items-start gap-3 text-sm text-ink">
                <input
                  className="mt-1 h-4 w-4 shrink-0 accent-brand"
                  type="radio"
                  name="eligible-student"
                  value={student.id}
                  checked={selectedId === student.id}
                  onChange={() => onSelect(student)}
                />
                <span className="min-w-0">
                  <span className="block font-semibold">{student.display_name}</span>
                  <span className="mt-1 block text-xs text-muted">
                    {student.institutional_id ? `Institutional ID ${student.institutional_id}` : "Institutional ID not available"}
                    {student.college ? ` · ${student.college.name}` : ""}
                  </span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {!isError && !isLoading && items.length > 0 ? (
        <nav aria-label="Eligible Student results" className="mt-3 flex items-center justify-between gap-3">
          <Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
            Previous
          </Button>
          <span className="text-sm text-muted">Page {page}</span>
          <Button variant="secondary" disabled={!hasNext} onClick={() => onPageChange(page + 1)}>
            Next
          </Button>
        </nav>
      ) : null}
    </fieldset>
  );
}
