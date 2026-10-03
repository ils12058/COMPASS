"use client";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { useStudentSupportGetContext } from "@/lib/api/generated/student-support/student-support";
import { InventoryStatusValue } from "@/lib/api/generated/model";

function ContextUnavailable({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const code = error instanceof CompassApiError ? readApiErrorCode(error.body) : undefined;
  const denied = error instanceof CompassApiError && (error.status === 401 || error.status === 403);
  const message =
    code === "student_support_not_found"
      ? "Support information for this student is unavailable to you."
      : code === "current_academic_year_not_configured"
        ? "Support information is unavailable until the current academic year is set up."
        : denied
          ? "Student support information is unavailable to this account."
          : "Student support information could not be loaded.";
  const canRetry = !denied && code !== "student_support_not_found" && code !== "current_academic_year_not_configured";
  return (
    <div role="alert" className="mt-3">
      <p className="text-sm leading-6 text-muted">{message}</p>
      {canRetry ? (
        <Button variant="secondary" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

// Privacy-minimized Guidance context: the current Academic Year's recorded
// support facts only, never Inventory answers, scores, or rankings.
export function StudentSupportContextSection({ studentId }: { studentId: string }) {
  const context = useStudentSupportGetContext(studentId, { query: { retry: false } });

  return (
    <section aria-labelledby="student-support-context-heading" className="border-t border-border py-6">
      <h2 id="student-support-context-heading" className="font-heading text-xl font-semibold text-ink">
        Student support context
      </h2>

      {context.isPending ? (
        <div aria-busy="true" className="mt-4 space-y-2">
          <Skeleton className="h-4 w-56" />
          <Skeleton className="h-10 w-full max-w-md" />
          <p className="sr-only">Loading Student support context…</p>
        </div>
      ) : context.isError ? (
        <ContextUnavailable error={context.error} onRetry={() => void context.refetch()} />
      ) : (
        <div className="mt-2">
          <p className="text-sm text-muted">
            {context.data.data.academic_year.label} · From the Student&apos;s current Individual Inventory
          </p>
          {context.data.data.inventory_status === InventoryStatusValue.MISSING ? (
            <p className="mt-3 text-sm leading-6 text-ink">
              The student has not started this year’s Individual Inventory, so no support information is available.
            </p>
          ) : context.data.data.inventory_status === InventoryStatusValue.DRAFT || !context.data.data.available ? (
            <p className="mt-3 text-sm leading-6 text-ink">
              This year’s Individual Inventory has not been submitted, so no support information is available.
            </p>
          ) : context.data.data.indicators.length > 0 ? (
            <ul className="mt-3 max-w-md divide-y divide-border border-y border-border">
              {context.data.data.indicators.map((indicator) => (
                <li key={indicator.code} className="py-2.5 text-sm text-ink">{indicator.label}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm leading-6 text-ink">No support indicators are recorded.</p>
          )}
          {context.data.data.available ? (
            <p className="mt-3 max-w-2xl text-xs leading-5 text-muted">
              Indicators reflect what the Student recorded. The absence of an indicator does not mean the opposite is true.
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}
