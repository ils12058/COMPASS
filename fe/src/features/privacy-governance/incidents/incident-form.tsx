"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PrivacyFieldLabels } from "@/features/privacy-governance/privacy-governance-errors";
import {
  editableIncidentStatuses,
  incidentStatusLabels,
  notificationAssessmentLabels,
} from "@/features/privacy-governance/privacy-governance-presentation";
import {
  CategoryInput,
  FieldHint,
  FormSection,
  privacySelectClass,
} from "@/features/privacy-governance/privacy-governance-shared";
import { dateTimeInputToISO, isoToDateTimeInput } from "@/lib/date-time";
import {
  NotificationAssessmentValue,
  type IncidentStatusValue,
  type PrivacyIncidentCreateRequest,
  type PrivacyIncidentResponse,
  type PrivacyIncidentUpdateRequest,
} from "@/lib/api/generated/model";

export const incidentFieldLabels: PrivacyFieldLabels = {
  title: "Title",
  summary: "Summary",
  affected_area: "Affected area",
  personal_data_categories: "Personal data categories",
  occurred_at: "Occurred",
  discovered_at: "Discovered",
  estimated_affected_subjects: "Estimated affected people",
  assessment_summary: "Assessment summary",
  containment_summary: "Containment summary",
  notification_assessment: "Notification assessment",
  notification_reference: "Notification reference",
  status: "Status",
};

export type IncidentFormValues = {
  status: IncidentStatusValue | null;
  title: string;
  summary: string;
  affectedArea: string;
  personalDataCategories: string[];
  occurredAt: string;
  discoveredAt: string;
  estimatedAffected: string;
  assessmentSummary: string;
  containmentSummary: string;
  notificationAssessment: NotificationAssessmentValue;
  notificationReference: string;
};

export const emptyIncidentValues: IncidentFormValues = {
  status: null,
  title: "",
  summary: "",
  affectedArea: "",
  personalDataCategories: [],
  occurredAt: "",
  discoveredAt: "",
  estimatedAffected: "",
  assessmentSummary: "",
  containmentSummary: "",
  notificationAssessment: NotificationAssessmentValue.NOT_ASSESSED,
  notificationReference: "",
};

export function incidentFormValues(item: PrivacyIncidentResponse): IncidentFormValues {
  return {
    status: item.status,
    title: item.title,
    summary: item.summary,
    affectedArea: item.affected_area,
    personalDataCategories: [...item.personal_data_categories],
    occurredAt: isoToDateTimeInput(item.occurred_at),
    discoveredAt: isoToDateTimeInput(item.discovered_at),
    estimatedAffected:
      item.estimated_affected_subjects === null ? "" : String(item.estimated_affected_subjects),
    assessmentSummary: item.assessment_summary,
    containmentSummary: item.containment_summary,
    notificationAssessment: item.notification_assessment,
    notificationReference: item.notification_reference,
  };
}

type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

function parseEstimate(value: string): Parsed<number | null> {
  const trimmed = value.trim();
  if (!trimmed) return { ok: true, value: null };
  const parsed = Number(trimmed);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    return {
      ok: false,
      error: "Estimated affected people must be a whole number of zero or more.",
    };
  }
  return { ok: true, value: parsed };
}

function parseDiscovered(value: string): Parsed<string> {
  const iso = dateTimeInputToISO(value);
  return iso ? { ok: true, value: iso } : { ok: false, error: "Enter when the incident was discovered." };
}

export function incidentCreateRequest(
  values: IncidentFormValues,
): Parsed<PrivacyIncidentCreateRequest> {
  const estimate = parseEstimate(values.estimatedAffected);
  if (!estimate.ok) return estimate;
  const discovered = parseDiscovered(values.discoveredAt);
  if (!discovered.ok) return discovered;
  return {
    ok: true,
    value: {
      title: values.title,
      summary: values.summary,
      affected_area: values.affectedArea,
      personal_data_categories: values.personalDataCategories,
      occurred_at: dateTimeInputToISO(values.occurredAt),
      discovered_at: discovered.value,
      estimated_affected_subjects: estimate.value,
      assessment_summary: values.assessmentSummary,
      containment_summary: values.containmentSummary,
      notification_assessment: values.notificationAssessment,
      notification_reference: values.notificationReference,
    },
  };
}

function sameList(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

export function incidentChanges(
  initial: IncidentFormValues,
  values: IncidentFormValues,
): Parsed<PrivacyIncidentUpdateRequest> {
  const changes: PrivacyIncidentUpdateRequest = {};
  if (values.status !== initial.status && values.status !== null) {
    changes.status = values.status;
  }
  if (values.title !== initial.title) changes.title = values.title;
  if (values.summary !== initial.summary) changes.summary = values.summary;
  if (values.affectedArea !== initial.affectedArea) changes.affected_area = values.affectedArea;
  if (!sameList(values.personalDataCategories, initial.personalDataCategories)) {
    changes.personal_data_categories = values.personalDataCategories;
  }
  if (values.occurredAt !== initial.occurredAt) {
    changes.occurred_at = dateTimeInputToISO(values.occurredAt);
  }
  if (values.discoveredAt !== initial.discoveredAt) {
    const discovered = parseDiscovered(values.discoveredAt);
    if (!discovered.ok) return discovered;
    changes.discovered_at = discovered.value;
  }
  if (values.estimatedAffected !== initial.estimatedAffected) {
    const estimate = parseEstimate(values.estimatedAffected);
    if (!estimate.ok) return estimate;
    changes.estimated_affected_subjects = estimate.value;
  }
  if (values.assessmentSummary !== initial.assessmentSummary) {
    changes.assessment_summary = values.assessmentSummary;
  }
  if (values.containmentSummary !== initial.containmentSummary) {
    changes.containment_summary = values.containmentSummary;
  }
  if (values.notificationAssessment !== initial.notificationAssessment) {
    changes.notification_assessment = values.notificationAssessment;
  }
  if (values.notificationReference !== initial.notificationReference) {
    changes.notification_reference = values.notificationReference;
  }
  return { ok: true, value: changes };
}

function TextArea({
  id,
  label,
  hint,
  required = false,
  maxLength,
  value,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  required?: boolean;
  maxLength: number;
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
        rows={4}
        value={value}
        aria-describedby={hint ? `${id}-hint` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

export function IncidentForm({
  initial,
  pending,
  submitLabel,
  pendingLabel,
  messages,
  cancel,
  onSubmit,
}: {
  initial: IncidentFormValues;
  pending: boolean;
  submitLabel: string;
  pendingLabel: string;
  messages: ReactNode;
  cancel: ReactNode;
  onSubmit: (values: IncidentFormValues) => void;
}) {
  const [values, setValues] = useState(initial);
  const statusOptions = initial.status ? editableIncidentStatuses(initial.status) : [];

  function set<K extends keyof IncidentFormValues>(key: K, value: IncidentFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(values);
  }

  return (
    <form className="max-w-3xl space-y-8" onSubmit={submit}>
      {initial.status ? (
        <FormSection title="Status">
          <div className="grid max-w-xs gap-2">
            <Label htmlFor="incident-status">Status</Label>
            <FieldHint id="incident-status-hint">
              Status moves forward only. Use Resolve incident to resolve it.
            </FieldHint>
            <select
              id="incident-status"
              className={privacySelectClass}
              value={values.status ?? initial.status}
              aria-describedby="incident-status-hint"
              onChange={(event) => {
                const next = statusOptions.find((option) => option === event.target.value);
                if (next) set("status", next);
              }}
            >
              {statusOptions.map((option) => (
                <option key={option} value={option}>
                  {incidentStatusLabels[option]}
                </option>
              ))}
            </select>
          </div>
        </FormSection>
      ) : null}

      <FormSection title="What happened">
        <div className="grid gap-2">
          <Label htmlFor="incident-title">Title</Label>
          <Input
            id="incident-title"
            required
            maxLength={200}
            value={values.title}
            onChange={(event) => set("title", event.target.value)}
          />
        </div>
        <TextArea
          id="incident-summary"
          label="Summary"
          required
          maxLength={3000}
          value={values.summary}
          onChange={(value) => set("summary", value)}
        />
        <div className="grid gap-2">
          <Label htmlFor="incident-area">Affected area</Label>
          <FieldHint id="incident-area-hint">
            The system, office, or process involved.
          </FieldHint>
          <Input
            id="incident-area"
            required
            maxLength={255}
            value={values.affectedArea}
            aria-describedby="incident-area-hint"
            onChange={(event) => set("affectedArea", event.target.value)}
          />
        </div>
        <CategoryInput
          id="incident-data"
          label="Personal data categories"
          hint="Add each category involved separately."
          values={values.personalDataCategories}
          onChange={(next) => set("personalDataCategories", next)}
        />
      </FormSection>

      <FormSection title="Timing">
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="incident-occurred">Occurred</Label>
            <FieldHint id="incident-occurred-hint">Optional, if known.</FieldHint>
            <Input
              id="incident-occurred"
              type="datetime-local"
              value={values.occurredAt}
              aria-describedby="incident-occurred-hint"
              onChange={(event) => set("occurredAt", event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="incident-discovered">Discovered</Label>
            <FieldHint id="incident-discovered-hint">Required.</FieldHint>
            <Input
              id="incident-discovered"
              type="datetime-local"
              required
              value={values.discoveredAt}
              aria-describedby="incident-discovered-hint"
              onChange={(event) => set("discoveredAt", event.target.value)}
            />
          </div>
        </div>
      </FormSection>

      <FormSection title="Assessment">
        <div className="grid max-w-xs gap-2">
          <Label htmlFor="incident-estimate">Estimated affected people</Label>
          <FieldHint id="incident-estimate-hint">Optional. A whole number.</FieldHint>
          <Input
            id="incident-estimate"
            type="number"
            inputMode="numeric"
            min={0}
            step={1}
            value={values.estimatedAffected}
            aria-describedby="incident-estimate-hint"
            onChange={(event) => set("estimatedAffected", event.target.value)}
          />
        </div>
        <TextArea
          id="incident-assessment"
          label="Assessment summary"
          maxLength={4000}
          value={values.assessmentSummary}
          onChange={(value) => set("assessmentSummary", value)}
        />
      </FormSection>

      <FormSection title="Containment">
        <TextArea
          id="incident-containment"
          label="Containment summary"
          maxLength={4000}
          value={values.containmentSummary}
          onChange={(value) => set("containmentSummary", value)}
        />
      </FormSection>

      <FormSection title="Notification">
        <div className="grid max-w-xs gap-2">
          <Label htmlFor="incident-notification">Notification assessment</Label>
          <FieldHint id="incident-notification-hint">
            Record your team&apos;s assessment of whether notification is needed.
          </FieldHint>
          <select
            id="incident-notification"
            className={privacySelectClass}
            value={values.notificationAssessment}
            aria-describedby="incident-notification-hint"
            onChange={(event) => {
              const next = Object.values(NotificationAssessmentValue).find(
                (option) => option === event.target.value,
              );
              if (next) set("notificationAssessment", next);
            }}
          >
            {Object.values(NotificationAssessmentValue).map((option) => (
              <option key={option} value={option}>
                {notificationAssessmentLabels[option]}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="incident-notification-reference">Notification reference</Label>
          <FieldHint id="incident-notification-reference-hint">
            Optional. A reference for any notification made.
          </FieldHint>
          <Input
            id="incident-notification-reference"
            maxLength={255}
            value={values.notificationReference}
            aria-describedby="incident-notification-reference-hint"
            onChange={(event) => set("notificationReference", event.target.value)}
          />
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
