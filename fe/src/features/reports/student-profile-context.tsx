import type { StudentProfilingReportResponse } from "@/lib/api/generated/model";
import { reportGeneratedAt } from "@/features/reports/reports-shared";

function referenceLabel(
  reference: { code: string; name: string } | null,
): string | null {
  return reference ? reference.code + " — " + reference.name : null;
}

export function StudentProfileContext({
  report,
  isGlobal,
}: {
  report: StudentProfilingReportResponse;
  isGlobal: boolean;
}) {
  const context = report.report_context;
  const campus =
    referenceLabel(context.campus) ??
    (isGlobal ? "All Campuses" : "All authorized Campuses");
  const college =
    referenceLabel(context.college) ??
    (context.campus
      ? isGlobal
        ? "All Colleges on selected Campus"
        : "All authorized Colleges on selected Campus"
      : isGlobal
        ? "All Colleges"
        : "All authorized Colleges");
  const program =
    referenceLabel(context.program) ??
    (context.college
      ? "All Programs in selected College"
      : isGlobal
        ? "All Programs"
        : "All authorized Programs");
  const yearLevel =
    context.year_level_label ?? "All Year Levels";

  const values = [
    { label: "Academic Year", value: context.academic_year.label },
    { label: "Campus", value: campus },
    { label: "College", value: college },
    { label: "Program", value: program },
    { label: "Year Level", value: yearLevel },
    {
      label: "Submitted Inventory Count",
      value: String(context.submitted_inventory_count),
    },
    { label: "Generated At", value: reportGeneratedAt(context.generated_at) },
  ];

  return (
    <section
      aria-labelledby="student-profile-context-heading"
      className="mt-6 border-y border-border py-5"
    >
      <h2
        id="student-profile-context-heading"
        className="font-heading text-lg font-semibold text-ink"
      >
        Report context
      </h2>
      <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
        {values.map((item) => (
          <div key={item.label} className="min-w-0">
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
              {item.label}
            </dt>
            <dd className="mt-1 break-words text-sm font-medium text-ink">
              {item.value}
              {item.label === "Academic Year" && context.academic_year.is_current
                ? " (Current)"
                : ""}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
