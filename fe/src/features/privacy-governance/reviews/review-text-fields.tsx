"use client";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { PrivacyFieldLabels } from "@/features/privacy-governance/privacy-governance-errors";
import { FieldHint } from "@/features/privacy-governance/privacy-governance-shared";

export const reviewFieldLabels: PrivacyFieldLabels = {
  review_type: "Review type",
  scope_summary: "Scope",
  findings_summary: "Findings",
  recommendations_summary: "Recommendations",
  resolution_summary: "Resolution summary",
};

export type ReviewTextValues = {
  scope: string;
  findings: string;
  recommendations: string;
};

export function ReviewTextFields({
  idPrefix,
  values,
  onChange,
}: {
  idPrefix: string;
  values: ReviewTextValues;
  onChange: (values: ReviewTextValues) => void;
}) {
  return (
    <>
      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-scope`}>Scope</Label>
        <FieldHint id={`${idPrefix}-scope-hint`}>What this review covers.</FieldHint>
        <Textarea
          id={`${idPrefix}-scope`}
          required
          maxLength={2000}
          rows={3}
          value={values.scope}
          aria-describedby={`${idPrefix}-scope-hint`}
          onChange={(event) => onChange({ ...values, scope: event.target.value })}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-findings`}>Findings</Label>
        <FieldHint id={`${idPrefix}-findings-hint`}>
          Optional while the review is open.
        </FieldHint>
        <Textarea
          id={`${idPrefix}-findings`}
          maxLength={4000}
          rows={5}
          value={values.findings}
          aria-describedby={`${idPrefix}-findings-hint`}
          onChange={(event) => onChange({ ...values, findings: event.target.value })}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor={`${idPrefix}-recommendations`}>Recommendations</Label>
        <FieldHint id={`${idPrefix}-recommendations-hint`}>
          Optional while the review is open.
        </FieldHint>
        <Textarea
          id={`${idPrefix}-recommendations`}
          maxLength={4000}
          rows={5}
          value={values.recommendations}
          aria-describedby={`${idPrefix}-recommendations-hint`}
          onChange={(event) =>
            onChange({ ...values, recommendations: event.target.value })
          }
        />
      </div>
    </>
  );
}
