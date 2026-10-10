import type { GraduateTracerDistributionSection } from "@/lib/api/generated/model";
import { dataTable } from "@/components/ui/data-table";
import { formatReportPercentage, reportSection } from "@/features/reports/reports-shared";

export function GraduateTracerSection({
  section,
}: {
  section: GraduateTracerDistributionSection;
}) {
  const headingId = "graduate-tracer-section-" + section.key;
  return (
    <section aria-labelledby={headingId} className={reportSection.root}>
      <div className={reportSection.head}>
        <h3 id={headingId} className={reportSection.title}>
          {section.label}
        </h3>
        <p className="text-xs text-muted">
          Denominator: {section.denominator_label} ({section.denominator})
        </p>
        {section.multiple_selection ? (
          <p className="basis-full text-sm leading-6 text-muted">
            Respondents may select more than one answer, so percentages may total more than 100%.
          </p>
        ) : null}
      </div>
      <div
        role="region"
        aria-labelledby={headingId}
        tabIndex={0}
        className={reportSection.region}
      >
        <table className={`${dataTable.table} min-w-[34rem]`}>
          <caption className="sr-only">
            {section.label}; denominator {section.denominator_label}, {section.denominator}
          </caption>
          <thead className={reportSection.tableHead}>
            <tr>
              <th
                scope="col"
                className={`${dataTable.headerCell} ${dataTable.stickyHeaderCell} min-w-64`}
              >
                Category
              </th>
              <th scope="col" className={`${dataTable.headerCell} min-w-28`}>
                Count
              </th>
              <th scope="col" className={`${dataTable.headerCell} min-w-32`}>
                Percentage
              </th>
            </tr>
          </thead>
          <tbody className={dataTable.body}>
            {section.rows.map((row) => (
              <tr key={row.key} className={dataTable.row}>
                <th
                  scope="row"
                  className={`${dataTable.cell} ${dataTable.stickyCell} min-w-64 font-medium text-ink`}
                >
                  {row.label}
                </th>
                <td className={`${dataTable.cell} tabular-nums text-ink`}>
                  {row.count}
                </td>
                <td className={`${dataTable.cell} tabular-nums text-ink`}>
                  {formatReportPercentage(row.percentage)}
                </td>
              </tr>
            ))}
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
