import type {
  DistributionSection,
  ProgramColumn,
} from "@/lib/api/generated/model";
import { formatReportPercentage } from "@/features/reports/reports-shared";

function programName(program: ProgramColumn): string {
  if (program.is_legacy) return program.name;
  return (program.code ? program.code + " — " : "") + program.name;
}

function programContext(program: ProgramColumn): string {
  if (program.is_legacy) return "Legacy Program identity";
  return [
    program.college
      ? "College: " + program.college.code + " — " + program.college.name
      : null,
    program.campus
      ? "Campus: " + program.campus.code + " — " + program.campus.name
      : null,
  ]
    .filter((value): value is string => Boolean(value))
    .join(" · ");
}

export function StudentProfileProgramLegend({
  columns,
}: {
  columns: ProgramColumn[];
}) {
  if (columns.length < 2) return null;
  return (
    <section
      aria-labelledby="student-profile-program-legend-heading"
      className="mt-6 border-y border-border py-4"
    >
      <h2
        id="student-profile-program-legend-heading"
        className="text-sm font-semibold text-ink"
      >
        Program columns
      </h2>
      <ul className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 xl:grid-cols-3">
        {columns.map((program) => (
          <li key={program.key} className="min-w-0">
            <span className="font-semibold text-ink">{programName(program)}</span>
            {programContext(program) ? (
              <span className="mt-0.5 block break-words text-xs text-muted">
                {programContext(program)}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function StudentProfileSection({
  section,
  programColumns,
}: {
  section: DistributionSection;
  programColumns: ProgramColumn[];
}) {
  const headingId = "student-profile-section-" + section.key;

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
            {section.label} distribution by Program, with total and percentage
          </caption>
          <thead className="bg-surface-muted text-xs text-muted">
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 min-w-52 bg-surface-muted px-3 py-3 font-semibold"
              >
                Category
              </th>
              {programColumns.map((program) => (
                <th
                  key={program.key}
                  scope="col"
                  className="min-w-36 px-3 py-3 font-semibold"
                  title={programContext(program) || undefined}
                >
                  <span className="block text-ink">{programName(program)}</span>
                  {programContext(program) ? (
                    <span className="mt-1 block max-w-56 text-xs font-normal leading-4 text-muted">
                      {programContext(program)}
                    </span>
                  ) : null}
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
                    className="sticky left-0 z-10 min-w-52 bg-surface px-3 py-3 font-medium text-ink"
                  >
                    {row.label}
                  </th>
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
          No categories were returned for this section.
        </p>
      ) : null}
    </section>
  );
}
