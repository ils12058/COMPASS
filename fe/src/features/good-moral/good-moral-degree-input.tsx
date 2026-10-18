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
  required = true,
  label = "Degree",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  required?: boolean;
  label?: ReactNode;
}) {
  const options = useGoodMoralListDegreeOptions({ query: { retry: false, staleTime: 5 * 60_000 } });
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
        list={listId}
        aria-describedby={helpId}
        disabled={disabled}
      />
      <datalist id={listId}>
        {items.map((degree) => <option key={degree} value={degree} />)}
      </datalist>
      <p id={helpId} className="mt-1 text-xs text-muted">
        {options.isPending
          ? "Loading current UCN Bachelor's Program suggestions…"
          : options.isError
            ? "Suggestions are unavailable. Enter the completed UCN Bachelor's degree as recorded."
            : items.length === 0
              ? "No current suggestions are available. Enter the completed UCN Bachelor's degree as recorded."
              : "Choose a current UCN Bachelor's Program or type a historical degree name that is no longer listed. Suggestions do not verify graduation."}
      </p>
    </div>
  );
}
