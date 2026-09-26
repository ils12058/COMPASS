"use client";

import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { GraduateTracerResponse } from "@/features/graduate-tracer/graduate-tracer-response";
import { GraduateTracerError, GraduateTracerHeading, graduateTracerErrorCode } from "@/features/graduate-tracer/graduate-tracer-shared";
import { formatGraduateTracerDateTime } from "@/features/graduate-tracer/graduate-tracer-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError } from "@/lib/api/errors";
import { useGraduateTracerGetResponse } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import { GraduateTracerStatusValue } from "@/lib/api/generated/model";

export function GraduateTracerDetailPage({ responseId }: { responseId: string }) {
  const { user } = usePortalSession();
  const access = getGraduateTracerAccess(user);
  const detail = useGraduateTracerGetResponse(responseId, { query: { enabled: access.canViewOperational, retry: false } });

  if (!access.canViewOperational) {
    return (
      <section className="space-y-6">
        <GraduateTracerHeading title="Graduate Tracer response" />
        <p role="alert" className="border-y border-border py-5 text-sm leading-6 text-muted">Your current access does not allow you to view submitted Graduate Tracer responses.</p>
      </section>
    );
  }

  if (detail.isPending) {
    return <section className="space-y-6" aria-busy="true"><Skeleton className="h-9 w-64" /><Skeleton className="h-20 w-full" /><Skeleton className="h-56 w-full" /><p className="sr-only">Loading Graduate Tracer response…</p></section>;
  }

  const response = detail.data?.data;
  const mustHideCached = detail.error instanceof CompassApiError && [401, 403, 404].includes(detail.error.status);
  if ((!response && detail.isError) || mustHideCached) {
    return (
      <section className="space-y-6">
        <Link href="/portal/graduate-tracer" className="inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Graduate Tracer queue</Link>
        <GraduateTracerHeading title="Graduate Tracer response" />
        <GraduateTracerError error={detail.error} fallback={graduateTracerErrorCode(detail.error) === "graduate_tracer_not_submitted" ? "This response is not available because it has not been submitted." : "The submitted Graduate Tracer response could not be loaded."} onRetry={() => void detail.refetch()} />
      </section>
    );
  }

  if (!response) return null;
  if (response.status !== GraduateTracerStatusValue.SUBMITTED) {
    return (
      <section className="space-y-6">
        <Link href="/portal/graduate-tracer" className="inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Graduate Tracer queue</Link>
        <GraduateTracerHeading title="Graduate Tracer response" />
        <p role="alert" className="border-y border-border py-5 text-sm leading-6 text-muted">This response has not been submitted, so it is not available for review.</p>
      </section>
    );
  }
  return (
    <section className="space-y-6">
      <Link href="/portal/graduate-tracer" className="inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Back to Graduate Tracer queue</Link>
      <GraduateTracerHeading
        title={response.name || response.student.display_name}
        description={
          response.student.institutional_id
            ? `Submitted Graduate Tracer response · ${response.student.institutional_id}`
            : "Submitted Graduate Tracer response"
        }
        action={<span className="text-sm text-muted">Submitted {formatGraduateTracerDateTime(response.submitted_at)}</span>}
      />
      {detail.isFetching ? <p role="status" className="text-xs text-muted">Refreshing submitted response…</p> : null}
      {detail.isError ? <GraduateTracerError error={detail.error} fallback="The response could not be refreshed. Showing the last confirmed response." onRetry={() => void detail.refetch()} /> : null}
      <GraduateTracerResponse detail={response} />
    </section>
  );
}
