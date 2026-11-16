"use client";

import type { ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGoodMoralListDegreeOptions } from "@/lib/api/generated/good-moral/good-moral";

export function GoodMoralDegreeInput({
  id,
  value,
  onChange,
  disabled = false,
  readOnly = false,
  required = true,
  label = "Degree",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  readOnly?: boolean;
  required?: boolean;
  label?: ReactNode;
}) {
  const options = useGoodMoralListDegreeOptions({ query: { enabled: !readOnly, retry: false, staleTime: 5 * 60_000 } });
  const items = options.data?.data.items ?? [];
  const helpId = `${id}-help`;
  const listId = `${id}-suggestions`;

  return (
    <div>
      <Label htmlFor={id}>
        {label} {required ? <span aria-hidden="true">*</span> : null}
      </Label>
      <Input
        id={id}
        className="mt-2"
        required={required}
        maxLength={255}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        list={readOnly ? undefined : listId}
        aria-describedby={readOnly ? undefined : helpId}
        disabled={disabled}
        readOnly={readOnly}
      />
      <datalist id={listId}>
        {items.map((degree) => <option key={degree} value={degree} />)}
      </datalist>
      {!readOnly ? <p id={helpId} className="mt-1 text-xs text-muted">
        {options.isPending
          ? "Loading degree suggestions…"
          : options.isError
            ? "Suggestions aren't available. Enter the degree as recorded."
            : items.length === 0
              ? "Enter the degree as recorded."
              : "Choose a current program or enter an older degree name."}
      </p> : null}
    </div>
  );
}
