import type {
  DistributionSection,
  ProgramColumn,
} from "@/lib/api/generated/model";
import { dataTable } from "@/components/ui/data-table";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { formatReportPercentage, reportSection } from "@/features/reports/reports-shared";

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
    <Panel aria-labelledby="student-profile-program-legend-heading">
      <PanelHeader title="Program columns" titleId="student-profile-program-legend-heading" />
      <PanelBody>
      <ul className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2 xl:grid-cols-3">
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
      </PanelBody>
    </Panel>
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
    <section aria-labelledby={headingId} className={reportSection.root}>
      <div className={reportSection.head}>
        <h3 id={headingId} className={reportSection.title}>
          {section.label}
        </h3>
        <p className="text-xs text-muted">Denominator: {section.denominator}</p>
      </div>
      <div
        role="region"
        aria-labelledby={headingId}
        tabIndex={0}
        className={reportSection.region}
      >
        <table className={`${dataTable.table} min-w-max`}>
          <caption className="sr-only">
            {section.label} distribution by Program, with total and percentage
          </caption>
          <thead className={reportSection.tableHead}>
            <tr>
              <th
                scope="col"
                className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell} min-w-52`}
              >
                Category
              </th>
              {programColumns.map((program) => (
                <th
                  key={program.key}
                  scope="col"
                  className={`${dataTable.headerCell} min-w-36`}
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
              <th scope="col" className={`${dataTable.headerCell} min-w-24`}>
                Total
              </th>
              <th scope="col" className={`${dataTable.headerCell} min-w-28`}>
                Percentage
              </th>
            </tr>
          </thead>
          <tbody className={dataTable.body}>
            {section.rows.map((row) => {
              const countsByProgram = new Map(
                row.program_counts.map((count) => [
                  count.program_key,
                  count.count,
                ]),
              );
              return (
                <tr key={row.key} className={dataTable.row}>
                  <th
                    scope="row"
                    className={`${dataTable.cell} ${dataTable.stickyCell} min-w-52 font-medium text-ink`}
                  >
                    {row.label}
                  </th>
                  {programColumns.map((program) => (
                    <td
                      key={program.key}
                      className={`${dataTable.cell} tabular-nums text-ink`}
                    >
                      {String(countsByProgram.get(program.key) ?? 0)}
                    </td>
                  ))}
                  <td className={`${dataTable.cell} font-semibold tabular-nums text-ink`}>
                    {row.total_count}
                  </td>
                  <td className={`${dataTable.cell} tabular-nums text-ink`}>
                    {formatReportPercentage(row.percentage)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {section.rows.length === 0 ? (
        <p className={reportSection.empty}>
          No data is available for this section.
        </p>
      ) : null}
    </section>
  );
}
