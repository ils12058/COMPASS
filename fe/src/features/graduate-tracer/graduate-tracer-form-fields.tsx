"use client";

import type { ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Choice } from "@/features/graduate-tracer/graduate-tracer-presentation";

export type GraduateTracerErrorLookup = (targetId: string) => string | undefined;

export function FormField({
  id,
  label,
  hint,
  required = false,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  required?: boolean;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </Label>
      {children}
      {hint ? <p id={`${id}-hint`} className="text-xs leading-5 text-muted">{hint}</p> : null}
      {error ? <p id={`${id}-error`} role="alert" className="text-xs leading-5 text-danger">{error}</p> : null}
    </div>
  );
}

function describedBy(id: string, hint?: string, error?: string): string | undefined {
  return [
    hint ? `${id}-hint` : undefined,
    error ? `${id}-error` : undefined,
  ].filter(Boolean).join(" ") || undefined;
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
  required = false,
  error,
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
  required?: boolean;
  error?: string;
}) {
  return (
    <FormField id={id} label={label} hint={hint} required={required} error={error}>
      <Input
        id={id}
        type={type}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        inputMode={inputMode}
        min={min}
        max={max}
        step={step}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
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
  required = false,
  error,
}: {
  id: string;
  label: string;
  value: string | undefined;
  onChange: (value: string) => void;
  hint?: string;
  required?: boolean;
  error?: string;
}) {
  return (
    <FormField id={id} label={label} hint={hint} required={required} error={error}>
      <Textarea
        id={id}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
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
  required = false,
  error,
}: {
  id: string;
  label: string;
  value: T | null | undefined;
  options: readonly Choice<T>[];
  onChange: (value: T | undefined) => void;
  placeholder?: string;
  required?: boolean;
  error?: string;
}) {
  return (
    <FormField id={id} label={label} required={required} error={error}>
      <select
        id={id}
        value={value ?? ""}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(options.find((option) => option.value === event.target.value)?.value)}
        className="min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm text-ink outline-none focus:border-focus focus:ring-2 focus:ring-focus/25 aria-[invalid=true]:border-danger aria-[invalid=true]:focus:border-danger aria-[invalid=true]:focus:ring-danger/25"
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
  required = false,
  error,
}: {
  id: string;
  legend: string;
  value: T | null | undefined;
  options: readonly Choice<T>[];
  onChange: (value: T) => void;
  required?: boolean;
  error?: string;
}) {
  const errorId = error ? `${id}-error` : undefined;
  return (
    <fieldset
      id={id}
      className="space-y-2"
      aria-required={required || undefined}
      aria-invalid={error ? true : undefined}
      aria-describedby={errorId}
    >
      <legend className="text-sm font-semibold text-ink">
        {legend}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((option) => {
          const inputId = `${id}-${option.value.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
          return (
            <label
              key={option.value}
              htmlFor={inputId}
              className={`flex min-h-10 items-start gap-2 rounded-md border px-3 py-2 text-sm text-ink focus-within:ring-2 focus-within:ring-focus/30 ${error ? "border-danger" : "border-border"}`}
            >
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
      {error ? <p id={errorId} role="alert" className="text-xs leading-5 text-danger">{error}</p> : null}
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
  required = false,
  error,
}: {
  id: string;
  legend: string;
  value: boolean | null | undefined;
  yesLabel?: string;
  noLabel?: string;
  onChange: (value: boolean) => void;
  required?: boolean;
  error?: string;
}) {
  const errorId = error ? `${id}-error` : undefined;
  return (
    <fieldset
      id={id}
      className="space-y-2"
      aria-required={required || undefined}
      aria-invalid={error ? true : undefined}
      aria-describedby={errorId}
    >
      <legend className="text-sm font-semibold text-ink">
        {legend}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </legend>
      <div className="flex flex-wrap gap-2">
        {[
          { value: true, label: yesLabel, suffix: "yes" },
          { value: false, label: noLabel, suffix: "no" },
        ].map((option) => (
          <label
            key={String(option.value)}
            htmlFor={`${id}-${option.suffix}`}
            className={`inline-flex min-h-10 items-center gap-2 rounded-md border px-3 py-2 text-sm text-ink focus-within:ring-2 focus-within:ring-focus/30 ${error ? "border-danger" : "border-border"}`}
          >
            <input
              id={`${id}-${option.suffix}`}
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
      {error ? <p id={errorId} role="alert" className="text-xs leading-5 text-danger">{error}</p> : null}
    </fieldset>
  );
}

export function CheckboxField<T extends string>({
  id,
  legend,
  values,
  options,
  onChange,
  required = false,
  error,
}: {
  id: string;
  legend: string;
  values: readonly T[] | undefined;
  options: readonly Choice<T>[];
  onChange: (values: T[]) => void;
  required?: boolean;
  error?: string;
}) {
  function toggle(value: T) {
    const current = values ?? [];
    onChange(current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
  }

  const errorId = error ? `${id}-error` : undefined;
  return (
    <fieldset
      id={id}
      className="space-y-2"
      aria-required={required || undefined}
      aria-invalid={error ? true : undefined}
      aria-describedby={errorId}
    >
      <legend className="text-sm font-semibold text-ink">
        {legend}
        {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
      </legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {options.map((option) => {
          const inputId = `${id}-${option.value.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
          return (
            <label
              key={option.value}
              htmlFor={inputId}
              className={`flex min-h-10 items-start gap-2 rounded-md border px-3 py-2 text-sm leading-5 text-ink focus-within:ring-2 focus-within:ring-focus/30 ${error ? "border-danger" : "border-border"}`}
            >
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
      {error ? <p id={errorId} role="alert" className="text-xs leading-5 text-danger">{error}</p> : null}
    </fieldset>
  );
}
