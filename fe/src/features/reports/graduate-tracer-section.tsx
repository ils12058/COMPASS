import type { GraduateTracerDistributionSection } from "@/lib/api/generated/model";
import { formatReportPercentage } from "@/features/reports/reports-shared";

export function GraduateTracerSection({
  section,
}: {
  section: GraduateTracerDistributionSection;
}) {
  const headingId = "graduate-tracer-section-" + section.key;
  return (
    <section aria-labelledby={headingId} className="mt-8">
      <h3
        id={headingId}
        className="font-heading text-lg font-semibold text-ink"
      >
        {section.label}
      </h3>
      <p className="mt-1 text-xs text-muted">
        Denominator: {section.denominator_label} ({section.denominator})
      </p>
      {section.multiple_selection ? (
        <p className="mt-3 border-l-2 border-border pl-3 text-sm leading-6 text-muted">
          Respondents may select more than one answer, so percentages may total more than 100%.
        </p>
      ) : null}
      <div
        role="region"
        aria-labelledby={headingId}
        tabIndex={0}
        className="mt-3 overflow-x-auto border-y border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
          <caption className="sr-only">
            {section.label}; denominator {section.denominator_label}, {section.denominator}
          </caption>
          <thead className="bg-surface-muted text-xs text-muted">
            <tr>
              <th
                scope="col"
                className="sticky left-0 z-10 min-w-64 bg-surface-muted px-3 py-3 font-semibold"
              >
                Category
              </th>
              <th scope="col" className="min-w-28 px-3 py-3 font-semibold">
                Count
              </th>
              <th scope="col" className="min-w-32 px-3 py-3 font-semibold">
                Percentage
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {section.rows.map((row) => (
              <tr key={row.key}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 min-w-64 bg-surface px-3 py-3 font-medium text-ink"
                >
                  {row.label}
                </th>
                <td className="px-3 py-3 tabular-nums text-ink">
                  {row.count}
                </td>
                <td className="px-3 py-3 tabular-nums text-ink">
                  {formatReportPercentage(row.percentage)}
                </td>
              </tr>
            ))}
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
