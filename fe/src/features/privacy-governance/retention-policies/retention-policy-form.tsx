"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PrivacyFieldLabels } from "@/features/privacy-governance/privacy-governance-errors";
import { formatLongDate } from "@/features/privacy-governance/privacy-governance-presentation";
import {
  FieldHint,
  FormSection,
} from "@/features/privacy-governance/privacy-governance-shared";
import { localDateInputValue } from "@/lib/date-time";
import type {
  RetentionCreate,
  RetentionResponse,
  RetentionUpdate,
} from "@/lib/api/generated/model";

export const RETENTION_BOUNDARY_NOTE =
  "Retention Policies document institutional guidance. COMPASS does not automatically delete records from these settings.";

export type RetentionFormValues = {
  code: string;
  name: string;
  scope: string;
  trigger: string;
  period: string;
  disposition: string;
  policyReference: string;
  effectiveOn: string;
  reviewDueOn: string;
};

export const retentionFieldLabels: PrivacyFieldLabels = {
  code: "Code",
  name: "Name",
  scope_summary: "What records does this cover?",
  retention_trigger_summary: "When does the retention period start?",
  retention_period_summary: "How long are records kept?",
  disposition_summary: "What happens after the retention period?",
  policy_reference: "Policy reference",
  effective_on: "Effective date",
  review_due_on: "Review due",
};

export const emptyRetentionValues: RetentionFormValues = {
  code: "",
  name: "",
  scope: "",
  trigger: "",
  period: "",
  disposition: "",
  policyReference: "",
  effectiveOn: "",
  reviewDueOn: "",
};

export function retentionFormValues(item: RetentionResponse): RetentionFormValues {
  return {
    code: item.code,
    name: item.name,
    scope: item.scope_summary,
    trigger: item.retention_trigger_summary,
    period: item.retention_period_summary,
    disposition: item.disposition_summary,
    policyReference: item.policy_reference,
    effectiveOn: item.effective_on ?? "",
    reviewDueOn: item.review_due_on ?? "",
  };
}

export function retentionCreateRequest(values: RetentionFormValues): RetentionCreate {
  return {
    code: values.code,
    name: values.name,
    scope_summary: values.scope,
    retention_trigger_summary: values.trigger,
    retention_period_summary: values.period,
    disposition_summary: values.disposition,
    policy_reference: values.policyReference,
    effective_on: values.effectiveOn || null,
    review_due_on: values.reviewDueOn || null,
  };
}

export function retentionChanges(
  initial: RetentionFormValues,
  values: RetentionFormValues,
): RetentionUpdate {
  const changes: RetentionUpdate = {};
  if (values.name !== initial.name) changes.name = values.name;
  if (values.scope !== initial.scope) changes.scope_summary = values.scope;
  if (values.trigger !== initial.trigger) changes.retention_trigger_summary = values.trigger;
  if (values.period !== initial.period) changes.retention_period_summary = values.period;
  if (values.disposition !== initial.disposition) {
    changes.disposition_summary = values.disposition;
  }
  if (values.policyReference !== initial.policyReference) {
    changes.policy_reference = values.policyReference;
  }
  if (values.effectiveOn !== initial.effectiveOn) {
    changes.effective_on = values.effectiveOn || null;
  }
  if (values.reviewDueOn !== initial.reviewDueOn) {
    changes.review_due_on = values.reviewDueOn || null;
  }
  return changes;
}

export function reviewDuePassed(value: string | null): boolean {
  return value !== null && value < localDateInputValue();
}

// Factual wording only: a passed review date is not a compliance finding.
export function ReviewDueText({ value }: { value: string | null }) {
  if (!value) return <span className="text-muted">No review date set.</span>;
  if (reviewDuePassed(value)) {
    return (
      <span className="text-warning">Review date passed on {formatLongDate(value)}.</span>
    );
  }
  return <span>Review due {formatLongDate(value)}.</span>;
}

function QuestionField({
  id,
  label,
  maxLength,
  value,
  onChange,
}: {
  id: string;
  label: string;
  maxLength: number;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        id={id}
        required
        maxLength={maxLength}
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

export function RetentionPolicyForm({
  mode,
  initial,
  pending,
  submitLabel,
  pendingLabel,
  messages,
  cancel,
  onSubmit,
}: {
  mode: "create" | "edit";
  initial: RetentionFormValues;
  pending: boolean;
  submitLabel: string;
  pendingLabel: string;
  messages: ReactNode;
  cancel: ReactNode;
  onSubmit: (values: RetentionFormValues) => void;
}) {
  const [values, setValues] = useState(initial);

  function set<K extends keyof RetentionFormValues>(key: K, value: RetentionFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(values);
  }

  return (
    <form className="max-w-3xl space-y-8" onSubmit={submit}>
      <FormSection title="Policy">
        {mode === "create" ? (
          <div className="grid gap-2">
            <Label htmlFor="retention-code">Code</Label>
            <FieldHint id="retention-code-hint">
              Use a stable internal code of letters, digits, dots, underscores, or
              hyphens. COMPASS stores it in uppercase. The code cannot be changed
              later.
            </FieldHint>
            <Input
              id="retention-code"
              required
              maxLength={64}
              autoComplete="off"
              spellCheck={false}
              className="max-w-sm font-mono"
              value={values.code}
              aria-describedby="retention-code-hint"
              onChange={(event) => set("code", event.target.value)}
            />
          </div>
        ) : (
          <div className="grid gap-1">
            <p className="text-sm font-medium text-ink">Code</p>
            <p className="break-all font-mono text-sm text-ink">{values.code}</p>
            <FieldHint>The code cannot be changed.</FieldHint>
          </div>
        )}
        <div className="grid gap-2">
          <Label htmlFor="retention-name">Name</Label>
          <Input
            id="retention-name"
            required
            maxLength={160}
            value={values.name}
            onChange={(event) => set("name", event.target.value)}
          />
        </div>
      </FormSection>

      <FormSection title="Retention guidance" description={RETENTION_BOUNDARY_NOTE}>
        <QuestionField
          id="retention-scope"
          label="What records does this cover?"
          maxLength={2000}
          value={values.scope}
          onChange={(value) => set("scope", value)}
        />
        <QuestionField
          id="retention-trigger"
          label="When does the retention period start?"
          maxLength={2000}
          value={values.trigger}
          onChange={(value) => set("trigger", value)}
        />
        <QuestionField
          id="retention-period"
          label="How long are records kept?"
          maxLength={1000}
          value={values.period}
          onChange={(value) => set("period", value)}
        />
        <QuestionField
          id="retention-disposition"
          label="What happens after the retention period?"
          maxLength={2000}
          value={values.disposition}
          onChange={(value) => set("disposition", value)}
        />
      </FormSection>

      <FormSection title="Reference and dates">
        <div className="grid gap-2">
          <Label htmlFor="retention-reference">Policy reference</Label>
          <FieldHint id="retention-reference-hint">
            Optional. The institutional document or section this policy comes from.
          </FieldHint>
          <Input
            id="retention-reference"
            maxLength={255}
            value={values.policyReference}
            aria-describedby="retention-reference-hint"
            onChange={(event) => set("policyReference", event.target.value)}
          />
        </div>
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="retention-effective">Effective date</Label>
            <Input
              id="retention-effective"
              type="date"
              value={values.effectiveOn}
              onChange={(event) => set("effectiveOn", event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="retention-review-due">Review due</Label>
            <Input
              id="retention-review-due"
              type="date"
              value={values.reviewDueOn}
              onChange={(event) => set("reviewDueOn", event.target.value)}
            />
          </div>
        </div>
      </FormSection>

      {messages}

      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
        {cancel}
        <Button type="submit" disabled={pending}>
          {pending ? pendingLabel : submitLabel}
        </Button>
      </div>
    </form>
  );
}
