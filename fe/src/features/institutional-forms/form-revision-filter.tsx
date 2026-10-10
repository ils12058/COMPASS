"use client";

import { useState, type SelectHTMLAttributes } from "react";

import { FilterField } from "@/components/ui/filter-toolbar";
import { Select } from "@/components/ui/select";
import type { FormRevisionFilterOption } from "@/lib/api/generated/model";

export function revisionFilterLabel(revision: FormRevisionFilterOption): string {
  const code = revision.official_code?.trim();
  const number = revision.official_revision?.trim();
  if (code && number) return `${code} · Rev. ${number}`;
  if (code) return code;
  if (number) return `Rev. ${number}`;
  return "Form Revision";
}

// Keep an applied UUID in the control while metadata is loading or unavailable. It is
// still submitted; a temporary metadata failure never clears historical list state.
export function FormRevisionFilter({
  id,
  selectedId,
  options = [],
  value,
  defaultValue,
  onChange,
  ...selectProps
}: {
  id: string;
  selectedId: string;
  options?: FormRevisionFilterOption[];
} & Omit<SelectHTMLAttributes<HTMLSelectElement>, "id" | "children">) {
  const [draftId, setDraftId] = useState(defaultValue ?? selectedId);
  const currentId = value ?? draftId;
  const unresolved = currentId && !options.some((revision) => revision.id === currentId);
  return (
    <FilterField label="Form Revision" htmlFor={id}>
      <Select id={id} name="form_revision_id" {...selectProps} value={currentId} onChange={(event) => {
        setDraftId(event.target.value);
        onChange?.(event);
      }}>
        <option value="">All revisions</option>
        {unresolved ? <option value={currentId}>Selected revision</option> : null}
        {options.map((revision) => (
          <option key={revision.id} value={revision.id}>{revisionFilterLabel(revision)}</option>
        ))}
      </Select>
    </FilterField>
  );
}
