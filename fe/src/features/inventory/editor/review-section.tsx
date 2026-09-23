"use client";

import { Button } from "@/components/ui/button";
import type { InventorySubmissionIssue } from "@/features/inventory/inventory-payload";
import { inventorySections, type InventorySectionId } from "@/features/inventory/inventory-presentation";
import { FieldGroup, InventoryNotice } from "@/features/inventory/inventory-shared";
import type { InventoryPayload } from "@/lib/api/generated/model";

export function ReviewSection({
  draft,
  academicYear,
  formRevision,
  issues,
  programLookupReady,
  onSelectSection,
}: {
  draft: InventoryPayload;
  academicYear: string;
  formRevision: string;
  issues: InventorySubmissionIssue[];
  programLookupReady: boolean;
  onSelectSection: (section: InventorySectionId) => void;
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
            <dd className="mt-1 text-sm text-ink">{draft.year_level ?? "Not selected"}</dd>
          </div>
        </dl>
      </FieldGroup>

      <FieldGroup legend="Submission readiness">
        {issues.length === 0 ? (
          <InventoryNotice tone="success">
            No immediate required-field issues were found. The backend remains authoritative for final validation.
          </InventoryNotice>
        ) : (
          <InventoryNotice title="Needs attention before submission" tone="warning">
            <p>Complete the required details below. Selecting an item returns you to its section.</p>
            <ul className="mt-3 space-y-2">
              {issues.map((issue, index) => (
                <li key={`${issue.section}-${index}`}>
                  <Button
                    variant="quiet"
                    className="h-auto min-h-8 whitespace-normal px-1 py-1 text-left"
                    onClick={() => onSelectSection(issue.section)}
                  >
                    {issue.message}
                  </Button>
                </li>
              ))}
            </ul>
          </InventoryNotice>
        )}
        {!programLookupReady ? (
          <p role="status" className="mt-4 text-sm leading-6 text-muted">
            Active Program choices could not be verified just now. The saved selection is preserved; final submission is still checked by COMPASS.
          </p>
        ) : null}
        <p className="mt-4 text-sm leading-6 text-muted">
          Submitting changes this annual record to read-only. An authorized Counselor may reopen the current-year record if a correction is needed. COMPASS does not use an approval workflow or digital signature for this action.
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
                  <span className={sectionIssues.length ? "text-xs font-semibold text-warning" : "text-xs text-muted"}>
                    {sectionIssues.length ? `${sectionIssues.length} needs attention` : "No immediate issue"}
                  </span>
                </li>
              );
            })}
        </ol>
      </FieldGroup>
    </div>
  );
}
