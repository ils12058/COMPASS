import { Panel, PanelHeader } from "@/components/ui/panel";
import type { InventoryCoverage, Methodology } from "@/lib/api/generated/model";

const FILTER_LABELS: Record<string, string> = {
  access_scope: "authorized reporting area",
  academic_year_id: "Academic Year",
  campus_id: "Campus",
  college_id: "College",
  program_id: "Program",
  year_level: "Year Level",
};

function countValue(value: number | null): string {
  return value === null ? "Unavailable" : String(value);
}

// Limits on what the counts above can show; each sits under the counts, separated by the panel's line.
const coverageNote = "border-t border-brand-line px-4 py-3 text-sm leading-6 text-ink sm:px-5";

export function StudentProfileCoverage({
  coverage,
  methodology,
}: {
  coverage: InventoryCoverage;
  methodology: Methodology;
}) {
  const isCurrent = coverage.mode === "CURRENT";
  const reconciliation = coverage.reconciliation;
  const values =
    isCurrent
      ? [
          { label: "Eligible current Students", value: countValue(coverage.eligible_student_count) },
          { label: "Submitted", value: String(coverage.submitted_count) },
          { label: "Draft", value: String(coverage.draft_count) },
          {
            label: "Without Individual Inventory",
            value: countValue(coverage.missing_count),
          },
        ]
      : [
          { label: "Submitted", value: String(coverage.submitted_count) },
          { label: "Draft", value: String(coverage.draft_count) },
          {
            label: "Without Individual Inventory",
            value: "Unavailable for historical Academic Years",
          },
        ];
  const comparison = isCurrent
    ? [
        { label: "Profile Inventories counted here", value: reconciliation.in_both_count },
        { label: "Profile Inventories not counted here", value: reconciliation.profile_only_count },
        { label: "Submitted here, outside profile filters", value: reconciliation.coverage_only_count },
      ]
    : [
        { label: "In the profile population", value: reconciliation.in_both_count },
        { label: "Outside the profile filters", value: reconciliation.coverage_only_count },
      ];
  const ignored = coverage.ignored_filters.map(
    (filter) => FILTER_LABELS[filter] ?? filter,
  );

  return (
    <Panel className="overflow-hidden" aria-labelledby="inventory-coverage-heading">
      <PanelHeader
        title={isCurrent ? "Current Student Inventory Coverage" : "Inventory Coverage (historical)"}
        titleId="inventory-coverage-heading"
        description={coverage.scope_note}
      />
      <dl className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2 xl:grid-cols-4">
        {values.map((item) => (
          <div key={item.label} className="min-w-0 bg-surface-raised px-4 py-3.5 sm:px-5">
            <dt className="text-sm text-muted">{item.label}</dt>
            <dd className="mt-1 font-heading text-xl font-semibold tabular-nums text-ink">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>
      {coverage.mode === "HISTORICAL_LIMITED" ? (
        <p className={coverageNote}>
          {methodology.historical_coverage_note ??
            "Historical missing-Inventory coverage cannot be reconstructed from current COMPASS data."}
        </p>
      ) : null}
      <div className="border-t border-brand-line">
        <p className="px-4 pt-3 text-sm font-semibold text-ink sm:px-5">
          Compared with the Submitted Inventory Profile Population
        </p>
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 px-4 pb-3 pt-2 sm:grid-cols-3 sm:px-5">
          {comparison.map((item) => (
            <div key={item.label} className="min-w-0">
              <dt className="text-sm text-muted">{item.label}</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-ink">{item.value}</dd>
            </div>
          ))}
        </dl>
        <p className="px-4 pb-3 text-sm text-muted sm:px-5">
          The populations are counted differently, so no submission rate is calculated.
        </p>
      </div>
      {ignored.length > 0 ? (
        <p className={coverageNote}>
          Inventory Coverage does not use these selected filters: {ignored.join(", ")}.
          {coverage.ignored_filters.some(
            (filter) => filter === "program_id" || filter === "year_level",
          )
            ? " Program and Year Level cannot classify Students without an Individual Inventory."
            : ""}
        </p>
      ) : null}
    </Panel>
  );
}
