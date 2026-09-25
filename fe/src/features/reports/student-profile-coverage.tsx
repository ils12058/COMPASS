import type { InventoryCoverage, Methodology } from "@/lib/api/generated/model";

const FILTER_LABELS: Record<string, string> = {
  access_scope: "authorized report scope",
  academic_year_id: "Academic Year",
  campus_id: "Campus",
  college_id: "College",
  program_id: "Program",
  year_level: "Year Level",
};

function countValue(value: number | null): string {
  return value === null ? "Unavailable" : String(value);
}

export function StudentProfileCoverage({
  coverage,
  methodology,
}: {
  coverage: InventoryCoverage;
  methodology: Methodology;
}) {
  const values =
    coverage.mode === "CURRENT"
      ? [
          { label: "Eligible Students", value: countValue(coverage.eligible_student_count) },
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
  const ignored = coverage.ignored_filters.map(
    (filter) => FILTER_LABELS[filter] ?? filter,
  );

  return (
    <section
      aria-labelledby="inventory-coverage-heading"
      className="mt-8 border-y border-border py-5"
    >
      <h2
        id="inventory-coverage-heading"
        className="font-heading text-xl font-semibold text-ink"
      >
        Inventory Coverage
      </h2>
      <p className="mt-3 max-w-5xl text-sm leading-6 text-muted">
        {coverage.scope_note}
      </p>
      <dl className="mt-5 grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
        {values.map((item) => (
          <div key={item.label} className="border-l-2 border-border pl-3">
            <dt className="text-sm text-muted">{item.label}</dt>
            <dd className="mt-1 text-xl font-semibold text-ink">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>
      {coverage.mode === "HISTORICAL_LIMITED" ? (
        <p className="mt-5 border-l-2 border-warning pl-3 text-sm leading-6 text-muted">
          {methodology.historical_coverage_note ??
            "Historical missing-Inventory coverage cannot be reconstructed from current COMPASS data."}
        </p>
      ) : null}
      {ignored.length > 0 ? (
        <p className="mt-5 border-l-2 border-warning pl-3 text-sm leading-6 text-muted">
          Inventory Coverage does not use these selected filters: {ignored.join(", ")}.
          {coverage.ignored_filters.some(
            (filter) => filter === "program_id" || filter === "year_level",
          )
            ? " Program and Year Level cannot classify Students without an Individual Inventory."
            : ""}
        </p>
      ) : null}
    </section>
  );
}
