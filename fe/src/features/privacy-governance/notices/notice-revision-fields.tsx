"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PrivacyFieldLabels } from "@/features/privacy-governance/privacy-governance-errors";
import {
  audienceDescriptions,
  audienceLabels,
  audienceOrder,
} from "@/features/privacy-governance/privacy-governance-presentation";
import { FieldHint } from "@/features/privacy-governance/privacy-governance-shared";
import type {
  AudienceValue,
  RevisionCreate,
  RevisionResponse,
  RevisionUpdate,
} from "@/lib/api/generated/model";

export const ACKNOWLEDGMENT_EXPLANATION =
  "Acknowledgment records that a person saw this notice revision. It is not consent to all data processing.";

export const noticeFieldLabels: PrivacyFieldLabels = {
  code: "Internal code",
  name: "Notice name",
  title: "Notice title",
  audiences: "Who should see this?",
  summary: "Short explanation",
  body: "Notice text",
  requires_acknowledgment: "Require acknowledgment",
  effective_on: "Effective date",
};

export type NoticeRevisionValues = {
  title: string;
  audiences: AudienceValue[];
  summary: string;
  body: string;
  requiresAcknowledgment: boolean;
  effectiveOn: string;
};

export const emptyNoticeRevisionValues: NoticeRevisionValues = {
  title: "",
  audiences: [],
  summary: "",
  body: "",
  requiresAcknowledgment: false,
  effectiveOn: "",
};

export function noticeRevisionValues(revision: RevisionResponse): NoticeRevisionValues {
  return {
    title: revision.title,
    audiences: [...revision.audiences],
    summary: revision.summary,
    body: revision.body,
    requiresAcknowledgment: revision.requires_acknowledgment,
    effectiveOn: revision.effective_on ?? "",
  };
}

function orderedAudiences(audiences: AudienceValue[]): AudienceValue[] {
  return audienceOrder.filter((audience) => audiences.includes(audience));
}

export function noticeRevisionCreateRequest(values: NoticeRevisionValues): RevisionCreate {
  return {
    title: values.title,
    audiences: orderedAudiences(values.audiences),
    summary: values.summary,
    body: values.body,
    requires_acknowledgment: values.requiresAcknowledgment,
    effective_on: values.effectiveOn || null,
  };
}

export function noticeRevisionChanges(
  initial: NoticeRevisionValues,
  values: NoticeRevisionValues,
): RevisionUpdate {
  const changes: RevisionUpdate = {};
  if (values.title !== initial.title) changes.title = values.title;
  const nextAudiences = orderedAudiences(values.audiences);
  if (nextAudiences.join() !== orderedAudiences(initial.audiences).join()) {
    changes.audiences = nextAudiences;
  }
  if (values.summary !== initial.summary) changes.summary = values.summary;
  if (values.body !== initial.body) changes.body = values.body;
  if (values.requiresAcknowledgment !== initial.requiresAcknowledgment) {
    changes.requires_acknowledgment = values.requiresAcknowledgment;
  }
  if (values.effectiveOn !== initial.effectiveOn) {
    changes.effective_on = values.effectiveOn || null;
  }
  return changes;
}

export function NoticeRevisionFields({
  idPrefix,
  values,
  audienceError,
  onChange,
}: {
  idPrefix: string;
  values: NoticeRevisionValues;
  audienceError: string | null;
  onChange: (values: NoticeRevisionValues) => void;
}) {
  function toggleAudience(audience: AudienceValue, checked: boolean) {
    onChange({
      ...values,
      audiences: checked
        ? orderedAudiences([...values.audiences, audience])
        : values.audiences.filter((item) => item !== audience),
    });
  }

  return (
    <>
      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-title`}>Notice title</Label>
        <Input
          id={`${idPrefix}-title`}
          required
          maxLength={200}
          value={values.title}
          onChange={(event) => onChange({ ...values, title: event.target.value })}
        />
      </div>

      <fieldset
        className="grid gap-2"
        aria-describedby={audienceError ? `${idPrefix}-audience-error` : undefined}
      >
        <legend className="text-sm font-medium text-ink">Who should see this?</legend>
        {audienceOrder.map((audience) => (
          <label key={audience} className="flex items-start gap-3 py-1 text-sm text-ink">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 shrink-0 accent-brand"
              checked={values.audiences.includes(audience)}
              onChange={(event) => toggleAudience(audience, event.target.checked)}
            />
            <span>
              <span className="font-medium">{audienceLabels[audience]}</span>
              <span className="block text-xs leading-5 text-muted">
                {audienceDescriptions[audience]}
              </span>
            </span>
          </label>
        ))}
        {audienceError ? (
          <p id={`${idPrefix}-audience-error`} role="alert" className="text-sm text-danger">
            {audienceError}
          </p>
        ) : null}
      </fieldset>

      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-summary`}>Short explanation</Label>
        <FieldHint id={`${idPrefix}-summary-hint`}>
          Shown with the notice as a brief summary.
        </FieldHint>
        <Textarea
          id={`${idPrefix}-summary`}
          required
          maxLength={2000}
          rows={3}
          value={values.summary}
          aria-describedby={`${idPrefix}-summary-hint`}
          onChange={(event) => onChange({ ...values, summary: event.target.value })}
        />
      </div>

      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-body`}>Notice text</Label>
        <FieldHint id={`${idPrefix}-body-hint`}>
          Use plain language. Paragraph breaks will be preserved.
        </FieldHint>
        <Textarea
          id={`${idPrefix}-body`}
          required
          maxLength={20000}
          rows={14}
          className="min-h-72"
          value={values.body}
          aria-describedby={`${idPrefix}-body-hint`}
          onChange={(event) => onChange({ ...values, body: event.target.value })}
        />
      </div>

      <div className="grid gap-1">
        <label className="flex items-start gap-3 text-sm text-ink">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 shrink-0 accent-brand"
            checked={values.requiresAcknowledgment}
            aria-describedby={`${idPrefix}-acknowledgment-hint`}
            onChange={(event) =>
              onChange({ ...values, requiresAcknowledgment: event.target.checked })
            }
          />
          <span className="font-medium">Require acknowledgment</span>
        </label>
        <p id={`${idPrefix}-acknowledgment-hint`} className="pl-7 text-xs leading-5 text-muted">
          {ACKNOWLEDGMENT_EXPLANATION}
        </p>
      </div>

      <div className="grid max-w-56 gap-2">
        <Label htmlFor={`${idPrefix}-effective`}>Effective date</Label>
        <Input
          id={`${idPrefix}-effective`}
          type="date"
          value={values.effectiveOn}
          aria-describedby={`${idPrefix}-effective-hint`}
          onChange={(event) => onChange({ ...values, effectiveOn: event.target.value })}
        />
      </div>
      <FieldHint id={`${idPrefix}-effective-hint`}>
        A revision can be published on or after its effective date.
      </FieldHint>
    </>
  );
}
