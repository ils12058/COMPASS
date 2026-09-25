import type {
  GeographicDistributionSection,
  ProgramColumn,
} from "@/lib/api/generated/model";
import { formatReportPercentage } from "@/features/reports/reports-shared";

function programName(program: ProgramColumn): string {
  if (program.is_legacy) return program.name;
  return (program.code ? program.code + " — " : "") + program.name;
}

export function StudentProfileGeographySection({
  section,
  programColumns,
}: {
  section: GeographicDistributionSection;
  programColumns: ProgramColumn[];
}) {
  const headingId = "student-profile-geography-heading";
  return (
    <section aria-labelledby={headingId} className="mt-8">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3
          id={headingId}
          className="font-heading text-lg font-semibold text-ink"
        >
          {section.label}
        </h3>
        <p className="text-xs text-muted">Denominator: {section.denominator}</p>
      </div>
      <div
        role="region"
        aria-labelledby={headingId}
        tabIndex={0}
        className="mt-3 overflow-x-auto border-y border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        <table className="min-w-max w-full border-collapse text-left text-sm">
          <caption className="sr-only">
            {section.label} with Province, Region, Program counts, total, and percentage
          </caption>
          <thead className="bg-surface-muted text-xs text-muted">
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 min-w-56 bg-surface-muted px-3 py-3 font-semibold"
              >
                City / Municipality
              </th>
              <th scope="col" className="min-w-40 px-3 py-3 font-semibold">
                Province
              </th>
              <th scope="col" className="min-w-32 px-3 py-3 font-semibold">
                Region
              </th>
              {programColumns.map((program) => (
                <th
                  key={program.key}
                  scope="col"
                  className="min-w-36 px-3 py-3 font-semibold"
                >
                  {programName(program)}
                </th>
              ))}
              <th scope="col" className="min-w-24 px-3 py-3 font-semibold">
                Total
              </th>
              <th scope="col" className="min-w-28 px-3 py-3 font-semibold">
                Percentage
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {section.rows.map((row) => {
              const countsByProgram = new Map(
                row.program_counts.map((count) => [
                  count.program_key,
                  count.count,
                ]),
              );
              return (
                <tr key={row.key}>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 min-w-56 bg-surface px-3 py-3 font-medium text-ink"
                  >
                    {row.label}
                  </th>
                  <td className="px-3 py-3 text-ink">
                    {row.province_name ?? "Not available"}
                  </td>
                  <td className="px-3 py-3 text-ink">
                    {row.region_name ?? "Not available"}
                  </td>
                  {programColumns.map((program) => (
                    <td
                      key={program.key}
                      className="px-3 py-3 tabular-nums text-ink"
                    >
                      {String(countsByProgram.get(program.key) ?? 0)}
                    </td>
                  ))}
                  <td className="px-3 py-3 font-semibold tabular-nums text-ink">
                    {row.total_count}
                  </td>
                  <td className="px-3 py-3 tabular-nums text-ink">
                    {formatReportPercentage(row.percentage)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {section.rows.length === 0 ? (
        <p className="border-b border-border py-4 text-sm text-muted">
          No geographic categories were returned for this section.
        </p>
      ) : null}
    </section>
  );
}
