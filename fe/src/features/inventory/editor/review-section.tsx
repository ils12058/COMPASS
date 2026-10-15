"use client";

import { Button } from "@/components/ui/button";
import type { InventorySubmissionIssue } from "@/features/inventory/inventory-payload";
import { inventorySections } from "@/features/inventory/inventory-presentation";
import { FieldGroup, InventoryNotice } from "@/features/inventory/inventory-shared";
import type { InventoryPayload } from "@/lib/api/generated/model";
import { yearLevelLabel } from "@/lib/year-level";

export function ReviewSection({
  draft,
  academicYear,
  formRevision,
  issues,
  programLookupReady,
  onSelectIssue,
}: {
  draft: InventoryPayload;
  academicYear: string;
  formRevision: string;
  issues: InventorySubmissionIssue[];
  programLookupReady: boolean;
  onSelectIssue: (issue: InventorySubmissionIssue) => void;
}) {
  const hasProgram = Boolean(draft.program_id);
  return (
    <div className="space-y-7">
      <FieldGroup legend="Record details">
        <dl className="grid gap-x-6 sm:grid-cols-2">
          <div className="border-b border-border py-3">
            <dt className="text-xs font-semibold text-muted">Academic Year</dt>
            <dd className="mt-1 text-sm text-ink">{academicYear}</dd>
          </div>
          <div className="border-b border-border py-3">
            <dt className="text-xs font-semibold text-muted">Official Form Revision</dt>
            <dd className="mt-1 text-sm text-ink">{formRevision}</dd>
          </div>
          <div className="border-b border-border py-3">
            <dt className="text-xs font-semibold text-muted">Current Program</dt>
            <dd className="mt-1 text-sm text-ink">
              {draft.course_currently_enrolled || (hasProgram ? "Selected Program" : "Not selected")}
            </dd>
          </div>
          <div className="border-b border-border py-3">
            <dt className="text-xs font-semibold text-muted">Year Level</dt>
            <dd className="mt-1 text-sm text-ink">{draft.year_level ? yearLevelLabel(draft.year_level) : "Not selected"}</dd>
          </div>
        </dl>
      </FieldGroup>

      <FieldGroup legend="Before you submit">
        {issues.length > 0 ? (
          <InventoryNotice title="Complete these answers" tone="warning">
            <p>Select an item below to go to the question.</p>
            <ul className="mt-3 space-y-2">
              {issues.map((issue, index) => (
                <li key={`${issue.section}-${index}`}>
                  <Button
                    variant="quiet"
                    className="h-auto min-h-8 whitespace-normal px-1 py-1 text-left"
                    onClick={() => onSelectIssue(issue)}
                  >
                    {issue.message}
                  </Button>
                </li>
              ))}
            </ul>
          </InventoryNotice>
        ) : null}
        {!programLookupReady ? (
          <p role="status" className="mt-4 text-sm leading-6 text-muted">
            Couldn’t load the program choices. Your saved program is unchanged.
          </p>
        ) : null}
        <p className="mt-4 text-sm leading-6 text-muted">
          You can’t edit your answers after submitting. Ask a counselor if you need to make a correction.
        </p>
      </FieldGroup>

      <FieldGroup legend="Sections">
        <ol className="grid gap-x-6 sm:grid-cols-2">
          {inventorySections
            .filter((section) => section.id !== "review")
            .map((section) => {
              const sectionIssues = issues.filter((issue) => issue.section === section.id);
              return (
                <li key={section.id} className="flex min-h-11 items-center justify-between gap-3 border-b border-border py-2">
                  <span className="text-sm text-ink">{section.label}</span>
                  {sectionIssues.length ? (
                    <span className="text-xs font-semibold text-warning">{sectionIssues.length} needs attention</span>
                  ) : null}
                </li>
              );
            })}
        </ol>
      </FieldGroup>
    </div>
  );
}
