"use client";

import Link from "next/link";
import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PrivacyFieldLabels } from "@/features/privacy-governance/privacy-governance-errors";
import {
  CategoryInput,
  FieldHint,
  FormSection,
  secondaryLinkClass,
} from "@/features/privacy-governance/privacy-governance-shared";
import { RetentionPolicyPicker } from "@/features/privacy-governance/processing-activities/retention-policy-picker";
import type {
  ProcessingActivityCreateRequest,
  ProcessingActivityResponse,
  ProcessingActivityUpdateRequest,
  RetentionSummary,
} from "@/lib/api/generated/model";

export type ProcessingActivityFormValues = {
  code: string;
  name: string;
  purpose: string;
  dataSubjectCategories: string[];
  personalDataCategories: string[];
  authorizedAccess: string;
  safeguards: string;
  choiceSummary: string;
  retentionPolicyId: string;
  retentionReference: string;
  policyBasisReference: string;
};

export const processingActivityFieldLabels: PrivacyFieldLabels = {
  code: "Code",
  name: "Name",
  purpose: "Why we use this information",
  data_subject_categories: "Who the information is about",
  personal_data_categories: "What information is used",
  authorized_access_summary: "Who may access it",
  safeguards_summary: "How it is protected",
  data_subject_choice_summary: "Choices and consent",
  retention_policy_id: "Retention Policy",
  retention_policy_reference: "External retention-policy reference",
  policy_basis_reference: "Policy basis reference",
};

export const emptyProcessingActivityValues: ProcessingActivityFormValues = {
  code: "",
  name: "",
  purpose: "",
  dataSubjectCategories: [],
  personalDataCategories: [],
  authorizedAccess: "",
  safeguards: "",
  choiceSummary: "",
  retentionPolicyId: "",
  retentionReference: "",
  policyBasisReference: "",
};

export function processingActivityFormValues(
  item: ProcessingActivityResponse,
): ProcessingActivityFormValues {
  return {
    code: item.code,
    name: item.name,
    purpose: item.purpose,
    dataSubjectCategories: [...item.data_subject_categories],
    personalDataCategories: [...item.personal_data_categories],
    authorizedAccess: item.authorized_access_summary,
    safeguards: item.safeguards_summary,
    choiceSummary: item.data_subject_choice_summary,
    retentionPolicyId: item.retention_policy?.id ?? "",
    retentionReference: item.retention_policy_reference,
    policyBasisReference: item.policy_basis_reference,
  };
}

export function processingActivityCreateRequest(
  values: ProcessingActivityFormValues,
): ProcessingActivityCreateRequest {
  return {
    code: values.code,
    name: values.name,
    purpose: values.purpose,
    data_subject_categories: values.dataSubjectCategories,
    personal_data_categories: values.personalDataCategories,
    authorized_access_summary: values.authorizedAccess,
    safeguards_summary: values.safeguards,
    data_subject_choice_summary: values.choiceSummary,
    retention_policy_id: values.retentionPolicyId || null,
    retention_policy_reference: values.retentionReference,
    policy_basis_reference: values.policyBasisReference,
  };
}

function sameList(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

// PATCH only what changed. An unchanged retired Retention Policy assignment
// is never re-sent, because the backend rejects assigning a retired policy.
export function processingActivityChanges(
  initial: ProcessingActivityFormValues,
  values: ProcessingActivityFormValues,
): ProcessingActivityUpdateRequest {
  const changes: ProcessingActivityUpdateRequest = {};
  if (values.name !== initial.name) changes.name = values.name;
  if (values.purpose !== initial.purpose) changes.purpose = values.purpose;
  if (!sameList(values.dataSubjectCategories, initial.dataSubjectCategories)) {
    changes.data_subject_categories = values.dataSubjectCategories;
  }
  if (!sameList(values.personalDataCategories, initial.personalDataCategories)) {
    changes.personal_data_categories = values.personalDataCategories;
  }
  if (values.authorizedAccess !== initial.authorizedAccess) {
    changes.authorized_access_summary = values.authorizedAccess;
  }
  if (values.safeguards !== initial.safeguards) changes.safeguards_summary = values.safeguards;
  if (values.choiceSummary !== initial.choiceSummary) {
    changes.data_subject_choice_summary = values.choiceSummary;
  }
  if (values.retentionPolicyId !== initial.retentionPolicyId) {
    changes.retention_policy_id = values.retentionPolicyId || null;
  }
  if (values.retentionReference !== initial.retentionReference) {
    changes.retention_policy_reference = values.retentionReference;
  }
  if (values.policyBasisReference !== initial.policyBasisReference) {
    changes.policy_basis_reference = values.policyBasisReference;
  }
  return changes;
}

function TextAreaField({
  id,
  label,
  hint,
  required = false,
  maxLength,
  rows = 4,
  value,
  onChange,
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  required?: boolean;
  maxLength: number;
  rows?: number;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      {hint ? <FieldHint id={`${id}-hint`}>{hint}</FieldHint> : null}
      <Textarea
        id={id}
        required={required}
        maxLength={maxLength}
        rows={rows}
        value={value}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

export function ProcessingActivityForm({
  mode,
  initial,
  currentPolicy,
  pending,
  submitLabel,
  pendingLabel,
  cancelHref,
  messages,
  onSubmit,
}: {
  mode: "create" | "edit";
  initial: ProcessingActivityFormValues;
  currentPolicy: RetentionSummary | null;
  pending: boolean;
  submitLabel: string;
  pendingLabel: string;
  cancelHref: string;
  messages: ReactNode;
  onSubmit: (values: ProcessingActivityFormValues) => void;
}) {
  const [values, setValues] = useState(initial);

  function set<K extends keyof ProcessingActivityFormValues>(
    key: K,
    value: ProcessingActivityFormValues[K],
  ) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(values);
  }

  return (
    <form className="max-w-3xl space-y-8" onSubmit={submit}>
      <FormSection title="Basic information">
        {mode === "create" ? (
          <div className="grid gap-2">
            <Label htmlFor="processing-code">Code</Label>
            <FieldHint id="processing-code-hint">
              Use a stable internal code of letters, digits, dots, underscores, or
              hyphens. COMPASS stores it in uppercase. The code cannot be changed
              later.
            </FieldHint>
            <Input
              id="processing-code"
              required
              maxLength={64}
              autoComplete="off"
              spellCheck={false}
              className="max-w-sm font-mono"
              value={values.code}
              aria-describedby="processing-code-hint"
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
          <Label htmlFor="processing-name">Name</Label>
          <Input
            id="processing-name"
            required
            maxLength={160}
            value={values.name}
            onChange={(event) => set("name", event.target.value)}
          />
        </div>
        <TextAreaField
          id="processing-purpose"
          label="Why we use this information"
          required
          maxLength={2000}
          value={values.purpose}
          onChange={(value) => set("purpose", value)}
        />
      </FormSection>

      <FormSection title="Information involved">
        <CategoryInput
          id="processing-subjects"
          label="Who the information is about"
          hint="Add each group separately, for example Students."
          values={values.dataSubjectCategories}
          onChange={(next) => set("dataSubjectCategories", next)}
        />
        <CategoryInput
          id="processing-data"
          label="What information is used"
          hint="Add each category separately, for example Contact details."
          values={values.personalDataCategories}
          onChange={(next) => set("personalDataCategories", next)}
        />
      </FormSection>

      <FormSection title="Access and protection">
        <TextAreaField
          id="processing-access"
          label="Who may access it"
          required
          maxLength={2000}
          value={values.authorizedAccess}
          onChange={(value) => set("authorizedAccess", value)}
        />
        <TextAreaField
          id="processing-safeguards"
          label="How it is protected"
          required
          maxLength={2000}
          value={values.safeguards}
          onChange={(value) => set("safeguards", value)}
        />
      </FormSection>

      <FormSection title="Choices and consent">
        <TextAreaField
          id="processing-choices"
          label="Choices and consent"
          hint="Describe any opt-in, opt-out, withdrawal, or separate consent that applies. Leave this blank when there is no applicable user choice."
          maxLength={2000}
          value={values.choiceSummary}
          onChange={(value) => set("choiceSummary", value)}
        />
      </FormSection>

      <FormSection title="Retention and policy">
        <RetentionPolicyPicker
          id="processing-retention-policy"
          value={values.retentionPolicyId}
          currentPolicy={currentPolicy}
          onChange={(value) => set("retentionPolicyId", value)}
        />
        <div className="grid gap-2">
          <Label htmlFor="processing-retention-reference">
            External retention-policy reference
          </Label>
          <FieldHint id="processing-retention-reference-hint">
            Optional. A reference to retention guidance kept outside COMPASS.
          </FieldHint>
          <Input
            id="processing-retention-reference"
            maxLength={255}
            value={values.retentionReference}
            aria-describedby="processing-retention-reference-hint"
            onChange={(event) => set("retentionReference", event.target.value)}
          />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="processing-policy-basis">Policy basis reference</Label>
          <FieldHint id="processing-policy-basis-hint">
            Optional. A reference to the policy or document this activity relies on.
          </FieldHint>
          <Input
            id="processing-policy-basis"
            maxLength={255}
            value={values.policyBasisReference}
            aria-describedby="processing-policy-basis-hint"
            onChange={(event) => set("policyBasisReference", event.target.value)}
          />
        </div>
      </FormSection>

      {messages}

      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
        <Link href={cancelHref} className={secondaryLinkClass}>
          Cancel
        </Link>
        <Button type="submit" disabled={pending}>
          {pending ? pendingLabel : submitLabel}
        </Button>
      </div>
    </form>
  );
}
