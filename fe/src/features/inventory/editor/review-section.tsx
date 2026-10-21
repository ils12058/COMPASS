"use client";

import { FormErrorSummary } from "@/components/ui/form-experience";
import { Button } from "@/components/ui/button";
import type { InventorySubmissionIssue } from "@/features/inventory/inventory-payload";
import { inventorySections, type InventorySectionId } from "@/features/inventory/inventory-presentation";
import { FieldGroup } from "@/features/inventory/inventory-shared";
import type { InventoryPayload, ProgramSummary } from "@/lib/api/generated/model";
import { yearLevelLabel } from "@/lib/year-level";

export function ReviewSection({
  draft,
  academicYear,
  formRevision,
  issues,
  programLookupReady,
  selectedProgram,
  onSelectIssue,
  onSelectSection,
}: {
  draft: InventoryPayload;
  academicYear: string;
  formRevision: string;
  issues: InventorySubmissionIssue[];
  programLookupReady: boolean;
  selectedProgram: ProgramSummary | null;
  onSelectIssue: (issue: InventorySubmissionIssue) => void;
  onSelectSection: (section: InventorySectionId) => void;
}) {
  const hasProgram = Boolean(draft.program_id);
  const yearLevelIsUnsupported = Boolean(
    draft.year_level !== null &&
      draft.year_level !== undefined &&
      selectedProgram?.year_level_policy_status === "CONFIGURED" &&
      selectedProgram.applicable_year_levels &&
      !selectedProgram.applicable_year_levels.includes(draft.year_level),
  );
  return (
    <div className="space-y-7">
      <FieldGroup legend="Record details">
        <dl className="grid gap-x-6 @md/inventory:grid-cols-2">
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
            <dd className="mt-1 text-sm text-ink">
              {draft.year_level
                ? `${yearLevelLabel(draft.year_level)}${yearLevelIsUnsupported ? " (saved value; unsupported for this Program)" : !selectedProgram && draft.year_level > 4 ? " (recorded value)" : ""}`
                : "Not selected"}
            </dd>
            {selectedProgram?.year_level_policy_status === "PENDING_POLICY" ? (
              <p className="mt-1 text-xs leading-5 text-muted">
                The Year Level policy for this Program is pending institutional confirmation.
              </p>
            ) : null}
          </div>
        </dl>
      </FieldGroup>

      <FieldGroup legend="Before you submit">
        <FormErrorSummary id="inventory-validation-heading" issues={issues} onSelect={onSelectIssue} />
        {!issues.length ? <p className="text-sm leading-6 text-ink">No required answers are missing. Review your sections below before submitting.</p> : null}
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
        <ol className="grid gap-x-6 @md/inventory:grid-cols-2">
          {inventorySections
            .filter((section) => section.id !== "review")
            .map((section) => {
              const sectionIssues = issues.filter((issue) => issue.section === section.id);
              return (
                <li key={section.id} className="flex min-h-11 items-center justify-between gap-3 border-b border-border py-2">
                  <Button variant="quiet" className="min-h-11 justify-start whitespace-normal px-0 text-left" onClick={() => onSelectSection(section.id)} aria-label={`Review ${section.label}`}>
                    {section.label}
                  </Button>
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
