import type {
  GeographicDistributionSection,
  ProgramColumn,
} from "@/lib/api/generated/model";
import { dataTable } from "@/components/ui/data-table";
import { formatReportPercentage, reportSection } from "@/features/reports/reports-shared";

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
            {section.label} with Province, Region, Program counts, total, and percentage
          </caption>
          <thead className={reportSection.tableHead}>
            <tr>
              <th
                scope="col"
                className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell} min-w-56`}
              >
                City / Municipality
              </th>
              <th scope="col" className={`${dataTable.headerCell} min-w-40`}>
                Province
              </th>
              <th scope="col" className={`${dataTable.headerCell} min-w-32`}>
                Region
              </th>
              {programColumns.map((program) => (
                <th
                  key={program.key}
                  scope="col"
                  className={`${dataTable.headerCell} min-w-36`}
                >
                  {programName(program)}
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
                    className={`${dataTable.cell} ${dataTable.stickyCell} min-w-56 font-medium text-ink`}
                  >
                    {row.label}
                  </th>
                  <td className={`${dataTable.cell} text-ink`}>
                    {row.province_name ?? "Not available"}
                  </td>
                  <td className={`${dataTable.cell} text-ink`}>
                    {row.region_name ?? "Not available"}
                  </td>
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
          No geographic data is available for this section.
        </p>
      ) : null}
    </section>
  );
}
