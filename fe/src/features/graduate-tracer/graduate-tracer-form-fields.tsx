"use client";

import type { ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Choice } from "@/features/graduate-tracer/graduate-tracer-presentation";

export function FormField({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint ? <p id={`${id}-hint`} className="text-xs leading-5 text-muted">{hint}</p> : null}
    </div>
  );
}

export function TextField({
  id,
  label,
  value,
  onChange,
  type = "text",
  hint,
  inputMode,
  min,
  max,
  step,
}: {
  id: string;
  label: string;
  value: string | undefined;
  onChange: (value: string) => void;
  type?: string;
  hint?: string;
  inputMode?: "text" | "email" | "tel" | "numeric";
  min?: string | number;
  max?: string | number;
  step?: string | number;
}) {
  return (
    <FormField id={id} label={label} hint={hint}>
      <Input
        id={id}
        type={type}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        inputMode={inputMode}
        min={min}
        max={max}
        step={step}
        aria-describedby={hint ? `${id}-hint` : undefined}
      />
    </FormField>
  );
}

export function TextAreaField({
  id,
  label,
  value,
  onChange,
  hint,
}: {
  id: string;
  label: string;
  value: string | undefined;
  onChange: (value: string) => void;
  hint?: string;
}) {
  return (
    <FormField id={id} label={label} hint={hint}>
      <Textarea
        id={id}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        aria-describedby={hint ? `${id}-hint` : undefined}
      />
    </FormField>
  );
}

export function SelectField<T extends string>({
  id,
  label,
  value,
  options,
  onChange,
  placeholder = "Select an option",
}: {
  id: string;
  label: string;
  value: T | null | undefined;
  options: readonly Choice<T>[];
  onChange: (value: T | undefined) => void;
  placeholder?: string;
}) {
  return (
    <FormField id={id} label={label}>
      <select
        id={id}
        value={value ?? ""}
        onChange={(event) => onChange(options.find((option) => option.value === event.target.value)?.value)}
        className="min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink outline-none focus:border-focus focus:ring-2 focus:ring-focus/25"
      >
        <option value="">{placeholder}</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </FormField>
  );
}

export function RadioField<T extends string>({
  id,
  legend,
  value,
  options,
  onChange,
}: {
  id: string;
  legend: string;
  value: T | null | undefined;
  options: readonly Choice<T>[];
  onChange: (value: T) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-semibold text-ink">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((option) => {
          const inputId = `${id}-${option.value.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
          return (
            <label key={option.value} htmlFor={inputId} className="flex min-h-10 items-start gap-2 rounded-md border border-border px-3 py-2 text-sm text-ink focus-within:ring-2 focus-within:ring-focus/30">
              <input
                id={inputId}
                type="radio"
                name={id}
                value={option.value}
                checked={value === option.value}
                onChange={() => onChange(option.value)}
                className="mt-0.5 accent-brand"
              />
              <span>{option.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function BooleanField({
  id,
  legend,
  value,
  yesLabel = "Yes",
  noLabel = "No",
  onChange,
}: {
  id: string;
  legend: string;
  value: boolean | null | undefined;
  yesLabel?: string;
  noLabel?: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-semibold text-ink">{legend}</legend>
      <div className="flex flex-wrap gap-2">
        {[
          { value: true, label: yesLabel },
          { value: false, label: noLabel },
        ].map((option) => (
          <label key={String(option.value)} className="inline-flex min-h-10 items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-ink focus-within:ring-2 focus-within:ring-focus/30">
            <input
              type="radio"
              name={id}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="accent-brand"
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function CheckboxField<T extends string>({
  id,
  legend,
  values,
  options,
  onChange,
}: {
  id: string;
  legend: string;
  values: readonly T[] | undefined;
  options: readonly Choice<T>[];
  onChange: (values: T[]) => void;
}) {
  function toggle(value: T) {
    const current = values ?? [];
    onChange(current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
  }

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-semibold text-ink">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((option) => {
          const inputId = `${id}-${option.value.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
          return (
            <label key={option.value} htmlFor={inputId} className="flex min-h-10 items-start gap-2 rounded-md border border-border px-3 py-2 text-sm leading-5 text-ink focus-within:ring-2 focus-within:ring-focus/30">
              <input
                id={inputId}
                type="checkbox"
                checked={values?.includes(option.value) ?? false}
                onChange={() => toggle(option.value)}
                className="mt-1 accent-brand"
              />
              <span>{option.label}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
