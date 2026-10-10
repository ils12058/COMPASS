"use client";

import type { ChangeEvent, ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export type FieldOption<T extends string> = readonly [T, string];

export function TextField({
  id,
  label,
  value,
  onChange,
  type = "text",
  required = false,
  readOnly = false,
  disabled = false,
  hint,
  error,
  min,
  max,
  step,
  maxLength,
  autoComplete,
}: {
  id: string;
  label: string;
  value: string | number | null | undefined;
  onChange: (value: string) => void;
  type?: "text" | "email" | "tel" | "date" | "number";
  required?: boolean;
  readOnly?: boolean;
  disabled?: boolean;
  hint?: string;
  error?: string;
  min?: number | string;
  max?: number | string;
  step?: number | "any";
  maxLength?: number;
  autoComplete?: string;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="min-w-0">
      <Label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </Label>
      <Input
        id={id}
        type={type}
        value={value ?? ""}
        readOnly={readOnly}
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        maxLength={maxLength}
        autoComplete={autoComplete}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
        className={readOnly ? "bg-surface-muted" : undefined}
      />
      {hint ? <p id={hintId} className="mt-1.5 text-xs leading-5 text-muted">{hint}</p> : null}
      {error ? <p id={errorId} role="alert" className="mt-1.5 text-xs leading-5 text-danger">{error}</p> : null}
    </div>
  );
}

export function TextAreaField({
  id,
  label,
  value,
  onChange,
  required = false,
  rows = 3,
  hint,
  error,
  maxLength,
}: {
  id: string;
  label: string;
  value: string | null | undefined;
  onChange: (value: string) => void;
  required?: boolean;
  rows?: number;
  hint?: string;
  error?: string;
  maxLength?: number;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="min-w-0">
      <Label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </Label>
      <Textarea
        id={id}
        rows={rows}
        value={value ?? ""}
        maxLength={maxLength}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? <p id={hintId} className="mt-1.5 text-xs leading-5 text-muted">{hint}</p> : null}
      {error ? <p id={errorId} role="alert" className="mt-1.5 text-xs leading-5 text-danger">{error}</p> : null}
    </div>
  );
}

export function SelectField<T extends string>({
  id,
  label,
  value,
  options,
  onChange,
  placeholder = "Select an option",
  required = false,
  hint,
  error,
}: {
  id: string;
  label: string;
  value: T | null | undefined;
  options: readonly FieldOption<T>[];
  onChange: (value: T | null) => void;
  placeholder?: string;
  required?: boolean;
  hint?: string;
  error?: string;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="min-w-0">
      <Label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </Label>
      <Select
        id={id}
        className="mt-2"
        value={value ?? ""}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        onChange={(event) => {
          const selected = options.find(([optionValue]) => optionValue === event.target.value);
          onChange(selected?.[0] ?? null);
        }}
      >
        <option value="">{placeholder}</option>
        {options.map(([optionValue, labelText]) => (
          <option key={optionValue} value={optionValue}>{labelText}</option>
        ))}
      </Select>
      {hint ? <p id={hintId} className="mt-1.5 text-xs leading-5 text-muted">{hint}</p> : null}
      {error ? <p id={errorId} role="alert" className="mt-1.5 text-xs leading-5 text-danger">{error}</p> : null}
    </div>
  );
}

export function CheckboxGroupField<T extends string>({
  id,
  legend,
  value,
  options,
  onChange,
  columns = 2,
  hint,
  required = false,
  error,
}: {
  id?: string;
  legend: string;
  value: readonly T[] | undefined;
  options: readonly FieldOption<T>[];
  onChange: (values: T[]) => void;
  columns?: 1 | 2 | 3;
  hint?: string;
  required?: boolean;
  error?: string;
}) {
  const values = value ?? [];
  const grid = columns === 1 ? "sm:grid-cols-1" : columns === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2";
  const hintId = id && hint ? `${id}-hint` : undefined;
  const errorId = id && error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <fieldset
      id={id}
      aria-required={required || undefined}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy}
    >
      <legend className="text-sm font-semibold text-ink">
        {legend}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </legend>
      {hint ? <p id={hintId} className="mt-1 text-xs leading-5 text-muted">{hint}</p> : null}
      <div className={`mt-3 grid gap-x-5 gap-y-3 ${grid}`}>
        {options.map(([optionValue, labelText]) => {
          const checked = values.includes(optionValue);
          return (
            <label key={optionValue} className="flex min-h-8 items-start gap-2.5 text-sm leading-5 text-ink">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 shrink-0 accent-brand"
                checked={checked}
                onChange={(event) => {
                  onChange(
                    event.target.checked
                      ? [...values, optionValue]
                      : values.filter((current) => current !== optionValue),
                  );
                }}
              />
              <span>{labelText}</span>
            </label>
          );
        })}
      </div>
      {error ? <p id={errorId} role="alert" className="mt-1.5 text-xs leading-5 text-danger">{error}</p> : null}
    </fieldset>
  );
}

export function BooleanField({
  id,
  legend,
  value,
  onChange,
  required = false,
  error,
}: {
  id?: string;
  legend: string;
  value: boolean | null | undefined;
  onChange: (value: boolean | null) => void;
  required?: boolean;
  error?: string;
}) {
  const choices = [
    { id: "yes", label: "Yes", value: true },
    { id: "no", label: "No", value: false },
    { id: "unanswered", label: "No response", value: null },
  ] as const;
  const errorId = id && error ? `${id}-error` : undefined;

  return (
    <fieldset
      id={id}
      role="radiogroup"
      aria-required={required || undefined}
      aria-invalid={error ? true : undefined}
      aria-describedby={errorId}
    >
      <legend className="text-sm font-semibold text-ink">
        {legend}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </legend>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-3">
        {choices.map((choice) => (
          <label key={choice.id} className="flex min-h-9 items-center gap-2.5 text-sm text-ink">
            <input
              type="radio"
              name={id ?? legend}
              className="h-4 w-4 accent-brand"
              checked={value === choice.value}
              onChange={() => onChange(choice.value)}
            />
            {choice.label}
          </label>
        ))}
      </div>
      {error ? <p id={errorId} role="alert" className="mt-1.5 text-xs leading-5 text-danger">{error}</p> : null}
    </fieldset>
  );
}

export function InlineHelp({ children }: { children: ReactNode }) {
  return <p className="text-xs leading-5 text-muted">{children}</p>;
}
